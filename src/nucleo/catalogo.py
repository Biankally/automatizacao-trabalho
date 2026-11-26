"""Catalogo: as 6 funcoes que o LLM pode combinar para montar um script.

Cada funcao e registrada com uso, retorno e exemplo. Essas descricoes formam a
"aula" que o Construtor manda ao LLM. O LLM escreve so a funcao executar(config),
chamando estas funcoes na ordem: ler_planilha, iniciar, casar_por_chave,
completar_coluna ou trocar_coluna, finalizar.

Camada 5: usa so o nucleo e a biblioteca padrao. Especificacao: docs/estrutura.md, secao 4.3.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from src.nucleo import nucleo as N

_FUNCOES: dict[str, Callable] = {}
_DESCRICOES: list["DescricaoDeFuncao"] = []


@dataclass(frozen=True)
class DescricaoDeFuncao:
    """Como uma funcao do catalogo e apresentada ao LLM."""

    nome: str
    assinatura: str
    uso: str
    retorna: str
    exemplo: str

    def linha_da_aula(self) -> str:
        """Devolve o trecho da aula sobre esta funcao (assinatura, uso, retorno e exemplo)."""
        return (f"- {self.assinatura}\n  Uso: {self.uso}\n  Retorna: {self.retorna}\n"
                f"  Exemplo: {self.exemplo}")


def registrar(uso: str, retorna: str, exemplo: str) -> Callable[[Callable], Callable]:
    """Decorador que coloca uma funcao no catalogo.

    Recebe: o uso, o que ela retorna e um exemplo de chamada.
    Devolve: o decorador; a funcao decorada continua igual.
    Garante: a ordem das descricoes e a ordem em que as funcoes aparecem neste arquivo.
    """
    def decorar(f: Callable) -> Callable:
        assinatura = f"{f.__name__}({', '.join(inspect.signature(f).parameters)})"
        _FUNCOES[f.__name__] = f
        _DESCRICOES.append(DescricaoDeFuncao(f.__name__, assinatura, uso, retorna, exemplo))
        return f
    return decorar


def funcoes() -> dict[str, Callable]:
    """Devolve uma copia de {nome: funcao}: o que o script gerado pode chamar."""
    return dict(_FUNCOES)


def descricoes() -> list[DescricaoDeFuncao]:
    """Devolve uma copia das descricoes, na ordem de uso."""
    return list(_DESCRICOES)


@dataclass
class Pares:
    """As linhas do destino que acharam par na origem, mais o que e preciso para altera-las."""

    origem: N.Tabela
    destino: N.Tabela
    indice_origem: dict
    casados: list = field(default_factory=list)      # (linha_destino, chave)
    casos_problema: dict = field(default_factory=dict)
    opcoes: N.Opcoes = field(default_factory=N.Opcoes)


@dataclass
class Resumo:
    """O que o script mostra na tela no final."""

    ok: bool
    saida: str
    relatorio: str
    alteradas: int
    pendencias: int

    def __str__(self) -> str:
        """Texto curto: PODE USAR ou NAO USE, o arquivo, o relatorio e os numeros."""
        estado = "PODE USAR" if self.ok else "NAO USE"
        return (f"{estado}: {self.saida}\nRelatorio: {self.relatorio}\n"
                f"Celulas alteradas: {self.alteradas} | Pendencias: {self.pendencias}")


def _opcoes(casos_problema: dict) -> N.Opcoes:
    """Traduz os casos-problema da ficha para as Opcoes do nucleo."""
    ignorar = bool(casos_problema.get("ignorar_acento_e_caixa", False))
    zeros = 20 if casos_problema.get("zeros_na_chave") else 0
    return N.Opcoes(ignorar_acento=ignorar, ignorar_caixa=ignorar, zeros_chave=zeros)


@registrar("Le uma aba de uma planilha.", "Tabela",
           'origem = ler_planilha("origem", p["origem"]["arquivo"], p["origem"]["aba"], '
           'p["origem"]["linha_cabecalho"])')
def ler_planilha(rotulo: str, arquivo: str, aba: str, linha_cabecalho: int) -> N.Tabela:
    """Le uma aba.

    Recebe: o rotulo ("origem" ou "destino"), o arquivo, a aba e a linha do cabecalho.
    Devolve: a Tabela, com o rotulo em maiusculas.
    Garante: arquivo, aba ou cabecalho com problema levantam ErroConfiguracao.
    """
    return N.ler_aba(rotulo.upper(), str(arquivo), aba, linha_cabecalho)


@registrar("Cria o registro de achados para as duas tabelas.", "Registro",
           'registro = iniciar("completar_email", origem, destino)')
def iniciar(ferramenta: str, origem: N.Tabela, destino: N.Tabela) -> N.Registro:
    """Cria o registro que vai anotar cada decisao.

    Recebe: um nome curto para a ferramenta e as duas tabelas.
    Devolve: o Registro.
    Garante: toda linha lida das duas tabelas passa a exigir um desfecho.
    """
    registro = N.Registro(ferramenta)
    registro.esperar(origem)
    registro.esperar(destino)
    return registro


@registrar("Casa as linhas da origem e do destino pela coluna-chave.", "Pares",
           'pares = casar_por_chave(registro, origem, config["chave"]["origem"], destino, '
           'config["chave"]["destino"], config["casos_problema"])')
def casar_por_chave(registro: N.Registro, origem: N.Tabela, coluna_origem: str,
                    destino: N.Tabela, coluna_destino: str, casos_problema: dict) -> Pares:
    """Liga cada linha do destino a linha da origem com a mesma chave.

    Recebe: o registro, as tabelas, as colunas-chave e os casos-problema da ficha.
    Devolve: os Pares (linhas casadas).
    Garante: comparacao exata depois de padronizar(); linhas sem chave e sem par viram
             achados; toda linha da origem recebe desfecho aqui.
    """
    op = _opcoes(casos_problema)
    origem.exigir([coluna_origem])
    destino.exigir([coluna_destino])
    idx_o, sem_o = N.indexar(origem, [coluna_origem], op)
    idx_d, sem_d = N.indexar(destino, [coluna_destino], op)
    for linha in sem_o:
        registro.desfecho(origem.rotulo, linha.n, "sem chave")
    for chave, linhas in idx_o.items():
        for linha in linhas:
            registro.desfecho(origem.rotulo, linha.n, "usada" if chave in idx_d else "so na origem")
    pares = Pares(origem, destino, idx_o, casos_problema=dict(casos_problema), opcoes=op)
    for linha in sem_d:
        registro.desfecho(destino.rotulo, linha.n, "sem chave")
        registro.achar(planilha=destino.rotulo, linha=linha.n, chave="", coluna=coluna_destino,
                       valor=None, referencia="", situacao="vazio", regra="chave.vazia",
                       severidade="AVISO", decisao="pendente", mensagem="Linha sem chave")
    for chave, linhas in idx_d.items():
        for linha in linhas:
            if chave not in idx_o:
                registro.desfecho(destino.rotulo, linha.n, "sem par na origem")
                registro.achar(planilha=destino.rotulo, linha=linha.n, chave=chave, coluna="",
                               valor=None, referencia=origem.rotulo, situacao="sem_par",
                               regra="chave.sem_par", severidade="AVISO",
                               mensagem="Chave nao existe na origem")
            else:
                pares.casados.append((linha, chave))
    return pares


def _alterar(registro: N.Registro, pares: Pares, coluna_origem: str, coluna_destino: str,
             trocar: bool) -> None:
    """Julga cada par: igual, completar, trocar ou pendencia. So anota; quem escreve e o finalizar."""
    pares.origem.exigir([coluna_origem])
    pares.destino.exigir([coluna_destino])
    op = pares.opcoes
    for linha, chave in pares.casados:
        fontes = [x for x in pares.indice_origem[chave] if not N.vazio(x.valores.get(coluna_origem))]
        atual = linha.valores.get(coluna_destino)
        base = dict(planilha=pares.destino.rotulo, linha=linha.n, chave=chave, coluna=coluna_destino,
                    valor=atual, referencia="ORIGEM")
        if not fontes:
            continue
        distintos = {N.padronizar(x.valores[coluna_origem], op) for x in fontes}
        if len(distintos) > 1 and pares.casos_problema.get("chave_repetida", "nao_alterar") == "nao_alterar":
            registro.achar(**base, situacao="chave_repetida", regra="origem.valores_diferentes",
                           severidade="ERRO", decisao="pendente", mensagem="Valores diferentes na origem")
            continue
        novo = fontes[0].valores[coluna_origem]
        if N.padronizar(atual, op) == N.padronizar(novo, op):
            registro.igual(coluna_destino)
            continue
        if (linha.n, pares.destino.colunas[coluna_destino]) in pares.destino.formulas:
            registro.achar(**base, situacao="protegido", regra="destino.formula", severidade="AVISO",
                           decisao="pendente", valor_novo=novo, mensagem="Celula com formula")
        elif N.vazio(atual):
            registro.achar(**base, situacao="vazio", regra="completar.vazio", severidade="INFO",
                           acao="completar", valor_novo=novo, aplicado=True, mensagem="Completado")
        elif trocar:
            registro.achar(**base, situacao="diferente", regra="trocar.diferente", severidade="INFO",
                           acao="trocar", valor_novo=novo, aplicado=True, mensagem="Trocado")
        else:
            registro.achar(**base, situacao="diferente", regra="completar.ja_preenchido",
                           severidade="AVISO", decisao="pendente", valor_novo=novo,
                           mensagem="Ja preenchido com valor diferente")


@registrar("Preenche so as celulas vazias do destino com o valor da origem.", "None",
           'completar_coluna(registro, pares, "E-mail", "E-mail")')
def completar_coluna(registro: N.Registro, pares: Pares, coluna_origem: str,
                     coluna_destino: str) -> None:
    """Completa so o que esta vazio.

    Recebe: o registro, os pares e as colunas (origem -> destino).
    Devolve: nada; anota os achados no registro.
    Garante: celula ja preenchida com outro valor vira pendencia, nunca e sobrescrita;
             celula com formula nunca e alterada.
    """
    _alterar(registro, pares, coluna_origem, coluna_destino, trocar=False)


@registrar("Troca o valor do destino quando difere do da origem.", "None",
           'trocar_coluna(registro, pares, "E-mail", "E-mail")')
def trocar_coluna(registro: N.Registro, pares: Pares, coluna_origem: str,
                  coluna_destino: str) -> None:
    """Completa o vazio e troca o diferente.

    Recebe: o registro, os pares e as colunas (origem -> destino).
    Devolve: nada; anota os achados no registro.
    Garante: celula com formula nunca e alterada; chave repetida com valores diferentes
             vira pendencia (a menos que casos_problema diga "primeiro").
    """
    _alterar(registro, pares, coluna_origem, coluna_destino, trocar=True)


@registrar("Grava a saida, roda todas as conferencias e o relatorio.", "Resumo",
           'return finalizar(registro, pares, config["saida"], config["relatorio"])')
def finalizar(registro: N.Registro, pares: Pares, saida: str, relatorio: str) -> Resumo:
    """Fecha o trabalho: da desfecho as linhas casadas, grava, confere e relata.

    Recebe: o registro, os pares e os caminhos da saida e do relatorio.
    Devolve: o Resumo (ok, arquivo final, relatorio, celulas alteradas, pendencias).
    Garante: as garantias do nucleo (completude, exatidao, rastro, original intocado);
             se alguma falhar, a saida sai como NAO_USE_<nome>.
    """
    for linha, _chave in pares.casados:
        meus = [a for a in registro.achados if a.planilha == pares.destino.rotulo and a.linha == linha.n]
        mudou = any(a.aplicado for a in meus)
        pendente = any(a.decisao == "pendente" for a in meus)
        registro.desfecho(pares.destino.rotulo, linha.n,
                          "alterada" if mudou else "com pendencia" if pendente else "sem mudanca")
    copia = N.CopiaSegura(pares.destino)
    for achado in registro.aplicados():
        copia.aplicar(achado)
    Path(saida).parent.mkdir(parents=True, exist_ok=True)
    Path(relatorio).parent.mkdir(parents=True, exist_ok=True)
    ok, final = N.finalizar(registro, copia, str(saida), str(relatorio),
                            [("Ferramenta", registro.ferramenta)])
    return Resumo(ok, final, str(relatorio), len(copia.alteradas), len(registro.pendentes()))
