"""Carregamento e preenchimento de templates de prompts em Markdown."""

from __future__ import annotations

from pathlib import Path
from string import Template

PASTA_PROMPTS = Path("prompts")


def carregar(nome: str, **valores: str) -> str:
    """Lê um arquivo de prompt em Markdown e substitui suas variáveis.

    Recebe:
        nome: nome do arquivo dentro de prompts/ (sem a extensão .md).
        valores: pares chave=valor usados para preencher as variáveis $chave.
    Devolve:
        O texto completo do prompt preenchido.
    Lança:
        FileNotFoundError: se o arquivo prompts/<nome>.md não existir.
        KeyError: se alguma variável esperada no template não for informada.
    """
    arquivo = PASTA_PROMPTS / f"{nome}.md"
    conteudo = arquivo.read_text(encoding="utf-8")
    return Template(conteudo).substitute(**valores)
