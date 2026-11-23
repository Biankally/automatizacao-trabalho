"""Extração e validação estática de código Python e JSON gerados pelo LLM.

Responsabilidades:
1. extrair_codigo: extrai um único bloco ```python da resposta do modelo.
2. conferir_codigo: analisa a AST sem executar o código, bloqueando construções
   perigosas ou fora do catálogo e exigindo as funções esperadas.
3. extrair_json: localiza e decodifica um objeto JSON mesmo cercado de texto ou crases.
"""

from __future__ import annotations

import ast
import json
import re

FUNCOES_SEGURAS: set[str] = {
    "abs",
    "all",
    "any",
    "bool",
    "dict",
    "enumerate",
    "filter",
    "float",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "print",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
    "Exception",
    "ValueError",
    "KeyError",
    "TypeError",
    "IndexError",
}

PROIBIDAS: set[str] = {
    "open",
    "exec",
    "eval",
    "compile",
    "__import__",
    "getattr",
    "setattr",
    "delattr",
    "globals",
    "locals",
    "vars",
    "input",
    "breakpoint",
    "exit",
    "quit",
    "help",
    "dir",
}

# "{0.__class__}".format(x) acessa atributos internos sem passar pela AST.
ATRIBUTOS_PROIBIDOS: set[str] = {"format", "format_map"}
# Atributos de frames, geradores e corrotinas que expõem o ambiente externo.
PREFIXOS_PROIBIDOS: tuple[str, ...] = ("gi_", "cr_", "ag_", "f_", "tb_", "co_")

_BLOCO_CODIGO = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
_BLOCO_GENERICO = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL | re.IGNORECASE)


class CodigoRecusado(Exception):
    """Lançada quando a resposta não contém código válido ou falha na conferência AST."""


def extrair_codigo(resposta: str) -> str:
    """Extrai um único bloco de código Python delimitado por crases.

    Recebe:
        resposta: texto completo devolvido pelo LLM.
    Devolve:
        O código Python limpo contido no bloco.
    Lança:
        CodigoRecusado: se não houver bloco ```python ou se houver mais de um.
    """
    blocos = _BLOCO_CODIGO.findall(resposta)
    if not blocos:
        raise CodigoRecusado("A resposta não tem bloco ```python.")
    if len(blocos) > 1:
        raise CodigoRecusado("A resposta tem mais de um bloco de código; esperado um só.")
    return blocos[0].strip()


def conferir_codigo(
    codigo: str,
    permitidas: set[str],
    exigir_funcoes: tuple[str, ...] = (),
) -> list[str]:
    """Verifica estaticamente (via AST) se o código gerado é seguro e respeita o catálogo.

    Recebe:
        codigo: código Python extraído da resposta do LLM.
        permitidas: conjunto de nomes de funções autorizadas para chamada.
        exigir_funcoes: tupla de nomes de funções que devem estar definidas no topo do código.
    Devolve:
        Lista de problemas encontrados; lista vazia significa código aceito.
    Garante:
        Não executa o código analisado e bloqueia imports, acessos internos e chamadas proibidas.
    """
    try:
        arvore = ast.parse(codigo)
    except SyntaxError as erro:
        return [f"Erro de sintaxe na linha {erro.lineno}."]

    definidas_topo = {n.name for n in arvore.body if isinstance(n, ast.FunctionDef)}
    definidas_todas = {n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)}

    atribuidas: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Name) and isinstance(no.ctx, ast.Store):
            atribuidas.add(no.id)
        elif isinstance(no, (ast.FunctionDef, ast.Lambda)):
            atribuidas |= {arg.arg for arg in no.args.args + no.args.kwonlyargs}
        elif isinstance(no, ast.ExceptHandler) and no.name:
            atribuidas.add(no.name)

    todas_permitidas = permitidas | FUNCOES_SEGURAS | definidas_todas
    problemas: list[str] = []

    for no in ast.walk(arvore):
        linha = getattr(no, "lineno", "?")
        if isinstance(no, (ast.Import, ast.ImportFrom)):
            problemas.append(f"Linha {linha}: import não é permitido.")
        elif isinstance(no, (ast.Global, ast.Nonlocal)):
            problemas.append(f"Linha {linha}: global/nonlocal não é permitido.")
        elif isinstance(no, ast.Attribute) and (
            no.attr.startswith("_")
            or no.attr in ATRIBUTOS_PROIBIDOS
            or no.attr.startswith(PREFIXOS_PROIBIDOS)
        ):
            problemas.append(f"Linha {linha}: atributo interno '{no.attr}' não é permitido.")
        elif isinstance(no, ast.Name) and no.id.startswith("__"):
            problemas.append(f"Linha {linha}: nome interno '{no.id}' não é permitido.")
        elif isinstance(no, ast.Name) and no.id in PROIBIDAS:
            problemas.append(f"Linha {linha}: '{no.id}' não é permitido.")
        elif isinstance(no, ast.Call) and isinstance(no.func, ast.Name):
            nome = no.func.id
            if nome not in todas_permitidas and nome not in atribuidas and nome not in PROIBIDAS:
                problemas.append(f"Linha {linha}: função '{nome}' não está no catálogo.")

    for funcao_exigida in exigir_funcoes:
        if funcao_exigida not in definidas_topo:
            problemas.append(f"Função obrigatória '{funcao_exigida}' não foi definida.")

    return problemas


def extrair_json(resposta: str) -> dict:
    """Localiza e interpreta um objeto JSON (dict) mesmo cercado de texto ou crases.

    Recebe:
        resposta: texto devolvido pelo LLM contendo um objeto JSON.
    Devolve:
        Dicionário Python decodificado a partir do JSON.
    Lança:
        ValueError: se nenhum objeto JSON válido for encontrado na resposta.
    """
    candidatos: list[str] = [bloco.strip() for bloco in _BLOCO_GENERICO.findall(resposta)]
    candidatos.append(resposta.strip())

    for texto in candidatos:
        if not texto:
            continue
        try:
            objeto = json.loads(texto)
            if isinstance(objeto, dict):
                return objeto
        except json.JSONDecodeError:
            pass

    decodificador = json.JSONDecoder()
    for indice, caractere in enumerate(resposta):
        if caractere != "{":
            continue
        try:
            objeto, _ = decodificador.raw_decode(resposta, indice)
            if isinstance(objeto, dict):
                return objeto
        except json.JSONDecodeError:
            continue

    raise ValueError("Nenhum objeto JSON válido encontrado na resposta.")