"""Montagem e reconfiguração de scripts Python a partir do modelo oficial."""

from __future__ import annotations

import ast
from pathlib import Path
import pprint
import re
from string import Template
import unicodedata

from src.contratos.ficha import Ficha

_RAIZ_PROJETO = Path(__file__).resolve().parents[3]
CAMINHO_MODELO = _RAIZ_PROJETO / "modelos" / "script_gerado.py.modelo"
MARCADOR_CONFIG_INICIO = "# --- CONFIG (inicio) ---"
MARCADOR_CONFIG_FIM = "# --- CONFIG (fim) ---"


def config_da_ficha(ficha: Ficha) -> dict:
    """Converte a ficha validada no dicionário CONFIG esperado pelo script gerado.

    Recebe:
        ficha: instância de Ficha preenchida.
    Devolve:
        Dicionário CONFIG no formato da seção 4.2.
    Garante:
        Não altera a ficha recebida.
    """
    return ficha.para_config()


def montar(funcao: str, ficha: Ficha) -> str:
    """Encaixa o CONFIG da ficha e a função executar no modelo de script.

    Recebe:
        funcao: código-fonte da função `def executar(config):`.
        ficha: ficha com os parâmetros da automação.
    Devolve:
        Código completo do script Python pronto para ser salvo e executado.
    Garante:
        O código final compila sintaticamente quando `funcao` é válida.
    """
    modelo_texto = CAMINHO_MODELO.read_text(encoding="utf-8")
    config_formatado = pprint.pformat(config_da_ficha(ficha), width=100, sort_dicts=False)
    script = Template(modelo_texto).substitute(
        raiz=str(_RAIZ_PROJETO),
        config=config_formatado,
        funcao=funcao.strip(),
    )
    compile(script, "<script_gerado>", "exec")
    return script


def configurar(ficha: Ficha, pasta_aprovado: Path) -> str:
    """Reaproveita um script aprovado trocando exclusivamente o bloco CONFIG.

    Recebe:
        ficha: nova ficha com os caminhos e colunas do pedido atual.
        pasta_aprovado: diretório do script aprovado contendo `script.py`.
    Devolve:
        Texto do script com o novo CONFIG e todo o restante preservado.
    Garante:
        Nenhum caractere fora dos marcadores de CONFIG é alterado.
    """
    caminho_script = pasta_aprovado / "script.py"
    script_atual = caminho_script.read_text(encoding="utf-8")

    if MARCADOR_CONFIG_INICIO not in script_atual or MARCADOR_CONFIG_FIM not in script_atual:
        raise ValueError("Marcadores de CONFIG não encontrados no script aprovado.")

    antes, resto = script_atual.split(MARCADOR_CONFIG_INICIO, 1)
    _, depois = resto.split(MARCADOR_CONFIG_FIM, 1)

    config_formatado = pprint.pformat(config_da_ficha(ficha), width=100, sort_dicts=False)
    return (
        f"{antes}{MARCADOR_CONFIG_INICIO}\n"
        f"CONFIG = {config_formatado}\n"
        f"{MARCADOR_CONFIG_FIM}{depois}"
    )


def funcao_de(script: str) -> str:
    """Extrai o código-fonte da função `executar` de um script Python.

    Recebe:
        script: texto completo de um script Python.
    Devolve:
        Trecho correspondente à definição de `def executar(config):`.
    Garante:
        Lança ValueError se o script não definir `executar`.
    """
    try:
        arvore = ast.parse(script)
    except SyntaxError as erro:
        raise ValueError("Script com erro de sintaxe ao extrair 'executar'.") from erro

    linhas = script.splitlines()
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "executar":
            inicio = no.decorator_list[0].lineno if no.decorator_list else no.lineno
            fim = no.end_lineno or no.lineno
            return "\n".join(linhas[inicio - 1 : fim]).strip()

    raise ValueError("Função 'executar' não encontrada no script.")


def nome_do_script(ficha: Ficha) -> str:
    """Gera um identificador limpo para a pasta do script aprovado a partir da ficha.

    Recebe:
        ficha: ficha da automação.
    Devolve:
        Nome normalizado (ex.: 'completar_email_por_matricula').
    Garante:
        Contém apenas caracteres `a-z`, `0-9` e `_`, sem acentos.
    """
    acao = _normalizar_identificador(ficha.acao or "executar")
    colunas = "_".join(_normalizar_identificador(c) for c in ficha.colunas.values() if c)
    chave_bruta = ficha.chave.get("destino") or ficha.chave.get("origem") or "chave"
    chave = _normalizar_identificador(chave_bruta)

    partes = [p for p in (acao, colunas, "por", chave) if p]
    return "_".join(partes)


def _normalizar_identificador(texto: str) -> str:
    """Remove acentos e converte um texto livre em identificador ASCII snake_case."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")
    return re.sub(r"_+", "_", limpo)
