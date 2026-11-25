"""Testes do preenchimento e exibição da Ficha pelo Construtor (src/agentes/construtor/ficha.py)."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from src.agentes.comum.llm import LLMFalso
from src.agentes.construtor.ficha import mostrar, preencher
from src.contratos.ficha import CasosProblema, Ficha, FichaInvalida, PlanilhaDaFicha


@dataclass
class _RaioXFalso:
    texto: str

    def para_texto(self) -> str:
        return self.texto


def _json_ficha_valida(acao: str = "completar") -> str:
    dados = {
        "planilhas": [
            {"rotulo": "origem", "arquivo": "rh.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
            {"rotulo": "destino", "arquivo": "cadastro.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
        ],
        "chave": {"origem": "Matricula", "destino": "Matricula"},
        "acao": acao,
        "colunas": {"Email": "Email"},
        "casos_problema": {
            "chave_repetida": "nao_alterar",
            "ignorar_acento_e_caixa": False,
            "zeros_na_chave": True,
        },
        "saida": "saida/cadastro_completado.xlsx",
        "suposicoes": ["Matrículas com zeros à esquerda serão comparadas como iguais."],
    }
    return json.dumps(dados, ensure_ascii=False)


def test_preencher_interpreta_resposta_suja_e_define_pedido_e_nao_confirmada() -> None:
    # prepara
    resposta_suja = (
        "Com base nas colunas analisadas, segue a ficha preenchida:\n"
        f"```json\n{_json_ficha_valida()}\n```\n"
        "Revise antes de prosseguir."
    )
    llm = LLMFalso([resposta_suja])
    raio_x = [_RaioXFalso("Planilha rh.xlsx: Matricula (texto), Email (texto)")]
    amostras = [[{"Matricula": "00123", "Email": "exemplo@dominio.com"}]]
    pedido = "Completar o email do cadastro usando a planilha do RH"

    # age
    ficha = preencher(llm, pedido, raio_x, amostras)  # type: ignore[arg-type]

    # confere
    assert isinstance(ficha, Ficha)
    assert ficha.pedido == pedido
    assert ficha.confirmada is False
    assert ficha.acao == "completar"
    assert ficha.chave == {"origem": "Matricula", "destino": "Matricula"}
    assert ficha.colunas == {"Email": "Email"}
    assert ficha.casos_problema.zeros_na_chave is True
    assert ficha.suposicoes == ["Matrículas com zeros à esquerda serão comparadas como iguais."]
    assert ficha.problemas() == []
    assert len(llm.recebido) == 1
    prompt_enviado = llm.recebido[0][-1]["content"]
    assert pedido in prompt_enviado
    assert "Planilha rh.xlsx" in prompt_enviado
    assert "00123" in prompt_enviado


def test_preencher_faz_uma_nova_tentativa_quando_primeira_resposta_falha() -> None:
    # prepara
    resposta_invalida = "Desculpe, não consegui gerar o JSON agora."
    resposta_valida = _json_ficha_valida(acao="trocar")
    llm = LLMFalso([resposta_invalida, resposta_valida])
    raio_x = [_RaioXFalso("Raio-X teste")]

    # age
    ficha = preencher(llm, "Trocar email", raio_x, [])  # type: ignore[arg-type]

    # confere
    assert ficha.acao == "trocar"
    assert len(llm.recebido) == 2
    aviso_segunda_tentativa = llm.recebido[1][-1]["content"]
    assert "erro" in aviso_segunda_tentativa.lower() or "inválid" in aviso_segunda_tentativa.lower()


def test_preencher_lanca_ficha_invalida_na_segunda_falha() -> None:
    # prepara
    resposta_sem_json = "Texto sem estrutura JSON"
    resposta_acao_invalida = _json_ficha_valida(acao="acao_inexistente")
    llm = LLMFalso([resposta_sem_json, resposta_acao_invalida])
    raio_x = [_RaioXFalso("Raio-X teste")]

    # age e confere
    with pytest.raises(FichaInvalida):
        preencher(llm, "Fazer algo", raio_x, [])  # type: ignore[arg-type]
    assert len(llm.recebido) == 2


def test_mostrar_exibe_todos_os_campos_relevantes_da_ficha() -> None:
    # prepara
    ficha = Ficha(
        pedido="Completar email por matrícula",
        planilhas=[
            PlanilhaDaFicha("origem", "rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1", 1),
        ],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(
            chave_repetida="nao_alterar",
            ignorar_acento_e_caixa=True,
            zeros_na_chave=True,
        ),
        saida="saida/cadastro_completado.xlsx",
        suposicoes=["Ignorar zeros à esquerda na matrícula."],
    )

    # age
    tela = mostrar(ficha)

    # confere
    assert "Completar email por matrícula" in tela
    assert "rh.xlsx" in tela
    assert "cadastro.xlsx" in tela
    assert "Matricula" in tela
    assert "completar" in tela
    assert "Email" in tela
    assert "saida/cadastro_completado.xlsx" in tela
    assert "Ignorar zeros à esquerda na matrícula." in tela
