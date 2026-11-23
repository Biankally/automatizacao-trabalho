from __future__ import annotations

from typing import TYPE_CHECKING

from src.agentes.comum.execucao import CodigoRecusado, conferir_codigo, extrair_codigo
from src.agentes.comum.llm import LLM, Mensagem
from src.agentes.comum.prompts import carregar
from src.contratos.ficha import Ficha

if TYPE_CHECKING:
    from src.nucleo.catalogo import DescricaoDeFuncao


def gerar_corpo(
    llm: LLM,
    ficha: Ficha,
    descricoes: list[DescricaoDeFuncao],
    exemplo: str | None = None,
    aviso_anterior: str | None = None,
) -> str:
    """Gera e valida estaticamente a função `def executar(config):` para a ficha.

    Recebe:
        llm: cliente de modelo de linguagem (real ou falso).
        ficha: ficha confirmada descrevendo a automação.
        descricoes: lista de descrições das funções disponíveis no catálogo.
        exemplo: código opcional de `executar` de um script aprovado parecido.
        aviso_anterior: resumo opcional das falhas da tentativa anterior.
    Devolve:
        Código-fonte validado da função `def executar(config):`.
    Garante:
        Lança CodigoRecusado se o código não tiver bloco único, não definir
        `executar` ou violar as regras de segurança da AST.
    """
    texto_descricoes = "\n".join(
        desc.linha_da_aula() if hasattr(desc, "linha_da_aula") else str(desc)
        for desc in descricoes
    )
    texto_exemplo = (
        f"```python\n{exemplo.strip()}\n```"
        if exemplo and exemplo.strip()
        else "Nenhum script parecido disponível."
    )

    prompt = carregar(
        "construtor_aula",
        descricoes=texto_descricoes,
        ficha=ficha.para_json(),
        exemplo=texto_exemplo,
    )

    if aviso_anterior:
        prompt = (
            f"{prompt}\n\n"
            "# Correção obrigatória da tentativa anterior\n"
            "A versão anterior falhou na verificação ou nos testes:\n"
            f"{aviso_anterior}\n"
            "Corrija a lógica de `def executar(config):` para resolver essas falhas."
        )

    mensagens: list[Mensagem] = [{"role": "user", "content": prompt}]
    resposta = llm.conversar(mensagens)
    codigo = extrair_codigo(resposta)

    nomes_do_catalogo = {desc.nome for desc in descricoes}
    problemas = conferir_codigo(
        codigo,
        nomes_do_catalogo,
        exigir_funcoes=("executar",),
    )
    if problemas:
        raise CodigoRecusado("; ".join(problemas))

    return codigo
