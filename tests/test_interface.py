"""Interface no navegador (peca opcional): percorre o fluxo inteiro sem internet.

Pulado quando o Streamlit nao esta instalado (o nucleo nao depende dele).
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]


def _clicar(app, rotulo):
    [b for b in app.button if b.label == rotulo][0].click().run()


def test_fluxo_completo_sem_internet(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERFACE_PASTA", str(tmp_path))
    app = AppTest.from_file(str(RAIZ / "interface.py"), default_timeout=180)
    app.run()
    app.toggle[0].set_value(True).run()
    _clicar(app, "Analisar pedido")
    assert app.session_state.fase == "ficha"
    _clicar(app, "Confirmar ficha e criar script")
    assert app.session_state.fase == "criado"
    _clicar(app, "Executar script")
    assert not app.exception
    assert any("PODE USAR" in s.value for s in app.success)
    assert any("enviados ao LLM: **0**" in i.value for i in app.info)


def test_sabotagem_ficha_invalida_nao_avanca(tmp_path, monkeypatch):
    monkeypatch.setenv("INTERFACE_PASTA", str(tmp_path))
    app = AppTest.from_file(str(RAIZ / "interface.py"), default_timeout=180)
    app.run()
    app.toggle[0].set_value(True).run()
    _clicar(app, "Analisar pedido")
    app.session_state.ficha.planilhas = []          # estraga a ficha de proposito
    _clicar(app, "Confirmar ficha e criar script")
    assert app.session_state.fase == "ficha"
    assert app.error
