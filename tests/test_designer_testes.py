"""Testes do designer de testes do Revisor (src/agentes/revisor/designer_testes.py).

O LLM é sempre o LLMFalso. Os últimos testes rodam o arquivo gerado de verdade,
pelo executor, contra scripts de mentira: um certo e um sabotado.
"""

import json
from pathlib import Path

import pytest

from src.agentes.comum.execucao import CodigoRecusado
from src.agentes.comum.llm import LLMFalso
from src.agentes.revisor.designer_testes import categorias, escrever_testes
from src.agentes.revisor.executor import executar
from src.agentes.revisor.kit_testes import DESCRICAO_KIT
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha

TESTES_BONS = '''Aqui estão os testes:
```python
def test_basico_completa_vazio(tmp_path):
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "a@x.com"]])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [["1", None]])
    r = rodar_script(SCRIPT, config_teste(FICHA, {"origem": o, "destino": d}, tmp_path))
    assert r.ok and not r.bloqueada
    assert valor(r.saida, "Matricula", "1", "Email") == "a@x.com"


def test_borda_nao_sobrescreve(tmp_path):
    o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "novo@x.com"]])
    d = criar_planilha(tmp_path, "d.xlsx", ["Matricula", "Email"], [["1", "velho@x.com"]])
    r = rodar_script(SCRIPT, config_teste(FICHA, {"origem": o, "destino": d}, tmp_path))
    assert valor(r.saida, "Matricula", "1", "Email") == "velho@x.com"
    assert achados(r.relatorio, "diferente")
```'''

SO_BASICO = '''```python
def test_basico_um(tmp_path):
    assert True
```'''


