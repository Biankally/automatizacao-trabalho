from __future__ import annotations

from dataclasses import dataclass
import json
from typing import TYPE_CHECKING

from src.agentes.comum.execucao import extrair_json
from src.agentes.comum.llm import LLM, Mensagem
from src.agentes.comum.prompts import carregar

if TYPE_CHECKING:
    from src.nucleo.disfarce import RaioX


@dataclass
class Decisao:
    """Resultado da análise de reaproveitamento sobre a biblioteca de scripts aprovados."""

    reaproveitar: str | None
    parecido: str | None
    motivo: str


def decidir(
    llm: LLM,
    pedido: str,
    raio_x: list[RaioX],
    indice: list[dict],
) -> Decisao:
    """Decide se um script aprovado atende ao pedido ou serve como exemplo.

    Recebe:
        llm: cliente de modelo de linguagem (real ou falso).
        pedido: descrição em linguagem natural da automação desejada.
        raio_x: lista de metadados estruturais (RaioX) das planilhas.
        indice: entradas carregadas de scripts_aprovados/indice.json.
    Devolve:
        Decisao indicando o script a reaproveitar, um parecido para exemplo ou None.
    Garante:
        Nunca devolve um nome de script que não esteja presente no índice.
    """
    texto_raio_x = "\n\n".join(
        rx.para_texto() if hasattr(rx, "para_texto") else str(rx) for rx in raio_x
    )
    texto_indice = json.dumps(indice, ensure_ascii=False, indent=2)
    prompt = carregar(
        "construtor_busca",
        pedido=pedido,
        raio_x=texto_raio_x,
        indice=texto_indice,
    )

    mensagens: list[Mensagem] = [{"role": "user", "content": prompt}]
    resposta = llm.conversar(mensagens)
    dados = extrair_json(resposta)

    nomes_validos = {
        str(item["nome"])
        for item in indice
        if isinstance(item, dict) and isinstance(item.get("nome"), str) and item["nome"]
    }

    bruto_reaproveitar = dados.get("reaproveitar")
    bruto_parecido = dados.get("parecido")
    motivo = str(dados.get("motivo") or "").strip()

    reaproveitar = (
        bruto_reaproveitar
        if isinstance(bruto_reaproveitar, str) and bruto_reaproveitar in nomes_validos
        else None
    )
    parecido = (
        bruto_parecido
        if isinstance(bruto_parecido, str) and bruto_parecido in nomes_validos
        else None
    )

    return Decisao(
        reaproveitar=reaproveitar,
        parecido=parecido,
        motivo=motivo,
    )
