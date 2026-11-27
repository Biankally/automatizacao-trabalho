"""Testes do kit usado pelos testes gerados (src/agentes/revisor/kit_testes.py).

O núcleo ainda pode não existir, então os scripts usados aqui são "de mentira":
escrevem a saída e o relatório direto com openpyxl, no mesmo formato que o núcleo grava.
"""

import json
from pathlib import Path

import openpyxl
import pytest

from src.agentes.revisor import kit_testes
from src.agentes.revisor.kit_testes import (
    DESCRICAO_KIT, Execucao, ScriptNaoInformado, achados, config_teste, criar_planilha,
    rodar_script, script_sob_teste, valor,
)
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha

# Script de mentira: copia o Email da origem para o destino quando o destino está vazio,
# grava a saída e um relatório com a aba "Achados". Devolve um objeto com ok e saida.
SCRIPT_BOM = '''
from pathlib import Path
from types import SimpleNamespace
import openpyxl

def executar(config):
    p = config["planilhas"]
    o = openpyxl.load_workbook(p["origem"]["arquivo"]).worksheets[0]
    d_livro = openpyxl.load_workbook(p["destino"]["arquivo"])
    d = d_livro.worksheets[0]
    emails = {str(l[0]): l[1] for l in o.iter_rows(min_row=2, values_only=True)}
    rel = openpyxl.Workbook()
    rel.active.title = "Resumo"
    ach = rel.create_sheet("Achados")
    ach.append(["Linha", "Chave", "Situação", "Valor"])
    for r in range(2, d.max_row + 1):
        chave = str(d.cell(r, 1).value)
        if chave not in emails:
            ach.append([r, chave, "sem_par", None])
        elif d.cell(r, 2).value is None:
            d.cell(r, 2).value = emails[chave]
        elif d.cell(r, 2).value != emails[chave]:
            ach.append([r, chave, "diferente", d.cell(r, 2).value])
    Path(config["saida"]).parent.mkdir(parents=True, exist_ok=True)
    d_livro.save(config["saida"])
    rel.save(config["relatorio"])
    return SimpleNamespace(ok=True, saida=config["saida"], relatorio=config["relatorio"])
'''

# Script de mentira que simula uma conferência falhando: a saída vira NAO_USE_.
SCRIPT_BLOQUEADO = '''
from pathlib import Path
from types import SimpleNamespace
import openpyxl

def executar(config):
    saida = Path(config["saida"])
    bloqueada = saida.with_name("NAO_USE_" + saida.name)
    openpyxl.Workbook().save(bloqueada)
    openpyxl.Workbook().save(config["relatorio"])
    return SimpleNamespace(ok=False, saida=str(bloqueada), relatorio=config["relatorio"])
'''


def _ficha_dict() -> dict:
    ficha = Ficha(
        pedido="completar email",
        planilhas=[PlanilhaDaFicha("origem", "rh_real.xlsx", "AbaDaFicha", 3),
                   PlanilhaDaFicha("destino", "cad_real.xlsx", "OutraAba", 2)],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(zeros_na_chave=True),
        saida="saida/real.xlsx",
    )
    return json.loads(ficha.para_json())


def _script(tmp_path: Path, codigo: str, nome: str = "script.py") -> Path:
    caminho = tmp_path / nome
    caminho.write_text(codigo, encoding="utf-8")
    return caminho


def test_criar_planilha_grava_cabecalho_e_linhas(tmp_path):
    caminho = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "a@x.com"], ["2", None]])

    ws = openpyxl.load_workbook(caminho).active
    assert caminho == tmp_path / "o.xlsx"
    assert ws.title == "Plan1"
    assert [[c.value for c in linha] for linha in ws.iter_rows()] == [
        ["Matricula", "Email"], ["1", "a@x.com"], ["2", None]]


def test_criar_planilha_com_outra_aba(tmp_path):
    caminho = criar_planilha(tmp_path, "o.xlsx", ["A"], [], aba="Dados")

    assert openpyxl.load_workbook(caminho).sheetnames == ["Dados"]


def test_config_teste_troca_planilhas_aba_cabecalho_e_saida(tmp_path):
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [], aba="Primeira")
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [])

    config = config_teste(_ficha_dict(), {"origem": o, "destino": d}, tmp_path)

    assert config["planilhas"] == {
        "origem": {"arquivo": str(o), "aba": "Primeira", "linha_cabecalho": 1},
        "destino": {"arquivo": str(d), "aba": "Plan1", "linha_cabecalho": 1},
    }
    assert config["saida"] == str(tmp_path / "saida.xlsx")
    assert config["relatorio"] == str(tmp_path / "saida_RELATORIO.xlsx")
    assert config["chave"] == {"origem": "Matricula", "destino": "Matricula"}
    assert config["casos_problema"]["zeros_na_chave"] is True


def test_config_teste_nao_altera_a_ficha(tmp_path):
    ficha = _ficha_dict()
    copia = json.loads(json.dumps(ficha))
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula"], [])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula"], [])

    config_teste(ficha, {"origem": o, "destino": d}, tmp_path)

    assert ficha == copia


