"""Teste da demonstracao: roda o roteiro inteiro no plano B (sem internet) numa pasta temporaria."""

import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def test_demo_offline_roda_do_pedido_ao_painel(tmp_path):
    env = dict(os.environ, DEMO_PASTA=str(tmp_path / "demo"), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(RAIZ / "demo.py"), "--offline", "--direto", "--sem-navegador"],
                       cwd=RAIZ, env=env, capture_output=True, text=True, encoding="utf-8", timeout=300)
    assert r.returncode == 0, r.stderr
    assert "PODE USAR" in r.stdout
    assert "2 de 3 passaram" in r.stdout and "3 de 3 passaram" in r.stdout     # o Revisor pegou o erro
    painel = (tmp_path / "demo" / "painel.html").read_text(encoding="utf-8")
    assert "aprovado" in painel and "Antes" in painel


def test_planilhas_de_exemplo(tmp_path):
    sys.path.insert(0, str(RAIZ))
    from dados_exemplo import gerar_exemplos
    feitos = gerar_exemplos.main(tmp_path)
    assert (tmp_path / "basico" / "rh.xlsx").exists() and len(feitos) == 12
