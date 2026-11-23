"""Testes do orquestrador da Fase 1 (src/agentes/orquestrador.py)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.agentes.comum.execucao import CodigoRecusado
from src.agentes.comum.llm import LLMFalso
from src.agentes.orquestrador import Orquestrador
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha


def _ficha_valida(saida: Path) -> Ficha:
    return Ficha(
        pedido="Completar email por matricula",
        planilhas=[
            PlanilhaDaFicha("origem", "rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1", 1),
        ],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(zeros_na_chave=True),
        saida=str(saida),
        suposicoes=["Chave com zeros a esquerda."],
    )


def _configurar_pecas_falsas(
    monkeypatch: pytest.MonkeyPatch,
    ficha: Ficha,
    resultados_execucao: list[tuple[bool, int, str]],
    reaproveitar: str | None = None,
    lancar_recusado_na_primeira: bool = False,
) -> dict[str, list]:
    """Substitui as dependências externas do orquestrador para testar o fluxo isoladamente."""
    chamadas: dict[str, list] = {
        "decidir": [],
        "preencher": [],
        "escrever_testes": [],
        "gerar_corpo": [],
        "configurar": [],
        "executar": [],
    }

    monkeypatch.setattr(
        "src.agentes.orquestrador._extrair_raio_x_e_amostras",
        lambda planilhas: ([], []),
    )
    monkeypatch.setattr("src.agentes.orquestrador._obter_descricoes_catalogo", lambda: [])

    def falso_decidir(llm, pedido, raio_x, indice):
        chamadas["decidir"].append((pedido, indice))
        llm.conversar([{"role": "user", "content": pedido}])
        return SimpleNamespace(reaproveitar=reaproveitar, parecido=None, motivo="teste")

    def falso_preencher(llm, pedido, raio_x, amostras):
        chamadas["preencher"].append(pedido)
        llm.conversar([{"role": "user", "content": pedido}])
        return ficha

    def falso_escrever_testes(llm, ficha_arg, descricao_kit):
        chamadas["escrever_testes"].append(ficha_arg.acao)
        llm.conversar([{"role": "user", "content": ficha_arg.pedido}])
        return "def test_basico_ok():\n    assert True\n"

    def falso_gerar_corpo(llm, ficha_arg, descricoes, exemplo=None, aviso_anterior=None):
        chamadas["gerar_corpo"].append({"exemplo": exemplo, "aviso": aviso_anterior})
        llm.conversar([{"role": "user", "content": aviso_anterior or "primeira"}])
        if lancar_recusado_na_primeira and len(chamadas["gerar_corpo"]) == 1:
            raise CodigoRecusado("import proibido")
        return "def executar(config):\n    return config['saida']\n"

    def falso_configurar(ficha_arg, pasta_aprovado):
        chamadas["configurar"].append((ficha_arg.saida, pasta_aprovado))
        return (
            "# --- CONFIG (inicio) ---\n"
            f"CONFIG = {ficha_arg.para_config()!r}\n"
            "# --- CONFIG (fim) ---\n"
            "def executar(config):\n    return config['saida']\n"
        )

    fila_resultados = list(resultados_execucao)

    def falso_executar(script, testes, tempo_limite=60):
        chamadas["executar"].append((script, testes))
        passou, total, msg_aviso = fila_resultados.pop(0)
        return SimpleNamespace(
            passou=passou,
            total=total,
            falhas=[]
            if passou
            else [SimpleNamespace(teste="test_borda_x", tipo_erro="AssertionError", linha=10)],
            aviso=lambda: msg_aviso,
        )

    monkeypatch.setattr("src.agentes.orquestrador._chamar_decidir", falso_decidir)
    monkeypatch.setattr("src.agentes.orquestrador._chamar_preencher", falso_preencher)
    monkeypatch.setattr("src.agentes.orquestrador._chamar_escrever_testes", falso_escrever_testes)
    monkeypatch.setattr("src.agentes.orquestrador._chamar_gerar_corpo", falso_gerar_corpo)
    monkeypatch.setattr("src.agentes.orquestrador.configurar", falso_configurar)
    monkeypatch.setattr("src.agentes.orquestrador._chamar_executar_testes", falso_executar)
    return chamadas


def test_fase1_aprova_na_primeira_volta_e_atualiza_indice(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    ficha = _ficha_valida(tmp_path / "saida.xlsx")
    _configurar_pecas_falsas(monkeypatch, ficha, [(True, 2, "")])
    llm = LLMFalso(["r_busca", "r_ficha", "r_testes", "r_codigo"])
    orq = Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    # age
    resultado = orq.fase1(
        "Completar email por matricula",
        {"origem": tmp_path / "rh.xlsx", "destino": tmp_path / "cadastro.xlsx"},
        confirmar=lambda f: f,
    )

    # confere
    assert resultado.situacao == "aprovado"
    assert resultado.voltas == 1
    assert resultado.script is not None and resultado.script.is_file()
    pasta_script = resultado.script.parent
    assert (pasta_script / "ficha.json").is_file()
    assert (pasta_script / "test_script.py").is_file()

    indice = json.loads((aprovados / "indice.json").read_text(encoding="utf-8"))
    assert len(indice) == 1
    assert indice[0]["nome"] == "completar_email_por_matricula"
    assert indice[0]["voltas"] == 1
    assert "r_codigo" in orq.registro.texto_enviado() or "primeira" in orq.registro.texto_enviado()


def test_fase1_corrige_na_segunda_volta_enviando_aviso(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    ficha = _ficha_valida(tmp_path / "saida.xlsx")
    chamadas = _configurar_pecas_falsas(
        monkeypatch,
        ficha,
        [
            (False, 2, "Falharam 1 de 2 testes:\n- test_borda_x: AssertionError na linha 10"),
            (True, 2, ""),
        ],
    )
    llm = LLMFalso(["r_busca", "r_ficha", "r_testes", "r_cod_1", "r_cod_2"])
    orq = Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    # age
    resultado = orq.fase1(
        "Completar email",
        {"origem": tmp_path / "rh.xlsx", "destino": tmp_path / "cadastro.xlsx"},
        confirmar=lambda f: f,
    )

    # confere
    assert resultado.situacao == "aprovado"
    assert resultado.voltas == 2
    assert len(chamadas["escrever_testes"]) == 1
    assert len(chamadas["gerar_corpo"]) == 2
    assert chamadas["gerar_corpo"][0]["aviso"] is None
    assert "test_borda_x" in chamadas["gerar_corpo"][1]["aviso"]


def test_fase1_reprova_apos_max_voltas_e_conta_codigo_recusado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    ficha = _ficha_valida(tmp_path / "saida.xlsx")
    chamadas = _configurar_pecas_falsas(
        monkeypatch,
        ficha,
        [
            (False, 2, "Falha volta 2"),
            (False, 2, "Falha volta 3"),
        ],
        lancar_recusado_na_primeira=True,
    )
    llm = LLMFalso(["r_busca", "r_ficha", "r_testes", "r_1", "r_2", "r_3"])
    orq = Orquestrador(llm, aprovados, max_voltas=3, pasta_trabalho=tmp_path / "trabalho")

    # age
    resultado = orq.fase1(
        "Completar email",
        {"origem": tmp_path / "rh.xlsx", "destino": tmp_path / "cadastro.xlsx"},
        confirmar=lambda f: f,
    )

    # confere
    assert resultado.situacao == "reprovado"
    assert resultado.voltas == 3
    assert resultado.script is None
    assert len(chamadas["gerar_corpo"]) == 3
    assert not (aprovados / "indice.json").exists()


def test_fase1_cancela_quando_confirmacao_devolve_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    ficha = _ficha_valida(tmp_path / "saida.xlsx")
    chamadas = _configurar_pecas_falsas(monkeypatch, ficha, [])
    llm = LLMFalso(["r_busca", "r_ficha"])
    orq = Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    # age
    resultado = orq.fase1(
        "Completar email",
        {"origem": tmp_path / "rh.xlsx", "destino": tmp_path / "cadastro.xlsx"},
        confirmar=lambda f: None,
    )

    # confere
    assert resultado.situacao == "cancelado"
    assert resultado.voltas == 0
    assert chamadas["escrever_testes"] == []
    assert chamadas["gerar_corpo"] == []


def test_fase1_reaproveita_script_existente_sem_gerar_codigo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # prepara
    aprovados = tmp_path / "aprovados"
    pasta_existente = aprovados / "completar_email_por_matricula"
    pasta_existente.mkdir(parents=True)
    (pasta_existente / "script.py").write_text("# script existente", encoding="utf-8")

    ficha = _ficha_valida(tmp_path / "nova_saida.xlsx")
    chamadas = _configurar_pecas_falsas(
        monkeypatch,
        ficha,
        [(True, 2, "")],
        reaproveitar="completar_email_por_matricula",
    )
    llm = LLMFalso(["r_busca", "r_ficha", "r_testes"])
    orq = Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    # age
    resultado = orq.fase1(
        "Completar email",
        {"origem": tmp_path / "rh.xlsx", "destino": tmp_path / "cadastro.xlsx"},
        confirmar=lambda f: f,
    )

    # confere
    assert resultado.situacao == "aprovado"
    assert resultado.voltas == 1
    assert chamadas["gerar_corpo"] == []
    assert len(chamadas["configurar"]) == 1
