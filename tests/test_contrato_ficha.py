"""Testes do contrato da Ficha (src/contratos/ficha.py).

Cada teste prova uma regra da seção 4.2 de docs/estrutura.md.
Escritos ANTES da implementação: rodar antes do ficha.py existir deve falhar.
"""

import json
from dataclasses import replace

import pytest

from src.contratos.ficha import CasosProblema, Ficha, FichaInvalida, PlanilhaDaFicha


@pytest.fixture
def ficha() -> Ficha:
    """Uma ficha válida, igual ao exemplo da seção 4.2."""
    return Ficha(
        pedido="completar o email do cadastro com o do RH, pela matricula",
        planilhas=[
            PlanilhaDaFicha("origem", "rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1", 1),
        ],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(zeros_na_chave=True),
        saida="saida/cadastro_completado.xlsx",
        suposicoes=["0048213 e 48213 sao a mesma pessoa"],
    )


# ---------- problemas(): ficha válida ----------

def test_ficha_valida_nao_tem_problemas(ficha):
    assert ficha.problemas() == []
    assert ficha.perguntas() == []


# ---------- problemas(): cada uma das 6 respostas ----------

def test_planilhas_precisa_de_origem_e_destino(ficha):
    ficha.planilhas = [ficha.planilhas[0]]
    assert any("planilhas" in p for p in ficha.problemas())


def test_planilhas_com_rotulo_errado(ficha):
    ficha.planilhas[1] = replace(ficha.planilhas[1], rotulo="alvo")
    assert any("planilhas" in p for p in ficha.problemas())


def test_planilha_sem_arquivo_ou_aba(ficha):
    ficha.planilhas[0] = replace(ficha.planilhas[0], arquivo="")
    assert any("planilhas" in p for p in ficha.problemas())


def test_chave_precisa_das_duas_colunas(ficha):
    ficha.chave = {"origem": "Matricula"}
    assert any("chave" in p for p in ficha.problemas())


def test_acao_so_completar_ou_trocar(ficha):
    ficha.acao = "apagar"
    assert any("acao" in p for p in ficha.problemas())


def test_colunas_nao_pode_ser_vazia(ficha):
    ficha.colunas = {}
    assert any("colunas" in p for p in ficha.problemas())


def test_chave_do_destino_nao_pode_ser_alterada(ficha):
    ficha.colunas = {"Email": "Matricula"}
    assert any("colunas" in p for p in ficha.problemas())


def test_chave_repetida_so_aceita_os_dois_valores(ficha):
    ficha.casos_problema = CasosProblema(chave_repetida="tanto_faz")
    assert any("chave_repetida" in p for p in ficha.problemas())


def test_saida_obrigatoria(ficha):
    ficha.saida = ""
    assert any("saida" in p for p in ficha.problemas())


def test_cada_problema_vira_uma_pergunta(ficha):
    ficha.acao = "apagar"
    ficha.saida = ""
    assert len(ficha.perguntas()) == len(ficha.problemas()) == 2


# ---------- para_config(): o formato exato que o script recebe ----------

def test_para_config_formato_exato(ficha):
    assert ficha.para_config() == {
        "planilhas": {
            "origem": {"arquivo": "rh.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
            "destino": {"arquivo": "cadastro.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
        },
        "chave": {"origem": "Matricula", "destino": "Matricula"},
        "acao": "completar",
        "colunas": {"Email": "Email"},
        "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False,
                           "zeros_na_chave": True},
        "saida": "saida/cadastro_completado.xlsx",
        "relatorio": "saida/cadastro_completado_RELATORIO.xlsx",
    }


def test_para_config_troca_arquivos_e_saida(ficha):
    cfg = ficha.para_config(arquivos={"origem": "teste/o.xlsx"}, saida="teste/s.xlsx")
    assert cfg["planilhas"]["origem"]["arquivo"] == "teste/o.xlsx"
    assert cfg["planilhas"]["destino"]["arquivo"] == "cadastro.xlsx"    # o que não foi trocado fica
    assert cfg["saida"] == "teste/s.xlsx"
    assert cfg["relatorio"] == "teste/s_RELATORIO.xlsx"


def test_para_config_nao_altera_a_ficha(ficha):
    cfg = ficha.para_config()
    cfg["colunas"]["X"] = "Y"
    assert ficha.colunas == {"Email": "Email"}


# ---------- JSON: ida e volta ----------

def test_json_ida_e_volta(ficha):
    assert Ficha.de_json(ficha.para_json()) == ficha


def test_json_mantem_acentos_legiveis(ficha):
    ficha.pedido = "atualizar endereço"
    assert "endereço" in ficha.para_json()


def test_de_json_campos_opcionais_ausentes(ficha):
    d = json.loads(ficha.para_json())
    for campo in ("pedido", "suposicoes", "confirmada"):
        d.pop(campo)
    f = Ficha.de_json(json.dumps(d))
    assert f.pedido == "" and f.suposicoes == [] and f.confirmada is False


@pytest.mark.parametrize("texto", ["isto não é json", "{}", '{"planilhas": 5}', "[]"])
def test_de_json_invalido_lanca_ficha_invalida(texto):
    with pytest.raises(FichaInvalida):
        Ficha.de_json(texto)


def test_relatorio_mantem_as_barras_do_windows(ficha):
    cfg = ficha.para_config(saida="saida\\cadastro.xlsx")
    assert cfg["relatorio"] == "saida\\cadastro_RELATORIO.xlsx"