def test_rodar_script_e_valor(tmp_path):
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "a@x.com"]])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [["1", None]])
    config = config_teste(_ficha_dict(), {"origem": o, "destino": d}, tmp_path)

    r = rodar_script(_script(tmp_path, SCRIPT_BOM), config)

    assert isinstance(r, Execucao)
    assert r.ok is True and r.bloqueada is False
    assert r.saida == tmp_path / "saida.xlsx"
    assert r.relatorio == tmp_path / "saida_RELATORIO.xlsx"
    assert valor(r.saida, "Matricula", "1", "Email") == "a@x.com"


def test_rodar_script_detecta_saida_bloqueada(tmp_path):
    """Sabotagem: quando a conferência do núcleo falha, o teste precisa enxergar o bloqueio."""
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "a@x.com"]])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [["1", None]])
    config = config_teste(_ficha_dict(), {"origem": o, "destino": d}, tmp_path)

    r = rodar_script(_script(tmp_path, SCRIPT_BLOQUEADO), config)

    assert r.ok is False
    assert r.bloqueada is True
    assert r.saida.name == "NAO_USE_saida.xlsx"


def test_rodar_script_duas_vezes_no_mesmo_teste(tmp_path):
    """Cada chamada carrega o script de novo; uma rodada não contamina a outra."""
    script = _script(tmp_path, SCRIPT_BOM)
    for pasta, email in (("a", "a@x.com"), ("b", "b@x.com")):
        p = tmp_path / pasta
        p.mkdir()
        o = criar_planilha(p, "o.xlsx", ["Matricula", "Email"], [["1", email]])
        d = criar_planilha(p, "d.xlsx", ["Matricula", "Email"], [["1", None]])
        r = rodar_script(script, config_teste(_ficha_dict(), {"origem": o, "destino": d}, p))
        assert valor(r.saida, "Matricula", "1", "Email") == email


def test_rodar_script_nao_esconde_erro_do_script(tmp_path):
    script = _script(tmp_path, "def executar(config):\n    raise KeyError('coluna')\n")

    with pytest.raises(KeyError):
        rodar_script(script, {"saida": str(tmp_path / "s.xlsx"),
                              "relatorio": str(tmp_path / "s_RELATORIO.xlsx")})


def test_valor_compara_chave_exata_aceitando_numero_ou_texto(tmp_path):
    saida = criar_planilha(tmp_path, "s.xlsx", ["Nome", "Matricula", "Email"],
                           [["X", 48213, "x@x.com"], ["Y", "0048213", "y@x.com"]])

    assert valor(saida, "Matricula", "48213", "Email") == "x@x.com"
    assert valor(saida, "Matricula", "0048213", "Email") == "y@x.com"


def test_valor_procura_a_aba_que_tem_a_coluna_chave(tmp_path):
    saida = tmp_path / "s.xlsx"
    livro = openpyxl.Workbook()
    livro.active.title = "Legenda"
    livro.active.append(["Cor", "Significa"])
    dados = livro.create_sheet("Plan1")
    dados.append(["Matricula", "Email"])
    dados.append(["1", "a@x.com"])
    livro.save(saida)

    assert valor(saida, "Matricula", "1", "Email") == "a@x.com"


def test_valor_chave_ausente_lanca_erro(tmp_path):
    saida = criar_planilha(tmp_path, "s.xlsx", ["Matricula", "Email"], [["1", "a@x.com"]])

    with pytest.raises(KeyError):
        valor(saida, "Matricula", "2", "Email")
    with pytest.raises(KeyError):
        valor(saida, "Matricula", "1", "Telefone")


def test_achados_le_e_filtra_por_situacao(tmp_path):
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "novo@x.com"]])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [["1", "velho@x.com"], ["9", None]])
    r = rodar_script(_script(tmp_path, SCRIPT_BOM),
                     config_teste(_ficha_dict(), {"origem": o, "destino": d}, tmp_path))

    todos = achados(r.relatorio)
    diferentes = achados(r.relatorio, "diferente")

    assert len(todos) == 2
    assert [a["Chave"] for a in diferentes] == ["1"]
    assert [a["Chave"] for a in achados(r.relatorio, "sem_par")] == ["9"]
    assert achados(r.relatorio, "vazio") == []


def test_achados_sem_aba_lanca_erro(tmp_path):
    relatorio = criar_planilha(tmp_path, "r.xlsx", ["X"], [], aba="Resumo")

    with pytest.raises(KeyError):
        achados(relatorio)


def test_script_sob_teste_le_variavel(monkeypatch, tmp_path):
    monkeypatch.setenv("SCRIPT_SOB_TESTE", str(tmp_path / "script.py"))

    assert script_sob_teste() == tmp_path / "script.py"


def test_script_sob_teste_sem_variavel(monkeypatch):
    monkeypatch.delenv("SCRIPT_SOB_TESTE", raising=False)

    with pytest.raises(ScriptNaoInformado):
        script_sob_teste()


def test_descricao_kit_cita_todas_as_pecas():
    for nome in ("criar_planilha", "config_teste", "rodar_script", "valor", "achados",
                 "FICHA", "SCRIPT", "tmp_path", "test_basico_", "test_borda_"):
        assert nome in DESCRICAO_KIT


def test_importar_tudo_expoe_so_as_pecas_do_kit():
    assert set(kit_testes.__all__) == {
        "Execucao", "script_sob_teste", "criar_planilha", "config_teste",
        "rodar_script", "valor", "achados",
    }
