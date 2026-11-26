"""Testes do nucleo (src/nucleo/nucleo.py): padronizar, ler, casar e as conferencias.

Toda conferencia tem um teste de sabotagem: o resultado e estragado de proposito
e a conferencia precisa acusar. Planilhas so em tmp_path, com valores inventados.
"""

import datetime as dt

import pytest
from openpyxl import Workbook, load_workbook

from src.nucleo import nucleo as N


def criar_xlsx(caminho, linhas, aba="Plan1"):
    """Grava uma planilha simples: a primeira linha e o cabecalho."""
    wb = Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)
    return str(caminho)


@pytest.fixture
def destino(tmp_path):
    return criar_xlsx(tmp_path / "destino.xlsx", [
        ["Matricula", "Email"],
        ["001", None],
        ["002", "b@exemplo.com"],
    ])


# ---------- padronizar e chave_de ----------

@pytest.mark.parametrize("a, b", [
    ("José", "JOSE"),
    ("  ana   maria ", "Ana Maria"),
    ("1234,00", 1234),
    ("2026-09-01", dt.date(2026, 9, 1)),
    ("1/9/2026", "01/09/2026"),
])
def test_padronizar_iguala_formas_diferentes(a, b):
    assert N.padronizar(a) == N.padronizar(b)


@pytest.mark.parametrize("v", [None, "", "   ", "null", "NaN", float("nan")])
def test_vazios_viram_texto_vazio(v):
    assert N.vazio(v)
    assert N.padronizar(v) == ""


def test_chave_com_zeros_a_esquerda():
    linha = N.Linha(2, {"Matricula": "48213"})
    outra = N.Linha(3, {"Matricula": "0048213"})
    op = N.Opcoes(zeros_chave=20)
    assert N.chave_de(linha, ["Matricula"], op) == N.chave_de(outra, ["Matricula"], op)
    assert N.chave_de(linha, ["Matricula"]) != N.chave_de(outra, ["Matricula"])


def test_chave_composta_com_parte_vazia_e_vazia():
    linha = N.Linha(2, {"A": "x", "B": None})
    assert N.chave_de(linha, ["A", "B"]) == ""


# ---------- ler_aba ----------

def test_ler_aba_guarda_linhas_e_pula_vazias(tmp_path):
    arq = criar_xlsx(tmp_path / "t.xlsx", [["Nome"], ["a"], [None], ["b"]])
    t = N.ler_aba("ORIGEM", arq, "Plan1")
    assert [l.valores["Nome"] for l in t.linhas] == ["a", "b"]
    assert t.linhas_vazias == 1
    assert t.colunas == {"Nome": 1}


def test_ler_aba_marca_formulas(tmp_path):
    arq = criar_xlsx(tmp_path / "t.xlsx", [["A", "B"], [1, "=A2*2"]])
    t = N.ler_aba("DESTINO", arq, "Plan1")
    assert (2, 2) in t.formulas


def test_ler_aba_erros_de_configuracao(tmp_path):
    with pytest.raises(N.ErroConfiguracao):
        N.ler_aba("X", str(tmp_path / "nao_existe.xlsx"), "Plan1")
    arq = criar_xlsx(tmp_path / "t.xlsx", [["A", "A"], [1, 2]])
    with pytest.raises(N.ErroConfiguracao):
        N.ler_aba("X", arq, "Plan1")                  # cabecalho repetido
    with pytest.raises(N.ErroConfiguracao):
        N.ler_aba("X", arq, "Outra")                  # aba que nao existe


def test_exigir_coluna_inexistente(destino):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    with pytest.raises(N.ErroConfiguracao):
        t.exigir(["Telefone"])


# ---------- indexar ----------

def test_indexar_separa_linhas_sem_chave(tmp_path):
    arq = criar_xlsx(tmp_path / "t.xlsx", [["K", "V"], ["1", "a"], [None, "b"], ["1", "c"]])
    t = N.ler_aba("ORIGEM", arq, "Plan1")
    indice, sem = N.indexar(t, ["K"])
    assert len(indice["1"]) == 2
    assert [l.valores["V"] for l in sem] == ["b"]


# ---------- Achado ----------

def test_achado_recusa_situacao_desconhecida():
    with pytest.raises(N.ErroProcesso):
        N.Achado("DESTINO", 2, "1", "Email", None, "", "inventada", "r", "INFO", "m")


def test_achado_pendente_nao_pode_estar_aplicado():
    with pytest.raises(N.ErroProcesso):
        N.Achado("DESTINO", 2, "1", "Email", None, "", "vazio", "r", "INFO", "m",
                 acao="completar", aplicado=True, decisao="pendente")


# ---------- caminho completo e conferencias ----------