def _ficha() -> Ficha:
    return Ficha(
        pedido="completar o email do cadastro pela matricula",
        planilhas=[PlanilhaDaFicha("origem", "rh.xlsx", "Plan1"),
                   PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1")],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(),
        saida="saida/out.xlsx",
    )


def test_escrever_testes_monta_arquivo_com_cabecalho_fixo():
    llm = LLMFalso([TESTES_BONS])

    arquivo = escrever_testes(llm, _ficha(), DESCRICAO_KIT)

    assert "import json" in arquivo
    assert "from src.agentes.revisor.kit_testes import *" in arquivo
    assert "SCRIPT = script_sob_teste()" in arquivo
    assert "def test_basico_completa_vazio(tmp_path):" in arquivo
    assert "Aqui estão" not in arquivo
    compile(arquivo, "test_script.py", "exec")


def test_escrever_testes_ficha_embutida_volta_igual():
    arquivo = escrever_testes(LLMFalso([TESTES_BONS]), _ficha(), DESCRICAO_KIT)

    escopo: dict = {}
    linha_ficha = next(l for l in arquivo.splitlines() if l.startswith("FICHA = "))
    exec(linha_ficha, {"json": json}, escopo)
    assert escopo["FICHA"] == json.loads(_ficha().para_json())


def test_escrever_testes_prompt_tem_ficha_e_kit_e_nada_de_codigo():
    """O Revisor recebe só a ficha e o kit (RN-11): nunca o código do Construtor."""
    llm = LLMFalso([TESTES_BONS])

    escrever_testes(llm, _ficha(), DESCRICAO_KIT)

    prompt = llm.recebido[0][-1]["content"]
    assert '"acao": "completar"' in prompt
    assert "criar_planilha" in prompt
    assert "def executar" not in prompt


def test_escrever_testes_sem_borda_tenta_de_novo_e_desiste():
    llm = LLMFalso([SO_BASICO, SO_BASICO])

    with pytest.raises(CodigoRecusado):
        escrever_testes(llm, _ficha(), DESCRICAO_KIT)
    assert len(llm.recebido) == 2
    assert "test_borda_" in llm.recebido[1][-1]["content"]


def test_escrever_testes_segunda_tentativa_corrige():
    ruim = "```python\nimport os\n\ndef test_basico_x(tmp_path):\n    pass\n```"
    llm = LLMFalso([ruim, TESTES_BONS])

    arquivo = escrever_testes(llm, _ficha(), DESCRICAO_KIT)

    assert "test_borda_nao_sobrescreve" in arquivo
    assert len(llm.recebido) == 2


@pytest.mark.parametrize("corpo", [
    "import os\n\ndef test_basico_a(tmp_path):\n    pass\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "def test_basico_a(tmp_path):\n    open('x')\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "def test_basico_a(tmp_path):\n    executar({})\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "def ajuda():\n    return 1\n\ndef test_basico_a(tmp_path):\n    pass\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "X = 1\n\ndef test_basico_a(tmp_path):\n    pass\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "def test_basico_a(tmp_path):\n    pytest.skip('x')\n\ndef test_borda_b(tmp_path):\n    pass\n",
    "def test_outro_a(tmp_path):\n    pass\n\ndef test_basico_a(tmp_path):\n    pass\n\ndef test_borda_b(tmp_path):\n    pass\n",
])
def test_escrever_testes_recusa_codigo_fora_das_regras(corpo):
    resposta = f"```python\n{corpo}```"

    with pytest.raises(CodigoRecusado):
        escrever_testes(LLMFalso([resposta, resposta]), _ficha(), DESCRICAO_KIT)


def test_escrever_testes_aceita_pytest_raises_e_variaveis():
    corpo = (
        "def test_basico_a(tmp_path):\n"
        "    chave = FICHA['chave']['destino']\n"
        "    assert chave\n\n"
        "def test_borda_b(tmp_path):\n"
        "    with pytest.raises(KeyError):\n"
        "        {}['x']\n"
    )
    arquivo = escrever_testes(LLMFalso([f"```python\n{corpo}```"]), _ficha(), DESCRICAO_KIT)

    assert "pytest.raises" in arquivo


def test_categorias_conta_por_prefixo():
    arquivo = escrever_testes(LLMFalso([TESTES_BONS]), _ficha(), DESCRICAO_KIT)

    assert categorias(arquivo) == {"basico": 1, "borda": 1}
    assert categorias("def ajuda():\n    pass\n") == {"basico": 0, "borda": 0}


# ---------- O arquivo gerado roda de verdade ----------

SCRIPT_CERTO = '''
from pathlib import Path
from types import SimpleNamespace
import openpyxl

def executar(config):
    p = config["planilhas"]
    o = openpyxl.load_workbook(p["origem"]["arquivo"]).worksheets[0]
    livro = openpyxl.load_workbook(p["destino"]["arquivo"])
    d = livro.worksheets[0]
    emails = {str(l[0]): l[1] for l in o.iter_rows(min_row=2, values_only=True)}
    rel = openpyxl.Workbook()
    ach = rel.create_sheet("Achados")
    ach.append(["Chave", "Situacao"])
    for r in range(2, d.max_row + 1):
        chave = str(d.cell(r, 1).value)
        atual = d.cell(r, 2).value
        if atual is None:
            d.cell(r, 2).value = emails.get(chave)
        elif atual != emails.get(chave):
            ach.append([chave, "diferente"])
    livro.save(config["saida"])
    rel.save(config["relatorio"])
    return SimpleNamespace(ok=True, saida=config["saida"])
'''


def _gerar_e_rodar(tmp_path: Path, script: str):
    arquivo_testes = tmp_path / "test_script.py"
    arquivo_testes.write_text(escrever_testes(LLMFalso([TESTES_BONS]), _ficha(), DESCRICAO_KIT),
                              encoding="utf-8")
    arquivo_script = tmp_path / "script.py"
    arquivo_script.write_text(script, encoding="utf-8")
    return executar(arquivo_script, arquivo_testes)


def test_arquivo_gerado_aprova_script_certo(tmp_path):
    resultado = _gerar_e_rodar(tmp_path, SCRIPT_CERTO)

    assert resultado.passou, resultado.aviso()
    assert resultado.total == 2


def test_arquivo_gerado_reprova_script_que_sobrescreve(tmp_path):
    """Sabotagem: o script troca em vez de completar; o teste de borda tem de pegar."""
    sabotado = SCRIPT_CERTO.replace("if atual is None:", "if True:")

    resultado = _gerar_e_rodar(tmp_path, sabotado)

    assert not resultado.passou
    assert [f.teste for f in resultado.falhas] == ["test_borda_nao_sobrescreve"]
    assert "velho@x.com" not in resultado.aviso()
