"""Testes da busca e decisão de reaproveitamento (src/agentes/construtor/busca.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.agentes.comum.llm import LLMFalso
from src.agentes.construtor.busca import Decisao, decidir


@dataclass
class _RaioXFalso:
    texto: str

    def para_texto(self) -> str:
        return self.texto


def _indice_exemplo() -> list[dict]:
    return [
        {
            "nome": "alterar_coluna",
            "acao": "completar",
            "descricao": "Completar email do cadastro com dados do RH",
            "aprovado_em": "2026-11-20T10:00:00",
            "voltas": 1,
        },
        {
            "nome": "trocar_telefone_por_cpf",
            "acao": "trocar",
            "descricao": "Atualizar telefone de clientes pelo CPF",
            "aprovado_em": "2026-11-21T14:30:00",
            "voltas": 1,
        },
    ]


def test_decidir_reaproveita_script_presente_no_indice() -> None:
    # prepara
    resposta = (
        "Analisando o catálogo:\n"
        "```json\n"
        '{"reaproveitar": "alterar_coluna", "parecido": null, '
        '"motivo": "Mesma operação de completar coluna por chave."}\n'
        "```"
    )
    llm = LLMFalso([resposta])
    raio_x = [_RaioXFalso("Planilha origem.xlsx: Matricula, Email")]
    indice = _indice_exemplo()

    # age
    decisao = decidir(
        llm,
        "Completar email do cadastro usando RH",
        raio_x,  # type: ignore[arg-type]
        indice,
    )

    # confere
    assert isinstance(decisao, Decisao)
    assert decisao.reaproveitar == "alterar_coluna"
    assert decisao.parecido is None
    assert "Mesma operação" in decisao.motivo
    assert len(llm.recebido) == 1
    prompt_enviado = llm.recebido[0][-1]["content"]
    assert "Completar email do cadastro usando RH" in prompt_enviado
    assert "Planilha origem.xlsx" in prompt_enviado
    assert "trocar_telefone_por_cpf" in prompt_enviado


def test_decidir_indica_script_parecido_como_exemplo() -> None:
    # prepara
    resposta = json.dumps(
        {
            "reaproveitar": None,
            "parecido": "trocar_telefone_por_cpf",
            "motivo": "Estrutura semelhante de atualização por chave.",
        },
        ensure_ascii=False,
    )
    llm = LLMFalso([resposta])
    raio_x = [_RaioXFalso("Planilha clientes.xlsx: CPF, Endereco")]

    # age
    decisao = decidir(
        llm,
        "Trocar endereço pelo CPF",
        raio_x,  # type: ignore[arg-type]
        _indice_exemplo(),
    )

    # confere
    assert decisao.reaproveitar is None
    assert decisao.parecido == "trocar_telefone_por_cpf"
    assert "semelhante" in decisao.motivo


def test_decidir_nome_inventado_vira_none() -> None:
    # prepara
    resposta = json.dumps(
        {
            "reaproveitar": "script_fantasma_nao_existe",
            "parecido": "outro_script_inventado",
            "motivo": "Tentativa de inventar nome.",
        },
        ensure_ascii=False,
    )
    llm = LLMFalso([resposta])
    raio_x = [_RaioXFalso("Raio-X simples")]

    # age
    decisao = decidir(
        llm,
        "Pedido qualquer",
        raio_x,  # type: ignore[arg-type]
        _indice_exemplo(),
    )

    # confere
    assert decisao.reaproveitar is None
    assert decisao.parecido is None
    assert decisao.motivo == "Tentativa de inventar nome."