def _rodar_um_completar(destino_arq, saida, relatorio):
    """Completa o e-mail da linha 2 e finaliza; devolve (ok, final, reg, copia)."""
    t = N.ler_aba("DESTINO", destino_arq, "Plan1")
    reg = N.Registro("teste")
    reg.esperar(t)
    reg.achar(planilha="DESTINO", linha=2, chave="001", coluna="Email", valor=None, referencia="ORIGEM",
              situacao="vazio", regra="completar.vazio", severidade="INFO", mensagem="Completado",
              acao="completar", valor_novo="a@exemplo.com", aplicado=True)
    reg.desfecho("DESTINO", 2, "alterada")
    reg.desfecho("DESTINO", 3, "sem mudanca")
    copia = N.CopiaSegura(t)
    copia.aplicar(reg.aplicados()[0])
    ok, final = N.finalizar(reg, copia, str(saida), str(relatorio), [])
    return ok, final, reg, copia


def test_finalizar_caminho_feliz(destino, tmp_path):
    saida, rel = tmp_path / "saida.xlsx", tmp_path / "rel.xlsx"
    antes = N._hash(destino)
    ok, final, _, _ = _rodar_um_completar(destino, saida, rel)
    assert ok and final == str(saida)
    assert load_workbook(final)["Plan1"]["B2"].value == "a@exemplo.com"
    assert N._hash(destino) == antes                       # original intocado
    assert "Achados" in load_workbook(rel).sheetnames


def test_finalizar_nao_usa_print(destino, tmp_path, capsys):
    _rodar_um_completar(destino, tmp_path / "s.xlsx", tmp_path / "r.xlsx")
    assert capsys.readouterr().out == ""


def test_saida_nao_pode_ser_o_proprio_destino(destino, tmp_path):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    with pytest.raises(N.ErroConfiguracao):
        N.finalizar(reg, N.CopiaSegura(t), destino, str(tmp_path / "r.xlsx"), [])


def test_nao_escreve_sobre_formula(tmp_path):
    arq = criar_xlsx(tmp_path / "f.xlsx", [["A", "B"], [1, "=A2*2"]])
    t = N.ler_aba("DESTINO", arq, "Plan1")
    a = N.Achado("DESTINO", 2, "1", "B", 2, "", "diferente", "r", "INFO", "m",
                 acao="trocar", valor_novo=5, aplicado=True)
    with pytest.raises(N.ErroProcesso):
        N.CopiaSegura(t).aplicar(a)


# ---------- sabotagens: cada conferencia precisa acusar ----------

def test_sabotagem_completude_linha_sem_desfecho(destino):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    reg.esperar(t)
    reg.desfecho("DESTINO", 2, "sem mudanca")              # a linha 3 ficou sem desfecho
    assert not N.conferir_completude(reg).ok


def test_sabotagem_completude_desfecho_duplo(destino):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    reg.esperar(t)
    for n in (2, 3):
        reg.desfecho("DESTINO", n, "sem mudanca")
    reg.desfecho("DESTINO", 2, "alterada")                 # contou duas vezes
    assert not N.conferir_completude(reg).ok


def test_sabotagem_exatidao_celula_mudou_sem_achado(destino, tmp_path):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    estragada = tmp_path / "estragada.xlsx"
    wb = load_workbook(destino)
    wb["Plan1"]["B3"] = "mexeram@exemplo.com"
    wb.save(estragada)
    assert not N.conferir_exatidao(t, str(estragada), {}).ok


def test_sabotagem_exatidao_valor_errado(destino, tmp_path):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    estragada = tmp_path / "estragada.xlsx"
    wb = load_workbook(destino)
    wb["Plan1"]["B2"] = "errado@exemplo.com"
    wb.save(estragada)
    assert not N.conferir_exatidao(t, str(estragada), {(2, 2): "a@exemplo.com"}).ok


def test_sabotagem_rastro_alteracao_sem_achado(destino):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    assert not N.conferir_rastro(reg, {(3, 2): "x"}, t).ok


def test_sabotagem_rastro_achado_sem_alteracao(destino):
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    reg.achar(planilha="DESTINO", linha=2, chave="001", coluna="Email", valor=None, referencia="",
              situacao="vazio", regra="r", severidade="INFO", mensagem="m",
              acao="completar", valor_novo="a", aplicado=True)
    assert not N.conferir_rastro(reg, {}, t).ok


def test_sabotagem_conferencia_falha_gera_nao_use(destino, tmp_path):
    """Uma prova extra que falha faz a saida sair como NAO_USE_."""
    t = N.ler_aba("DESTINO", destino, "Plan1")
    reg = N.Registro("teste")
    reg.esperar(t)
    for n in (2, 3):
        reg.desfecho("DESTINO", n, "sem mudanca")

    def prova_que_falha(_caminho):
        return N.Conferencia("prova sabotada", False, "estragada de proposito")

    ok, final = N.finalizar(reg, N.CopiaSegura(t), str(tmp_path / "s.xlsx"), str(tmp_path / "r.xlsx"),
                            [], [prova_que_falha])
    assert not ok
    assert final.endswith("NAO_USE_s.xlsx")
    assert not (tmp_path / "s.xlsx").exists()
