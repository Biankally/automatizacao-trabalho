"""Testes da interface de linha de comando (src/principal.py)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agentes.comum.llm import LLMFalso, LLMIndisponivel
from src.agentes.orquestrador import ResultadoFase1
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha
from src.principal import executar_cli


def _ficha_teste(saida: Path) -> Ficha:
    return Ficha(
        pedido="Completar email",
        planilhas=[
            PlanilhaDaFicha("origem", "rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1", 1),
        ],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(zeros_na_chave=True),
        saida=str(saida),
        suposicoes=["Zeros a esquerda ignorados."],
    )


def test_listar_exibe_scripts_aprovados(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # prepara
    aprovados = tmp_path / "scripts_aprovados"
    aprovados.mkdir()
    indice = [
        {
            "nome": "completar_email_por_matricula",
            "acao": "completar",
            "descricao": "Completar email do cadastro",
            "aprovado_em": "2026-11-20T18:00:00",
            "voltas": 1,
        }
    ]
    (aprovados / "indice.json").write_text(
        json.dumps(indice, ensure_ascii=False), encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)

    # age
    codigo = executar_cli(["listar"])
    saida = capsys.readouterr().out

    # confere
    assert codigo == 0
    assert "completar_email_por_matricula" in saida
    assert "Completar email do cadastro" in saida


def test_listar_sem_indice_mostra_mensagem_amigavel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # prepara
    monkeypatch.chdir(tmp_path)

    # age
    codigo = executar_cli(["listar"])
    saida = capsys.readouterr().out

    # confere
    assert codigo == 0
    assert "Nenhum script aprovado" in saida


def test_criar_confirma_com_s_e_aprova_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # prepara
    origem = tmp_path / "rh.xlsx"
    destino = tmp_path / "cadastro.xlsx"
    origem.write_text("falso", encoding="utf-8")
    destino.write_text("falso", encoding="utf-8")
    script_gerado = tmp_path / "aprovados" / "completar_email" / "script.py"
    ficha = _ficha_teste(tmp_path / "saida.xlsx")

    class OrquestradorFalso:
        def __init__(self, llm, pasta_aprovados, **kwargs) -> None:
            self.pasta_aprovados = pasta_aprovados

        def fase1(self, pedido, planilhas, confirmar) -> ResultadoFase1:
            confirmada = confirmar(ficha)
            if confirmada is None:
                return ResultadoFase1("cancelado", ficha, None, 0, ["Cancelado"])
            return ResultadoFase1("aprovado", confirmada, script_gerado, 1, ["Aprovado"])

    monkeypatch.setattr("src.principal.criar_llm_do_ambiente", lambda: LLMFalso([]))
    monkeypatch.setattr("src.principal.Orquestrador", OrquestradorFalso)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "s")

    # age
    codigo = executar_cli(
        [
            "criar",
            "Completar email",
            "--planilha",
            f"origem={origem}",
            "--planilha",
            f"destino={destino}",
        ]
    )
    saida = capsys.readouterr().out

    # confere
    assert codigo == 0
    assert "aprovado" in saida.lower()
    assert str(script_gerado) in saida


def test_criar_cancela_com_n(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # prepara
    origem = tmp_path / "rh.xlsx"
    destino = tmp_path / "cadastro.xlsx"
    origem.write_text("falso", encoding="utf-8")
    destino.write_text("falso", encoding="utf-8")
    ficha = _ficha_teste(tmp_path / "saida.xlsx")

    class OrquestradorFalso:
        def __init__(self, llm, pasta_aprovados, **kwargs) -> None:
            pass

        def fase1(self, pedido, planilhas, confirmar) -> ResultadoFase1:
            confirmada = confirmar(ficha)
            assert confirmada is None
            return ResultadoFase1("cancelado", ficha, None, 0, ["Cancelado pelo usuario"])

    monkeypatch.setattr("src.principal.criar_llm_do_ambiente", lambda: LLMFalso([]))
    monkeypatch.setattr("src.principal.Orquestrador", OrquestradorFalso)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")

    # age
    codigo = executar_cli(
        [
            "criar",
            "Completar email",
            "--planilha",
            f"origem={origem}",
            "--planilha",
            f"destino={destino}",
        ]
    )
    saida = capsys.readouterr().out

    # confere
    assert codigo == 0
    assert "cancelado" in saida.lower()


def test_criar_aceita_correcao_antes_de_confirmar(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    origem = tmp_path / "rh.xlsx"
    destino = tmp_path / "cadastro.xlsx"
    origem.write_text("falso", encoding="utf-8")
    destino.write_text("falso", encoding="utf-8")
    ficha = _ficha_teste(tmp_path / "saida.xlsx")
    ficha_recebida: list[Ficha] = []

    class OrquestradorFalso:
        def __init__(self, llm, pasta_aprovados, **kwargs) -> None:
            pass

        def fase1(self, pedido, planilhas, confirmar) -> ResultadoFase1:
            confirmada = confirmar(ficha)
            assert confirmada is not None
            ficha_recebida.append(confirmada)
            return ResultadoFase1("aprovado", confirmada, tmp_path / "s.py", 1, [])

    respostas_usuario = iter(["acao=trocar", "s"])
    monkeypatch.setattr("src.principal.criar_llm_do_ambiente", lambda: LLMFalso([]))
    monkeypatch.setattr("src.principal.Orquestrador", OrquestradorFalso)
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(respostas_usuario))

    # age
    codigo = executar_cli(
        [
            "criar",
            "Trocar email",
            "--planilha",
            f"origem={origem}",
            "--planilha",
            f"destino={destino}",
        ]
    )

    # confere
    assert codigo == 0
    assert ficha_recebida[0].acao == "trocar"


def test_criar_erro_de_llm_mostra_mensagem_sem_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # prepara
    origem = tmp_path / "rh.xlsx"
    destino = tmp_path / "cadastro.xlsx"
    origem.write_text("falso", encoding="utf-8")
    destino.write_text("falso", encoding="utf-8")

    def falhar_llm():
        raise LLMIndisponivel("Chave LLM_API_KEY ausente")

    monkeypatch.setattr("src.principal.criar_llm_do_ambiente", falhar_llm)

    # age
    codigo = executar_cli(
        [
            "criar",
            "Completar email",
            "--planilha",
            f"origem={origem}",
            "--planilha",
            f"destino={destino}",
        ]
    )
    saida = capsys.readouterr().out

    # confere
    assert codigo == 1
    assert "Erro:" in saida
    assert "Traceback" not in saida
