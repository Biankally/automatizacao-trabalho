"""Testes do registro de chamadas ao LLM (src/agentes/comum/registro.py)."""

import json

import pytest

from src.agentes.comum.llm import LLMFalso, LLMIndisponivel
from src.agentes.comum.registro import LLMRegistrado, RegistroDeChamadas


def test_texto_enviado_junta_tudo_o_que_saiu():
    registro = RegistroDeChamadas()

    registro.anotar("busca", [{"role": "user", "content": "pedido um"}], "resposta um")
    registro.anotar("ficha", [{"role": "system", "content": "regras"},
                              {"role": "user", "content": "pedido dois"}], "resposta dois")

    enviado = registro.texto_enviado()
    assert "pedido um" in enviado and "regras" in enviado and "pedido dois" in enviado


def test_texto_enviado_nao_inclui_respostas():
    """O que o LLM respondeu não saiu da máquina; só o que foi enviado conta."""
    registro = RegistroDeChamadas()

    registro.anotar("busca", [{"role": "user", "content": "pergunta"}], "RESPOSTA_DO_LLM")

    assert "RESPOSTA_DO_LLM" not in registro.texto_enviado()


def test_registro_vazio():
    assert RegistroDeChamadas().texto_enviado() == ""


def test_llm_registrado_repassa_e_anota():
    falso = LLMFalso(["oi de volta"])
    registro = RegistroDeChamadas()
    llm = LLMRegistrado(falso, registro, "revisor")

    resposta = llm.conversar([{"role": "user", "content": "oi"}])

    assert resposta == "oi de volta"
    assert falso.recebido == [[{"role": "user", "content": "oi"}]]
    assert "oi" in registro.texto_enviado()


def test_llm_registrado_anota_mesmo_quando_o_llm_falha():
    """Se a chamada falha, o texto pode ter saído mesmo assim: fica anotado e o erro sobe."""

    class LLMQueFalha:
        def conversar(self, mensagens):
            raise LLMIndisponivel("fora do ar")

    registro = RegistroDeChamadas()
    llm = LLMRegistrado(LLMQueFalha(), registro, "ficha")

    with pytest.raises(LLMIndisponivel):
        llm.conversar([{"role": "user", "content": "texto enviado"}])
    assert "texto enviado" in registro.texto_enviado()


def test_anotar_guarda_copia_das_mensagens():
    """Mudar a lista depois de anotar não pode mudar o registro."""
    registro = RegistroDeChamadas()
    mensagens = [{"role": "user", "content": "original"}]

    registro.anotar("busca", mensagens, "r")
    mensagens[0]["content"] = "alterado"

    assert "original" in registro.texto_enviado()
    assert "alterado" not in registro.texto_enviado()


def test_salvar_grava_json_utf8(tmp_path):
    registro = RegistroDeChamadas()
    registro.anotar("construtor", [{"role": "user", "content": "matrícula e ação"}], "ok")
    arquivo = tmp_path / "logs" / "chamadas.json"

    registro.salvar(str(arquivo))

    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados == [{"agente": "construtor",
                      "mensagens": [{"role": "user", "content": "matrícula e ação"}],
                      "resposta": "ok"}]
    assert "matrícula" in arquivo.read_text(encoding="utf-8")
