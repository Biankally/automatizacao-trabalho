"""Testes do executor do Revisor (src/agentes/revisor/executor.py).

O executor roda o pytest num processo separado e resume o resultado SEM valores:
só o nome do teste, o tipo do erro e a linha. Os testes abaixo criam arquivos de
teste pequenos em tmp_path e conferem esse resumo.
"""

from pathlib import Path

from src.agentes.revisor.executor import Falha, ResultadoTestes, executar


def _arquivos(tmp_path: Path, testes: str) -> tuple[Path, Path]:
    """Cria um script qualquer e um arquivo de testes com o conteúdo dado."""
    script = tmp_path / "script.py"
    script.write_text("def executar(config):\n    return None\n", encoding="utf-8")
    arquivo_testes = tmp_path / "test_script.py"
    arquivo_testes.write_text(testes, encoding="utf-8")
    return script, arquivo_testes


def test_executar_todos_passam(tmp_path):
    script, testes = _arquivos(tmp_path, (
        "def test_basico_um():\n    assert 1 + 1 == 2\n\n"
        "def test_borda_dois():\n    assert 'a' in 'abc'\n"
    ))

    resultado = executar(script, testes)

    assert resultado.passou is True
    assert resultado.total == 2
    assert resultado.falhas == []


def test_executar_falha_traz_nome_tipo_e_linha(tmp_path):
    script, testes = _arquivos(tmp_path, (
        "def test_basico_ok():\n    assert True\n\n"
        "def test_borda_quebra():\n    x = 1\n    assert x == 2\n"
    ))

    resultado = executar(script, testes)

    assert resultado.passou is False
    assert resultado.total == 2
    assert resultado.falhas == [Falha("test_borda_quebra", "AssertionError", 6)]


def test_executar_aviso_nao_vaza_valores(tmp_path):
    """Sabotagem de privacidade: a mensagem do assert tem um valor; o aviso não pode trazê-lo."""
    script, testes = _arquivos(tmp_path, (
        "def test_borda_email():\n"
        "    valor = 'segredo@exemplo.com'\n"
        "    assert valor == 'outro@exemplo.com', 'esperava outro@exemplo.com'\n"
    ))

    aviso = executar(script, testes).aviso()

    assert "test_borda_email" in aviso
    assert "AssertionError" in aviso
    assert "segredo" not in aviso and "outro@" not in aviso


def test_executar_outro_tipo_de_erro(tmp_path):
    script, testes = _arquivos(tmp_path, "def test_basico_chave():\n    {}['x']\n")

    falha = executar(script, testes).falhas[0]

    assert falha.teste == "test_basico_chave"
    assert falha.tipo_erro == "KeyError"
    assert falha.linha == 2


def test_executar_repassa_script_sob_teste(tmp_path):
    script, testes = _arquivos(tmp_path, (
        "import os\n"
        "from pathlib import Path\n\n"
        "def test_basico_variavel():\n"
        "    assert Path(os.environ['SCRIPT_SOB_TESTE']).name == 'script.py'\n"
    ))

    assert executar(script, testes).passou is True


def test_executar_tempo_esgotado(tmp_path):
    script, testes = _arquivos(tmp_path, (
        "import time\n\ndef test_basico_lento():\n    time.sleep(30)\n"
    ))

    resultado = executar(script, testes, tempo_limite=2)

    assert resultado.passou is False
    assert [f.tipo_erro for f in resultado.falhas] == ["TempoEsgotado"]


def test_executar_nenhum_teste(tmp_path):
    script, testes = _arquivos(tmp_path, "def ajuda():\n    return 1\n")

    resultado = executar(script, testes)

    assert resultado.passou is False
    assert [f.tipo_erro for f in resultado.falhas] == ["NenhumTeste"]


def test_executar_teste_pulado_nao_conta_como_aprovado(tmp_path):
    """Sabotagem: um teste que se pula não prova nada, então não pode aprovar o script."""
    script, testes = _arquivos(tmp_path, (
        "import pytest\n\ndef test_basico_pula():\n    pytest.skip('sem motivo')\n"
    ))

    resultado = executar(script, testes)

    assert resultado.passou is False
    assert resultado.falhas[0].teste == "test_basico_pula"
    assert resultado.falhas[0].tipo_erro == "TestePulado"


def test_executar_erro_de_sintaxe_no_arquivo_de_testes(tmp_path):
    script, testes = _arquivos(tmp_path, "def test_basico_quebrado(:\n    pass\n")

    resultado = executar(script, testes)

    assert resultado.passou is False
    assert resultado.falhas


def test_aviso_formato():
    resultado = ResultadoTestes(False, 2, [Falha("test_borda_x", "AssertionError", 12)])

    assert resultado.aviso() == "Falharam 1 de 2 testes:\n- test_borda_x: AssertionError na linha 12"


def test_aviso_sem_linha_e_aprovado():
    sem_linha = ResultadoTestes(False, 0, [Falha("(todos)", "TempoEsgotado", None)])
    aprovado = ResultadoTestes(True, 3, [])

    assert sem_linha.aviso().endswith("- (todos): TempoEsgotado")
    assert aprovado.aviso() == "Todos os 3 testes passaram."
