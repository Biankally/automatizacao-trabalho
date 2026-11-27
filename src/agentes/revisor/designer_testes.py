"""Designer de testes do Revisor: o LLM escreve testes a partir SÓ da ficha.

O Revisor nunca vê o código do Construtor (abordagem do AgentCoder). Ele recebe a
ficha e a descrição do kit, e o LLM escreve apenas funções test_basico_* e
test_borda_*. O cabeçalho do arquivo é fixo e colocado aqui.

Camada 3. Especificação: docs/estrutura.md, seção 4.6.
Não importa nada de src/agentes/construtor/.
"""

from __future__ import annotations

import ast
import re

from src.agentes.comum.execucao import CodigoRecusado, conferir_codigo, extrair_codigo
from src.agentes.comum.llm import LLM, Mensagem
from src.agentes.comum.prompts import carregar
from src.agentes.revisor import kit_testes
from src.contratos.ficha import Ficha

MAX_TENTATIVAS = 2
PREFIXOS = {"basico": "test_basico_", "borda": "test_borda_"}
NOMES_PERMITIDOS: set[str] = set(kit_testes.__all__) | {"pytest", "FICHA", "SCRIPT"}
ATRIBUTOS_DE_PULAR = {"skip", "xfail", "importorskip"}

CABECALHO = """\
# ===== Testes gerados pelo Revisor. Nao edite o cabecalho. =====
import json

import pytest  # noqa: F401

from src.agentes.revisor.kit_testes import *  # noqa: F401,F403

FICHA = json.loads({ficha!r})
SCRIPT = script_sob_teste()  # noqa: F405

"""

_FUNCAO_DE_TESTE = re.compile(r"^def (test_basico_|test_borda_)\w*\s*\(", re.MULTILINE)


def escrever_testes(llm: LLM, ficha: Ficha, descricao_kit: str) -> str:
    """Pede ao LLM os testes da ficha e monta o arquivo pytest completo.

    Recebe:
        llm: o LLM em uso (real ou falso), já registrado pelo orquestrador.
        ficha: a ficha confirmada (a única informação sobre o pedido).
        descricao_kit: o texto do kit (kit_testes.DESCRICAO_KIT).
    Devolve:
        o arquivo de testes: cabeçalho fixo + as funções escritas pelo LLM.
    Garante:
        o LLM recebe só a ficha e o kit; as funções passam pela conferência AST com
        só o kit, pytest, FICHA e SCRIPT liberados; há ao menos um teste de cada
        categoria; nenhum teste se pula. Uma resposta recusada ganha 1 nova
        tentativa com o motivo; na 2ª recusa, lança CodigoRecusado.
    """
    prompt = carregar("revisor_testes", ficha=ficha.para_json(), kit=descricao_kit)
    mensagens: list[Mensagem] = [{"role": "user", "content": prompt}]
    motivo = ""
    for _tentativa in range(MAX_TENTATIVAS):
        resposta = llm.conversar(mensagens)
        try:
            codigo = extrair_codigo(resposta)
            problemas = _conferir(codigo)
        except CodigoRecusado as erro:
            problemas = [str(erro)]
        if not problemas:
            return CABECALHO.format(ficha=ficha.para_json()) + codigo + "\n"
        motivo = "; ".join(problemas)
        mensagens = mensagens + [
            {"role": "assistant", "content": resposta},
            {"role": "user", "content": (
                "Os testes foram recusados: " + motivo + "\n"
                "Corrija e responda de novo com um único bloco ```python, só com funções "
                "test_basico_* e test_borda_*."
            )},
        ]
    raise CodigoRecusado(motivo)


def categorias(testes: str) -> dict[str, int]:
    """Conta os testes de cada categoria pelo nome da função.

    Recebe: o texto de um arquivo de testes.
    Devolve: {"basico": n, "borda": n}.
    """
    prefixos = _FUNCAO_DE_TESTE.findall(testes)
    return {categoria: prefixos.count(prefixo) for categoria, prefixo in PREFIXOS.items()}


def _conferir(codigo: str) -> list[str]:
    """Junta a conferência de segurança (execucao.py) com as regras próprias dos testes."""
    problemas = conferir_codigo(codigo, NOMES_PERMITIDOS)
    if problemas:
        return problemas
    arvore = ast.parse(codigo)
    for no in arvore.body:
        if not isinstance(no, ast.FunctionDef):
            problemas.append(f"Linha {no.lineno}: só funções de teste são permitidas.")
        elif not no.name.startswith(tuple(PREFIXOS.values())):
            problemas.append(f"Linha {no.lineno}: '{no.name}' deve começar com "
                             "test_basico_ ou test_borda_.")
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute) and no.attr in ATRIBUTOS_DE_PULAR:
            problemas.append(f"Linha {no.lineno}: teste não pode se pular ('{no.attr}').")
    contagem = categorias(codigo)
    for categoria, quantidade in contagem.items():
        if quantidade == 0:
            problemas.append(f"Falta pelo menos um teste {PREFIXOS[categoria]}*.")
    return problemas
