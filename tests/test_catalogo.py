"""Testes do catalogo (src/nucleo/catalogo.py): as 6 funcoes que o LLM pode combinar.

Cada teste monta um "script" do jeito que o Construtor monta: ler, iniciar, casar,
completar ou trocar, finalizar. Planilhas so em tmp_path, com valores inventados.
"""

import pytest
from openpyxl import Workbook, load_workbook

from src.nucleo import catalogo as C

ORDEM = ["ler_planilha", "iniciar", "casar_por_chave", "completar_coluna", "trocar_coluna", "finalizar"]
CASOS_PADRAO = {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False, "zeros_na_chave": False}


def criar_xlsx(caminho, linhas, aba="Plan1"):
    wb = Workbook()
    ws = wb.active
    ws.title = aba
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)
    return str(caminho)


@pytest.fixture
def arquivos(tmp_path):
    origem = criar_xlsx(tmp_path / "rh.xlsx", [
        ["Matricula", "Email"],
        ["001", "ana@exemplo.com"],
        ["002", "beto@exemplo.com"],
        ["003", "caio@exemplo.com"],
    ])
    destino = criar_xlsx(tmp_path / "cadastro.xlsx", [
        ["Matricula", "Email"],
        ["001", None],                       # vazio: completar
        ["002", "antigo@exemplo.com"],       # diferente: so troca no "trocar"
        ["003", "caio@exemplo.com"],         # igual
        ["009", None],                       # sem par na origem
    ])
    return origem, destino, tmp_path


def rodar(arquivos, acao="completar", casos=None):
    origem_arq, destino_arq, pasta = arquivos
    origem = C.ler_planilha("origem", origem_arq, "Plan1", 1)
    destino = C.ler_planilha("destino", destino_arq, "Plan1", 1)
    registro = C.iniciar("teste", origem, destino)
    pares = C.casar_por_chave(registro, origem, "Matricula", destino, "Matricula", casos or CASOS_PADRAO)
    alterar = C.completar_coluna if acao == "completar" else C.trocar_coluna
    alterar(registro, pares, "Email", "Email")
    return C.finalizar(registro, pares, str(pasta / "saida" / "s.xlsx"),
                       str(pasta / "saida" / "s_RELATORIO.xlsx"))


# ---------- a "aula": o que o LLM recebe ----------

def test_seis_funcoes_na_ordem_de_uso():
    assert [d.nome for d in C.descricoes()] == ORDEM
    assert set(C.funcoes()) == set(ORDEM)


def test_cada_descricao_tem_assinatura_uso_e_exemplo():
    for d in C.descricoes():
        texto = d.linha_da_aula()
        assert d.nome in d.assinatura and d.uso and d.exemplo
        assert d.assinatura in texto and d.exemplo in texto


def test_funcoes_devolve_copia():
    C.funcoes().clear()
    assert len(C.funcoes()) == 6


# ---------- completar e trocar ----------

def test_completar_so_preenche_o_vazio(arquivos):
    resumo = rodar(arquivos, "completar")
    ws = load_workbook(resumo.saida)["Plan1"]
    assert resumo.ok
    assert ws["B2"].value == "ana@exemplo.com"
    assert ws["B3"].value == "antigo@exemplo.com"          # ja preenchido: nao muda, vira pendencia
    assert resumo.alteradas == 1
    assert resumo.pendencias == 1


def test_trocar_muda_o_diferente(arquivos):
    resumo = rodar(arquivos, "trocar")
    ws = load_workbook(resumo.saida)["Plan1"]
    assert resumo.ok
    assert ws["B2"].value == "ana@exemplo.com"
    assert ws["B3"].value == "beto@exemplo.com"
    assert resumo.alteradas == 2


def test_original_nao_muda(arquivos):
    _, destino_arq, _ = arquivos
    rodar(arquivos, "trocar")
    ws = load_workbook(destino_arq)["Plan1"]
    assert ws["B2"].value is None and ws["B3"].value == "antigo@exemplo.com"


