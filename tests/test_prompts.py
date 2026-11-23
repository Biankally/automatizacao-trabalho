"""Testes do carregador de prompts (src/agentes/comum/prompts.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agentes.comum.prompts import carregar


def test_carregar_preenche_variaveis_com_utf8(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    pasta_prompts = tmp_path / "prompts"
    pasta_prompts.mkdir()
    conteudo = (
        "Papel: assistente de automação.\n"
        "Pedido: $pedido\n"
        "Índice: $indice\n"
        'Responda apenas JSON: {"reaproveitar": null}'
    )
    (pasta_prompts / "exemplo.md").write_text(conteudo, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # age
    resultado = carregar("exemplo", pedido="Completar e-mail por matrícula", indice="[]")

    # confere
    assert "Pedido: Completar e-mail por matrícula" in resultado
    assert "Índice: []" in resultado
    assert '{"reaproveitar": null}' in resultado


def test_carregar_falta_variavel_lanca_key_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    pasta_prompts = tmp_path / "prompts"
    pasta_prompts.mkdir()
    (pasta_prompts / "incompleto.md").write_text(
        "Pedido: $pedido\nRaio-X: $raio_x", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    # age e confere
    with pytest.raises(KeyError):
        carregar("incompleto", pedido="Trocar telefone")


def test_carregar_arquivo_inexistente_lanca_file_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    monkeypatch.chdir(tmp_path)

    # age e confere
    with pytest.raises(FileNotFoundError):
        carregar("prompt_que_nao_existe")
