"""Testes do módulo de conexão com o LLM (src/agentes/comum/llm.py)."""

from __future__ import annotations

import io
import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agentes.comum.llm import (
    LLMCompativelOpenAI,
    LLMFalso,
    LLMIndisponivel,
    criar_llm_do_ambiente,
)


def _resposta_http_falsa(conteudo: str) -> MagicMock:
    """Monta um objeto compatível com o context manager de urllib.request.urlopen."""
    payload = json.dumps({"choices": [{"message": {"content": conteudo}}]}).encode("utf-8")
    resposta = MagicMock()
    resposta.read.return_value = payload
    resposta.__enter__.return_value = resposta
    resposta.__exit__.return_value = False
    return resposta


def _erro_http(codigo: int) -> urllib.error.HTTPError:
    """Cria uma instância de HTTPError para testes sem rede."""
    return urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=codigo,
        msg=f"Erro {codigo}",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b"{}"),
    )


def test_llm_falso_devolve_respostas_em_ordem_e_registra_recebido() -> None:
    # prepara
    llm = LLMFalso(["primeira", "segunda"])
    msg_1 = [{"role": "user", "content": "oi"}]
    msg_2 = [{"role": "user", "content": "tudo bem?"}]

    # age
    r1 = llm.conversar(msg_1)
    r2 = llm.conversar(msg_2)

    # confere
    assert r1 == "primeira"
    assert r2 == "segunda"
    assert llm.recebido == [msg_1, msg_2]
    with pytest.raises(RuntimeError):
        llm.conversar([{"role": "user", "content": "terceira"}])


def test_criar_llm_do_ambiente_le_variaveis(monkeypatch: pytest.MonkeyPatch) -> None:
    # prepara
    monkeypatch.setenv("LLM_URL_BASE", "https://api.groq.com/openai/v1")
    monkeypatch.setenv("LLM_MODELO", "llama-3.3-70b-versatile")
    monkeypatch.setenv("LLM_API_KEY", "chave-teste")

    # age
    llm = criar_llm_do_ambiente()

    # confere
    assert isinstance(llm, LLMCompativelOpenAI)
    assert llm.url_base == "https://api.groq.com/openai/v1"
    assert llm.modelo == "llama-3.3-70b-versatile"
    assert llm.chave == "chave-teste"


def test_criar_llm_do_ambiente_sem_modelo_lanca_indisponivel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LLM_MODELO", raising=False)
    monkeypatch.delenv("LLM_URL_BASE", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    # age e confere
    with pytest.raises(LLMIndisponivel):
        criar_llm_do_ambiente()


def test_llm_openai_sucesso_envia_requisicao_e_devolve_texto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # prepara
    monkeypatch.setenv("LLM_API_KEY", "segredo")
    chamadas: list[object] = []

    def falso_urlopen(pedido: object, timeout: int = 120) -> MagicMock:
        chamadas.append((pedido, timeout))
        return _resposta_http_falsa("resposta do modelo")

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    llm = LLMCompativelOpenAI(modelo="modelo-x", url_base="https://exemplo.local/v1")

    # age
    saida = llm.conversar([{"role": "user", "content": "ola"}])

    # confere
    assert saida == "resposta do modelo"
    assert len(chamadas) == 1
    pedido_enviado = chamadas[0][0]
    assert pedido_enviado.full_url == "https://exemplo.local/v1/chat/completions"  # type: ignore[attr-defined]
    assert pedido_enviado.headers["Authorization"] == "Bearer segredo"  # type: ignore[attr-defined]


def test_llm_openai_http_429_espera_5s_e_10s_e_recupera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # prepara
    esperas: list[float] = []
    tentativas = {"n": 0}

    def falso_urlopen(pedido: object, timeout: int = 120) -> MagicMock:
        tentativas["n"] += 1
        if tentativas["n"] < 3:
            raise _erro_http(429)
        return _resposta_http_falsa("ok na terceira")

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: esperas.append(s))
    llm = LLMCompativelOpenAI(modelo="modelo-x", url_base="https://exemplo.local/v1")

    # age
    saida = llm.conversar([{"role": "user", "content": "oi"}])

    # confere
    assert saida == "ok na terceira"
    assert tentativas["n"] == 3
    assert esperas == [5, 10]


def test_llm_openai_http_429_esgota_tentativas_e_lanca_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # prepara
    esperas: list[float] = []

    def falso_urlopen(pedido: object, timeout: int = 120) -> MagicMock:
        raise _erro_http(429)

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: esperas.append(s))
    llm = LLMCompativelOpenAI(modelo="modelo-x", url_base="https://exemplo.local/v1")

    # age e confere
    with pytest.raises(LLMIndisponivel):
        llm.conversar([{"role": "user", "content": "oi"}])
    assert esperas == [5, 10]


def test_llm_openai_erro_de_rede_lanca_indisponivel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # prepara
    def falso_urlopen(pedido: object, timeout: int = 120) -> MagicMock:
        raise urllib.error.URLError("falha de conexao")

    monkeypatch.setattr("urllib.request.urlopen", falso_urlopen)
    llm = LLMCompativelOpenAI(modelo="modelo-x", url_base="https://exemplo.local/v1")

    # age e confere
    with pytest.raises(LLMIndisponivel):
        llm.conversar([{"role": "user", "content": "oi"}])
