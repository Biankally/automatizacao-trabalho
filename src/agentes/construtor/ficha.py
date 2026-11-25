from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.agentes.comum.execucao import extrair_json
from src.agentes.comum.llm import LLM, Mensagem
from src.agentes.comum.prompts import carregar
from src.contratos.ficha import Ficha, FichaInvalida

if TYPE_CHECKING:
    from src.nucleo.disfarce import RaioX

MAX_TENTATIVAS_FICHA = 2


def preencher(
    llm: LLM,
    pedido: str,
    raio_x: list[RaioX],
    amostras: list[list[dict]],
) -> Ficha:
    """Preenche e valida uma Ficha a partir do pedido e dos metadados disfarçados.

    Recebe:
        llm: cliente de modelo de linguagem (real ou falso).
        pedido: descrição em linguagem natural da automação desejada.
        raio_x: lista de objetos RaioX das planilhas envolvidas.
        amostras: amostras disfarçadas das planilhas.
    Devolve:
        Uma instância válida de Ficha com confirmada=False.
    Garante:
        Tenta no máximo 2 vezes; na segunda falha lança FichaInvalida.
    """
    texto_raio_x = "\n\n".join(
        rx.para_texto() if hasattr(rx, "para_texto") else str(rx) for rx in raio_x
    )
    texto_amostra = json.dumps(amostras, ensure_ascii=False, indent=2)
    prompt_inicial = carregar(
        "construtor_ficha",
        pedido=pedido,
        raio_x=texto_raio_x,
        amostra=texto_amostra,
    )

    mensagens: list[Mensagem] = [{"role": "user", "content": prompt_inicial}]

    for tentativa in range(MAX_TENTATIVAS_FICHA):
        resposta = llm.conversar(mensagens)
        try:
            dados = extrair_json(resposta)
            dados["pedido"] = pedido
            dados["confirmada"] = False
            ficha = Ficha.de_json(json.dumps(dados, ensure_ascii=False))
            problemas = ficha.problemas()
            if problemas:
                raise FichaInvalida("; ".join(problemas))
            return ficha
        except (ValueError, FichaInvalida) as erro:
            if tentativa == MAX_TENTATIVAS_FICHA - 1:
                raise FichaInvalida(
                    f"Não foi possível gerar uma ficha válida após {MAX_TENTATIVAS_FICHA} "
                    f"tentativas: {erro}"
                ) from erro
            mensagens.append({"role": "assistant", "content": resposta})
            mensagens.append(
                {
                    "role": "user",
                    "content": (
                        f"A resposta anterior contém erro ({erro}). "
                        "Corrija e responda apenas com o JSON válido da ficha."
                    ),
                }
            )

    raise FichaInvalida("Falha inesperada ao preencher a ficha.")


def mostrar(ficha: Ficha) -> str:
    """Formata a ficha em texto legível para a tela de confirmação do usuário.

    Recebe:
        ficha: instância de Ficha a ser apresentada.
    Devolve:
        Texto estruturado com todos os parâmetros e suposições da ficha.
    Garante:
        Não imprime na tela nem modifica a ficha.
    """
    linhas: list[str] = [
        "=== Confirmação da Ficha ===",
        f"Pedido: {ficha.pedido}",
        "Planilhas:",
    ]
    for planilha in ficha.planilhas:
        linhas.append(
            f"  - {planilha.rotulo}: {planilha.arquivo} "
            f"(aba '{planilha.aba}', cabeçalho linha {planilha.linha_cabecalho})"
        )

    linhas.append(
        f"Chave: origem='{ficha.chave.get('origem', '')}' -> "
        f"destino='{ficha.chave.get('destino', '')}'"
    )
    linhas.append(f"Ação: {ficha.acao}")
    linhas.append("Colunas:")
    for col_origem, col_destino in ficha.colunas.items():
        linhas.append(f"  - {col_origem} -> {col_destino}")

    casos = ficha.casos_problema
    linhas.append(
        "Casos-problema: "
        f"chave_repetida={casos.chave_repetida}, "
        f"ignorar_acento_e_caixa={casos.ignorar_acento_e_caixa}, "
        f"zeros_na_chave={casos.zeros_na_chave}"
    )
    linhas.append(f"Saída: {ficha.saida}")

    if ficha.suposicoes:
        linhas.append("Suposições:")
        for suposicao in ficha.suposicoes:
            linhas.append(f"  - {suposicao}")

    problemas = ficha.problemas()
    if problemas:
        linhas.append("Pendências a corrigir:")
        for problema in problemas:
            linhas.append(f"  ! {problema}")

    return "\n".join(linhas)
