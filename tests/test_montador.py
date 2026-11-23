"""Testes do montador de scripts (src/agentes/construtor/montador.py)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.agentes.construtor.montador import (
    config_da_ficha,
    configurar,
    funcao_de,
    montar,
    nome_do_script,
)
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha


def _ficha_exemplo(
    acao: str = "completar",
    colunas: dict[str, str] | None = None,
    chave: dict[str, str] | None = None,
    saida: str = "saida/cadastro_completado.xlsx",
) -> Ficha:
    return Ficha(
        pedido="Completar email por matrícula",
        planilhas=[
            PlanilhaDaFicha("origem", "dados/rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "dados/cadastro.xlsx", "Plan1", 1),
        ],
        chave=chave or {"origem": "Matricula", "destino": "Matricula"},
        acao=acao,
        colunas=colunas or {"Email": "Email"},
        casos_problema=CasosProblema(
            chave_repetida="nao_alterar",
            ignorar_acento_e_caixa=False,
            zeros_na_chave=True,
        ),
        saida=saida,
    )


def test_config_da_ficha_corresponde_a_para_config() -> None:
    # prepara
    ficha = _ficha_exemplo()

    # age e confere
    assert config_da_ficha(ficha) == ficha.para_config()


def test_montar_gera_script_que_compila_com_config_e_funcao() -> None:
    # prepara
    ficha = _ficha_exemplo()
    funcao = (
        "def executar(config):\n"
        "    return config['acao']\n"
    )

    # age
    script = montar(funcao, ficha)

    # confere
    compile(script, "<script_gerado>", "exec")
    assert "# --- CONFIG (inicio) ---" in script
    assert "# --- CONFIG (fim) ---" in script
    assert "def executar(config):" in script
    assert "'zeros_na_chave': True" in script


def test_configurar_altera_apenas_bloco_config(tmp_path: Path) -> None:
    # prepara
    ficha_original = _ficha_exemplo(saida="saida/primeira.xlsx")
    funcao = (
        "def executar(config):\n"
        "    # comentario preservado\n"
        "    return config['saida']\n"
    )
    script_original = montar(funcao, ficha_original)
    pasta_aprovado = tmp_path / "completar_email_por_matricula"
    pasta_aprovado.mkdir()
    (pasta_aprovado / "script.py").write_text(script_original, encoding="utf-8")

    ficha_nova = _ficha_exemplo(saida="saida/segunda.xlsx")

    # age
    script_reconfigurado = configurar(ficha_nova, pasta_aprovado)

    # confere
    compile(script_reconfigurado, "<script_reconfigurado>", "exec")
    assert "saida/segunda.xlsx" in script_reconfigurado
    assert "saida/primeira.xlsx" not in script_reconfigurado

    inicio_marcador = "# --- CONFIG (inicio) ---"
    fim_marcador = "# --- CONFIG (fim) ---"
    antes_orig, resto_orig = script_original.split(inicio_marcador, 1)
    _, depois_orig = resto_orig.split(fim_marcador, 1)

    antes_novo, resto_novo = script_reconfigurado.split(inicio_marcador, 1)
    _, depois_novo = resto_novo.split(fim_marcador, 1)

    assert antes_novo == antes_orig
    assert depois_novo == depois_orig


def test_funcao_de_extrai_apenas_executar_do_script() -> None:
    # prepara
    ficha = _ficha_exemplo()
    funcao = (
        "def executar(config):\n"
        "    x = 10\n"
        "    return x\n"
    )
    script = montar(funcao, ficha)

    # age
    extraida = funcao_de(script)

    # confere
    assert extraida == funcao.strip()


def test_funcao_de_sem_executar_lanca_value_error() -> None:
    # age e confere
    with pytest.raises(ValueError):
        funcao_de("def outra_funcao():\n    return 1\n")


def test_nome_do_script_normaliza_acentos_e_caracteres_especiais() -> None:
    # prepara
    ficha_padrao = _ficha_exemplo()
    ficha_com_acentos = _ficha_exemplo(
        acao="trocar",
        colunas={"Endereço Completo": "Endereço (Atual)"},
        chave={"origem": "Código-ID", "destino": "Código-ID"},
    )

    # age
    nome_1 = nome_do_script(ficha_padrao)
    nome_2 = nome_do_script(ficha_com_acentos)

    # confere
    assert nome_1 == "completar_email_por_matricula"
    assert re.fullmatch(r"[a-z0-9_]+", nome_1)
    assert re.fullmatch(r"[a-z0-9_]+", nome_2)
    assert "endereco" in nome_2
    assert "codigo" in nome_2
