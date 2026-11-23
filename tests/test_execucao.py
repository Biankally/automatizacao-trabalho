"""Testes do módulo de extração e conferência de código/JSON (src/agentes/comum/execucao.py)."""

from __future__ import annotations

import pytest

from src.agentes.comum.execucao import (
    CodigoRecusado,
    conferir_codigo,
    extrair_codigo,
    extrair_json,
)


def test_extrair_codigo_bloco_unico_com_texto_ao_redor() -> None:
    # prepara
    resposta = (
        "Aqui está a solução solicitada:\n"
        "```python\n"
        "def executar(config):\n"
        "    return 42\n"
        "```\n"
        "Qualquer dúvida, avise."
    )

    # age
    codigo = extrair_codigo(resposta)

    # confere
    assert codigo == "def executar(config):\n    return 42"


def test_extrair_codigo_sem_bloco_ou_com_varios_lanca_recusado() -> None:
    # prepara
    sem_bloco = "def executar(config):\n    return 1"
    dois_blocos = "```python\nx = 1\n```\ntexto\n```python\ny = 2\n```"

    # age e confere
    with pytest.raises(CodigoRecusado):
        extrair_codigo(sem_bloco)
    with pytest.raises(CodigoRecusado):
        extrair_codigo(dois_blocos)


def test_conferir_codigo_aceita_funcao_valida_sem_print() -> None:
    # prepara
    codigo = (
        "def executar(config):\n"
        "    dados = ler_planilha('origem', config['arquivo'], 'Plan1', 1)\n"
        "    return len(dados)\n"
    )

    # age
    problemas = conferir_codigo(codigo, {"ler_planilha"}, exigir_funcoes=("executar",))

    # confere
    assert problemas == []


def test_conferir_codigo_recusa_quando_falta_funcao_exigida() -> None:
    # prepara
    codigo = "def auxiliar(x):\n    return x + 1\n"

    # age
    problemas = conferir_codigo(codigo, set(), exigir_funcoes=("executar",))

    # confere
    assert any("executar" in p for p in problemas)


@pytest.mark.parametrize(
    "trecho_proibido",
    [
        "import os\ndef executar(c):\n    return 1\n",
        "from pathlib import Path\ndef executar(c):\n    return 1\n",
        "def executar(c):\n    return open('a.txt')\n",
        "def executar(c):\n    return eval('1+1')\n",
        "def executar(c):\n    return c.__class__\n",
        "def executar(c):\n    return '{}'.format(c)\n",
        "def executar(c):\n    return c.gi_frame\n",
        "def executar(c):\n    return funcao_desconhecida(c)\n",
    ],
)
def test_conferir_codigo_recusa_construcoes_perigosas_e_fora_do_catalogo(
    trecho_proibido: str,
) -> None:
    # age
    problemas = conferir_codigo(trecho_proibido, {"ler_planilha"}, exigir_funcoes=("executar",))

    # confere
    assert problemas != []


def test_extrair_json_aceita_resposta_limpa_e_suja() -> None:
    # prepara
    limpo = '{"reaproveitar": null, "parecido": "alterar_coluna", "motivo": "similar"}'
    sujo = (
        "Claro! Segue a análise do pedido {com chaves no texto}:\n"
        "```json\n"
        '{\n  "acao": "completar",\n  "chave": {"origem": "ID", "destino": "ID"}\n}\n'
        "```\n"
        "Fim da resposta."
    )

    # age
    dados_limpos = extrair_json(limpo)
    dados_sujos = extrair_json(sujo)

    # confere
    assert dados_limpos == {
        "reaproveitar": None,
        "parecido": "alterar_coluna",
        "motivo": "similar",
    }
    assert dados_sujos == {
        "acao": "completar",
        "chave": {"origem": "ID", "destino": "ID"},
    }


@pytest.mark.parametrize(
    "texto_invalido",
    [
        "",
        "Resposta apenas em texto comum, sem estrutura.",
        '```json\n{"chave_sem_fechar": 123\n```',
        "[1, 2, 3]",
    ],
)
def test_extrair_json_sem_dicionario_valido_lanca_value_error(texto_invalido: str) -> None:
    # age e confere
    with pytest.raises(ValueError):
        extrair_json(texto_invalido)
