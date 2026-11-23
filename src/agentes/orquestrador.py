"""Orquestração da Fase 1: do pedido do usuário até o script aprovado e testado."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Literal

import openpyxl

from src.agentes.comum.execucao import CodigoRecusado
from src.agentes.comum.llm import LLM, Mensagem
from src.agentes.construtor.montador import configurar, funcao_de, montar, nome_do_script
from src.contratos.ficha import Ficha, FichaInvalida


@dataclass
class ResultadoFase1:
    """Resultado consolidado da execução da Fase 1."""

    situacao: Literal["aprovado", "reprovado", "cancelado"]
    ficha: Ficha | None
    script: Path | None
    voltas: int
    historico: list[str]


class _RegistroLocal:
    """Fallback compatível com RegistroDeChamadas enquanto registro.py não existe."""

    def __init__(self) -> None:
        self._entradas: list[dict[str, Any]] = []

    def anotar(self, agente: str, mensagens: list[Mensagem], resposta: str) -> None:
        self._entradas.append(
            {
                "agente": agente,
                "mensagens": [dict(m) for m in mensagens],
                "resposta": resposta,
            }
        )

    def texto_enviado(self) -> str:
        partes: list[str] = []
        for entrada in self._entradas:
            for msg in entrada["mensagens"]:
                partes.append(msg.get("content", ""))
        return "\n".join(partes)

    def salvar(self, arquivo: str) -> None:
        Path(arquivo).write_text(
            json.dumps(self._entradas, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class _LLMRegistradoLocal:
    """Fallback compatível com LLMRegistrado enquanto registro.py não existe."""

    def __init__(self, llm: LLM, registro: Any, agente: str) -> None:
        self._llm = llm
        self._registro = registro
        self._agente = agente

    def conversar(self, mensagens: list[Mensagem]) -> str:
        resposta = self._llm.conversar(mensagens)
        self._registro.anotar(self._agente, mensagens, resposta)
        return resposta


def _criar_registro() -> Any:
    """Instancia RegistroDeChamadas oficial ou o fallback local."""
    try:
        from src.agentes.comum.registro import RegistroDeChamadas

        return RegistroDeChamadas()
    except ImportError:
        return _RegistroLocal()


def _envolver_llm(llm: LLM, registro: Any, agente: str) -> LLM:
    """Envolve o LLM com LLMRegistrado para auditar tudo o que sai da máquina."""
    try:
        from src.agentes.comum.registro import LLMRegistrado

        return LLMRegistrado(llm, registro, agente)
    except ImportError:
        return _LLMRegistradoLocal(llm, registro, agente)


def _primeira_aba(caminho: Path) -> str:
    """Obtém o nome da primeira aba de uma planilha Excel."""
    livro = openpyxl.load_workbook(caminho, read_only=True)
    try:
        return livro.sheetnames[0]
    finally:
        livro.close()


def _extrair_raio_x_e_amostras(planilhas: dict[str, Path]) -> tuple[list[Any], list[list[dict]]]:
    """Gera raio-x e amostra disfarçada da primeira aba de cada planilha."""
    from src.nucleo.disfarce import amostra_disfarcada, raio_x

    lista_raio_x: list[Any] = []
    lista_amostras: list[list[dict]] = []
    for caminho in planilhas.values():
        aba = _primeira_aba(Path(caminho))
        lista_raio_x.append(raio_x(str(caminho), aba, linha_cabecalho=1))
        lista_amostras.append(amostra_disfarcada(str(caminho), aba, linha_cabecalho=1))
    return lista_raio_x, lista_amostras


def _obter_descricoes_catalogo() -> list[Any]:
    """Lê as descrições das funções disponíveis no catálogo do núcleo."""
    from src.nucleo.catalogo import descricoes

    return descricoes()


def _chamar_decidir(llm: LLM, pedido: str, raio_x: list[Any], indice: list[dict]) -> Any:
    """Aciona o agente de busca para decidir entre reaproveitar ou criar script."""
    from src.agentes.construtor.busca import decidir

    return decidir(llm, pedido, raio_x, indice)


def _chamar_preencher(
    llm: LLM, pedido: str, raio_x: list[Any], amostras: list[list[dict]]
) -> Ficha:
    """Aciona o agente de ficha para estruturar o pedido do usuário."""
    from src.agentes.construtor.ficha import preencher

    return preencher(llm, pedido, raio_x, amostras)


def _chamar_escrever_testes(llm: LLM, ficha: Ficha, descricao_kit: str) -> str:
    """Aciona o Revisor para gerar a suíte de testes a partir da ficha."""
    from src.agentes.revisor.designer_testes import escrever_testes

    return escrever_testes(llm, ficha, descricao_kit)


def _obter_descricao_kit() -> str:
    """Obtém a descrição textual do kit de testes do Revisor."""
    try:
        from src.agentes.revisor.kit_testes import DESCRICAO_KIT

        return DESCRICAO_KIT
    except ImportError:
        return ""


def _chamar_gerar_corpo(
    llm: LLM,
    ficha: Ficha,
    descricoes: list[Any],
    exemplo: str | None = None,
    aviso_anterior: str | None = None,
) -> str:
    """Aciona o Construtor para gerar a função executar(config)."""
    from src.agentes.construtor.gerador import gerar_corpo

    return gerar_corpo(
        llm,
        ficha,
        descricoes,
        exemplo=exemplo,
        aviso_anterior=aviso_anterior,
    )


def _chamar_executar_testes(script: Path, testes: Path, tempo_limite: int = 60) -> Any:
    """Executa o pytest sobre o script candidato usando o executor do Revisor."""
    from src.agentes.revisor.executor import executar

    return executar(script, testes, tempo_limite=tempo_limite)


class Orquestrador:
    """Coordena o ciclo completo da Fase 1 entre Construtor e Revisor."""

    def __init__(
        self,
        llm: LLM,
        pasta_aprovados: Path,
        max_voltas: int = 3,
        modo: Literal["dois_agentes", "um_agente"] = "dois_agentes",
        pasta_trabalho: Path = Path("saida/candidatos"),
    ) -> None:
        """Inicializa o orquestrador da Fase 1.

        Recebe:
            llm: cliente de modelo de linguagem (real ou falso).
            pasta_aprovados: diretório onde scripts aprovados e indice.json ficam salvos.
            max_voltas: número máximo de tentativas de geração e correção.
            modo: 'dois_agentes' (com Revisor) ou 'um_agente' (sem Revisor).
            pasta_trabalho: diretório temporário para tentativas intermediárias.
        """
        self._llm = llm
        self.pasta_aprovados = Path(pasta_aprovados)
        self.max_voltas = max_voltas
        self.modo = modo
        self.pasta_trabalho = Path(pasta_trabalho)
        self.registro = _criar_registro()

    def fase1(
        self,
        pedido: str,
        planilhas: dict[str, Path],
        confirmar: Callable[[Ficha], Ficha | None],
    ) -> ResultadoFase1:
        """Executa o fluxo da Fase 1 desde o pedido até a aprovação ou reprovação.

        Recebe:
            pedido: descrição em linguagem natural da automação desejada.
            planilhas: mapa de rótulo ('origem', 'destino') para o caminho do arquivo.
            confirmar: função de callback que valida/ajusta a ficha ou retorna None.
        Devolve:
            ResultadoFase1 com situação, ficha final, caminho do script, voltas e histórico.
        Garante:
            Nunca chama input(), nunca envia dados reais ao LLM e só salva aprovados na biblioteca.
        """
        historico: list[str] = []
        llm_busca = _envolver_llm(self._llm, self.registro, "busca")
        llm_ficha = _envolver_llm(self._llm, self.registro, "ficha")
        llm_revisor = _envolver_llm(self._llm, self.registro, "revisor")
        llm_construtor = _envolver_llm(self._llm, self.registro, "construtor")

        lista_raio_x, lista_amostras = _extrair_raio_x_e_amostras(planilhas)
        indice = self._ler_indice()

        decisao = _chamar_decidir(llm_busca, pedido, lista_raio_x, indice)
        historico.append(f"Busca: {decisao.motivo}")

        ficha_bruta = _chamar_preencher(llm_ficha, pedido, lista_raio_x, lista_amostras)
        ficha_bruta.pedido = pedido
        ficha_bruta.confirmada = False

        ficha_confirmada = confirmar(ficha_bruta)
        if ficha_confirmada is None:
            historico.append("Cancelado pelo usuário na confirmação da ficha.")
            return ResultadoFase1(
                situacao="cancelado",
                ficha=ficha_bruta,
                script=None,
                voltas=0,
                historico=historico,
            )

        ficha_confirmada.confirmada = True
        problemas = ficha_confirmada.problemas()
        if problemas:
            raise FichaInvalida("; ".join(problemas))

        codigo_testes = ""
        if self.modo == "dois_agentes":
            codigo_testes = _chamar_escrever_testes(
                llm_revisor, ficha_confirmada, _obter_descricao_kit()
            )
            historico.append("Testes gerados pelo Revisor.")

        if decisao.reaproveitar:
            pasta_existente = self.pasta_aprovados / decisao.reaproveitar
            if (pasta_existente / "script.py").is_file():
                return self._fluxo_reaproveitamento(
                    ficha_confirmada,
                    pasta_existente,
                    codigo_testes,
                    historico,
                )

        return self._fluxo_criacao(
            llm_construtor,
            ficha_confirmada,
            decisao.parecido,
            codigo_testes,
            historico,
        )

    def _fluxo_reaproveitamento(
        self,
        ficha: Ficha,
        pasta_existente: Path,
        codigo_testes: str,
        historico: list[str],
    ) -> ResultadoFase1:
        """Reconfigura um script já aprovado, testa e grava na biblioteca se passar."""
        pasta_tentativa = self._nova_pasta_tentativa(1)
        caminho_script = pasta_tentativa / "script.py"
        caminho_testes = pasta_tentativa / "test_script.py"

        script_reconfigurado = configurar(ficha, pasta_existente)
        caminho_script.write_text(script_reconfigurado, encoding="utf-8")
        caminho_testes.write_text(codigo_testes, encoding="utf-8")

        if self.modo == "dois_agentes":
            resultado = _chamar_executar_testes(caminho_script, caminho_testes)
            if not resultado.passou:
                aviso = resultado.aviso()
                historico.append(f"Reaproveitamento falhou nos testes: {aviso}")
                return ResultadoFase1(
                    situacao="reprovado",
                    ficha=ficha,
                    script=None,
                    voltas=1,
                    historico=historico,
                )

        script_final = self._gravar_aprovado(ficha, script_reconfigurado, codigo_testes, voltas=1)
        historico.append(f"Reaproveitado com sucesso em {script_final}.")
        return ResultadoFase1(
            situacao="aprovado",
            ficha=ficha,
            script=script_final,
            voltas=1,
            historico=historico,
        )

    def _fluxo_criacao(
        self,
        llm_construtor: LLM,
        ficha: Ficha,
        nome_parecido: str | None,
        codigo_testes: str,
        historico: list[str],
    ) -> ResultadoFase1:
        """Gera um novo script em até max_voltas tentativas validadas pelo Revisor."""
        exemplo = self._carregar_exemplo(nome_parecido)
        descricoes_catalogo = _obter_descricoes_catalogo()
        aviso_anterior: str | None = None

        for volta in range(1, self.max_voltas + 1):
            pasta_tentativa = self._nova_pasta_tentativa(volta)
            caminho_script = pasta_tentativa / "script.py"
            caminho_testes = pasta_tentativa / "test_script.py"
            caminho_testes.write_text(codigo_testes, encoding="utf-8")

            try:
                corpo = _chamar_gerar_corpo(
                    llm_construtor,
                    ficha,
                    descricoes_catalogo,
                    exemplo=exemplo,
                    aviso_anterior=aviso_anterior,
                )
                script_gerado = montar(corpo, ficha)
            except (CodigoRecusado, SyntaxError) as erro:
                aviso_anterior = f"Código recusado na conferência: {erro}"
                historico.append(f"Volta {volta}: {aviso_anterior}")
                continue

            caminho_script.write_text(script_gerado, encoding="utf-8")

            if self.modo == "um_agente":
                script_final = self._gravar_aprovado(ficha, script_gerado, codigo_testes, voltas=volta)
                historico.append(f"Volta {volta}: aprovado em modo um_agente.")
                return ResultadoFase1(
                    situacao="aprovado",
                    ficha=ficha,
                    script=script_final,
                    voltas=volta,
                    historico=historico,
                )

            resultado = _chamar_executar_testes(caminho_script, caminho_testes)
            if resultado.passou:
                script_final = self._gravar_aprovado(ficha, script_gerado, codigo_testes, voltas=volta)
                historico.append(f"Volta {volta}: aprovado nos testes.")
                return ResultadoFase1(
                    situacao="aprovado",
                    ficha=ficha,
                    script=script_final,
                    voltas=volta,
                    historico=historico,
                )

            aviso_anterior = resultado.aviso()
            historico.append(f"Volta {volta}: {aviso_anterior}")

        return ResultadoFase1(
            situacao="reprovado",
            ficha=ficha,
            script=None,
            voltas=self.max_voltas,
            historico=historico,
        )

    def _carregar_exemplo(self, nome_parecido: str | None) -> str | None:
        """Extrai a função executar de um script aprovado parecido, se existir."""
        if not nome_parecido:
            return None
        arquivo = self.pasta_aprovados / nome_parecido / "script.py"
        if not arquivo.is_file():
            return None
        return funcao_de(arquivo.read_text(encoding="utf-8"))

    def _nova_pasta_tentativa(self, volta: int) -> Path:
        """Cria uma subpasta datada em pasta_trabalho para registrar a tentativa."""
        carimbo = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        pasta = self.pasta_trabalho / f"{carimbo}_v{volta}"
        pasta.mkdir(parents=True, exist_ok=True)
        return pasta

    def _ler_indice(self) -> list[dict]:
        """Carrega scripts_aprovados/indice.json se existir."""
        arquivo_indice = self.pasta_aprovados / "indice.json"
        if not arquivo_indice.is_file():
            return []
        return json.loads(arquivo_indice.read_text(encoding="utf-8"))

    def _gravar_aprovado(
        self,
        ficha: Ficha,
        script_texto: str,
        testes_texto: str,
        voltas: int,
    ) -> Path:
        """Salva script.py, test_script.py, ficha.json e atualiza indice.json."""
        self.pasta_aprovados.mkdir(parents=True, exist_ok=True)
        nome = nome_do_script(ficha)
        pasta_destino = self.pasta_aprovados / nome
        pasta_destino.mkdir(parents=True, exist_ok=True)

        caminho_script = pasta_destino / "script.py"
        caminho_script.write_text(script_texto, encoding="utf-8")
        (pasta_destino / "test_script.py").write_text(testes_texto, encoding="utf-8")
        (pasta_destino / "ficha.json").write_text(ficha.para_json(), encoding="utf-8")

        indice = [item for item in self._ler_indice() if item.get("nome") != nome]
        indice.append(
            {
                "nome": nome,
                "acao": ficha.acao,
                "descricao": ficha.pedido,
                "aprovado_em": datetime.now().isoformat(timespec="seconds"),
                "voltas": voltas,
            }
        )
        (self.pasta_aprovados / "indice.json").write_text(
            json.dumps(indice, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return caminho_script