def test_relatorio_e_criado(arquivos):
    resumo = rodar(arquivos)
    assert "Conferência" in load_workbook(resumo.relatorio).sheetnames


def test_zeros_na_chave(tmp_path):
    origem = criar_xlsx(tmp_path / "o.xlsx", [["Matricula", "Email"], ["48213", "x@exemplo.com"]])
    destino = criar_xlsx(tmp_path / "d.xlsx", [["Matricula", "Email"], ["0048213", None]])
    casos = dict(CASOS_PADRAO, zeros_na_chave=True)
    resumo = rodar((origem, destino, tmp_path), casos=casos)
    assert load_workbook(resumo.saida)["Plan1"]["B2"].value == "x@exemplo.com"
    sem_opcao = rodar((origem, destino, tmp_path), casos=CASOS_PADRAO)
    assert sem_opcao.alteradas == 0                       # sem a opcao, as chaves sao diferentes


def test_chave_repetida_com_valores_diferentes_nao_altera(tmp_path):
    origem = criar_xlsx(tmp_path / "o.xlsx", [["Matricula", "Email"], ["1", "a@exemplo.com"], ["1", "b@exemplo.com"]])
    destino = criar_xlsx(tmp_path / "d.xlsx", [["Matricula", "Email"], ["1", None]])
    resumo = rodar((origem, destino, tmp_path))
    assert resumo.alteradas == 0 and resumo.pendencias == 1
    primeiro = rodar((origem, destino, tmp_path), casos=dict(CASOS_PADRAO, chave_repetida="primeiro"))
    assert load_workbook(primeiro.saida)["Plan1"]["B2"].value == "a@exemplo.com"


def test_formula_no_destino_vira_pendencia(tmp_path):
    origem = criar_xlsx(tmp_path / "o.xlsx", [["Matricula", "Email"], ["1", 99]])
    destino = criar_xlsx(tmp_path / "d.xlsx", [["Matricula", "Email"], ["1", "=1+1"]])
    resumo = rodar((origem, destino, tmp_path), "trocar")
    assert resumo.ok and resumo.alteradas == 0 and resumo.pendencias == 1


def test_coluna_que_nao_existe_para_tudo(arquivos):
    origem_arq, destino_arq, _ = arquivos
    origem = C.ler_planilha("origem", origem_arq, "Plan1", 1)
    destino = C.ler_planilha("destino", destino_arq, "Plan1", 1)
    registro = C.iniciar("teste", origem, destino)
    with pytest.raises(C.N.ErroConfiguracao):
        C.casar_por_chave(registro, origem, "CPF", destino, "Matricula", CASOS_PADRAO)


# ---------- Resumo ----------

def test_resumo_texto_para_a_tela(arquivos):
    texto = str(rodar(arquivos))
    assert "PODE USAR" in texto and "Pendencias: 1" in texto


def test_sabotagem_resumo_mostra_nao_use():
    r = C.Resumo(ok=False, saida="NAO_USE_s.xlsx", relatorio="r.xlsx", alteradas=0, pendencias=0)
    assert str(r).startswith("NAO USE")


def test_sabotagem_finalizar_acusa_linha_sem_desfecho(arquivos):
    """Se uma linha lida nao recebe desfecho, a saida sai como NAO_USE_."""
    origem_arq, destino_arq, pasta = arquivos
    origem = C.ler_planilha("origem", origem_arq, "Plan1", 1)
    destino = C.ler_planilha("destino", destino_arq, "Plan1", 1)
    registro = C.iniciar("teste", origem, destino)
    pares = C.casar_por_chave(registro, origem, "Matricula", destino, "Matricula", CASOS_PADRAO)
    registro.esperadas["ORIGEM"].add(999)                  # sabotagem: uma linha "fantasma"
    resumo = C.finalizar(registro, pares, str(pasta / "s.xlsx"), str(pasta / "r.xlsx"))
    assert not resumo.ok and "NAO_USE_" in resumo.saida
