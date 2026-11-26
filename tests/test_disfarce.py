"""Testes do disfarce (src/nucleo/disfarce.py): o LLM ve o formato, nunca os valores.

A planilha tem valores conhecidos; nenhum deles pode aparecer no texto do raio-x
nem na amostra disfarcada.
"""

import datetime as dt

import pytest
from openpyxl import Workbook

from src.nucleo import disfarce as D

VALORES_REAIS = ["Maria Silva", "maria.silva@exemplo.com", "0048213", "61999998888", "Brasilia"]


@pytest.fixture
def planilha(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan1"
    ws.append(["Nome", "Email", "Matricula", "Telefone", "Cidade", "Nascimento", "Obs"])
    ws.append(["Maria Silva", "maria.silva@exemplo.com", "0048213", "61999998888", "Brasilia",
               dt.datetime(1990, 5, 17), None])
    ws.append(["Maria Silva", "maria.silva@exemplo.com", "0048213", "61999998888", "Brasilia",
               dt.datetime(1990, 5, 17), None])
    caminho = tmp_path / "pessoas.xlsx"
    wb.save(caminho)
    return str(caminho)


def test_raio_x_descreve_formato(planilha):
    rx = D.raio_x(planilha, "Plan1")
    assert rx.total_linhas == 2
    assert [c.nome for c in rx.colunas] == ["Nome", "Email", "Matricula", "Telefone", "Cidade",
                                             "Nascimento", "Obs"]
    tipos = {c.nome: c.tipo for c in rx.colunas}
    assert tipos["Nascimento"] == "data" and tipos["Obs"] == "vazio" and tipos["Nome"] == "texto"
    assert {c.nome: c.pct_vazios for c in rx.colunas}["Obs"] == 100


def test_raio_x_texto_nao_vaza_valores(planilha):
    texto = D.raio_x(planilha, "Plan1").para_texto()
    for v in VALORES_REAIS + ["1990-05-17", "17/05/1990"]:
        assert v not in texto


def test_amostra_nao_vaza_valores(planilha):
    amostra = D.amostra_disfarcada(planilha, "Plan1")
    tudo = " ".join(str(v) for linha in amostra for v in linha.values())
    for v in VALORES_REAIS + ["1990-05-17"]:
        assert v not in tudo


def test_amostra_mantem_formato(planilha):
    linha = D.amostra_disfarcada(planilha, "Plan1", n=1)[0]
    assert "@" in linha["Email"] and "." in linha["Email"]
    assert linha["Matricula"].startswith("00") and len(linha["Matricula"]) == 7
    assert linha["Telefone"].isdigit() and len(linha["Telefone"]) == 11
    assert linha["Obs"] == ""


def test_amostra_respeita_n_e_semente(planilha):
    assert len(D.amostra_disfarcada(planilha, "Plan1", n=1)) == 1
    assert D.amostra_disfarcada(planilha, "Plan1", semente=7) == D.amostra_disfarcada(planilha, "Plan1", semente=7)


def test_sabotagem_vazamento_seria_detectado(planilha, monkeypatch):
    """Se o disfarce for desligado, o teste de vazamento precisa pegar."""
    monkeypatch.setattr(D, "_inventar", lambda v, rnd: "" if v is None else str(v))
    texto = D.raio_x(planilha, "Plan1").para_texto()
    assert any(v in texto for v in VALORES_REAIS)
