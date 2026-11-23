"""Interface de linha de comando (CLI) do sistema de automação de planilhas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.agentes.comum.llm import LLMIndisponivel, criar_llm_do_ambiente
from src.agentes.orquestrador import Orquestrador
from src.contratos.ficha import Ficha, FichaInvalida

PASTA_APROVADOS = Path("scripts_aprovados")


def _formatar_ficha(ficha: Ficha) -> str:
    """Formata a ficha para exibição na tela de confirmação."""
    try:
        from src.agentes.construtor.ficha import mostrar

        return mostrar(ficha)
    except ImportError:
        linhas = [
            "=== Confirmação da Ficha ===",
            f"Pedido: {ficha.pedido}",
            f"Ação: {ficha.acao}",
            f"Chave: origem='{ficha.chave.get('origem', '')}' -> "
            f"destino='{ficha.chave.get('destino', '')}'",
            f"Colunas: {ficha.colunas}",
            f"Saída: {ficha.saida}",
        ]
        if ficha.suposicoes:
            linhas.append("Suposições:")
            linhas.extend(f"  - {item}" for item in ficha.suposicoes)
        return "\n".join(linhas)


def _aplicar_correcao(ficha: Ficha, texto: str) -> None:
    """Aplica ajustes simples digitados pelo usuário no formato campo=valor."""
    if "=" not in texto:
        ficha.suposicoes.append(f"Observação do usuário: {texto}")
        return

    campo, valor = (parte.strip() for parte in texto.split("=", 1))
    campo_lower = campo.lower()

    if campo_lower == "acao":
        ficha.acao = valor
    elif campo_lower == "saida":
        ficha.saida = valor
    elif campo_lower == "chave.origem":
        ficha.chave["origem"] = valor
    elif campo_lower == "chave.destino":
        ficha.chave["destino"] = valor
    elif campo_lower.startswith("colunas.") and valor:
        coluna_origem = campo.split(".", 1)[1].strip()
        ficha.colunas[coluna_origem] = valor
    elif campo_lower == "zeros_na_chave":
        ficha.casos_problema.zeros_na_chave = valor.lower() in {"1", "true", "sim", "s"}
    elif campo_lower == "ignorar_acento_e_caixa":
        ficha.casos_problema.ignorar_acento_e_caixa = valor.lower() in {"1", "true", "sim", "s"}
    elif campo_lower == "chave_repetida" and valor in {"nao_alterar", "primeiro"}:
        ficha.casos_problema.chave_repetida = valor  # type: ignore[assignment]
    else:
        ficha.suposicoes.append(f"Ajuste solicitado ({campo}={valor})")


def _confirmar_interativo(ficha: Ficha) -> Ficha | None:
    """Exibe a ficha e aguarda confirmação ('s'), recusa ('n') ou correção."""
    while True:
        print(_formatar_ficha(ficha))
        resposta = input("Confirmar ficha? [s/n ou correção campo=valor]: ").strip()
        resposta_lower = resposta.lower()
        if resposta_lower in {"s", "sim"}:
            return ficha
        if resposta_lower in {"n", "nao", "não"}:
            return None
        if resposta:
            _aplicar_correcao(ficha, resposta)


def _interpretar_planilhas(itens: list[str]) -> dict[str, Path]:
    """Converte argumentos 'rotulo=caminho' em dicionário de caminhos validados."""
    planilhas: dict[str, Path] = {}
    for item in itens:
        if "=" not in item:
            raise ValueError(f"Formato inválido para --planilha: '{item}'. Use rotulo=CAMINHO.")
        rotulo, caminho_str = (parte.strip() for parte in item.split("=", 1))
        if not rotulo or not caminho_str:
            raise ValueError(f"Rótulo ou caminho vazio em --planilha: '{item}'.")
        caminho = Path(caminho_str)
        if not caminho.is_file():
            raise FileNotFoundError(f"Planilha '{rotulo}' não encontrada: {caminho}")
        planilhas[rotulo] = caminho

    if set(planilhas) != {"origem", "destino"}:
        raise ValueError("Informe exatamente --planilha origem=CAMINHO e --planilha destino=CAMINHO.")
    return planilhas


def _comando_listar(pasta_aprovados: Path) -> int:
    """Lista os scripts aprovados registrados em indice.json."""
    arquivo_indice = pasta_aprovados / "indice.json"
    if not arquivo_indice.is_file():
        print("Nenhum script aprovado encontrado.")
        return 0

    itens = json.loads(arquivo_indice.read_text(encoding="utf-8"))
    if not itens:
        print("Nenhum script aprovado encontrado.")
        return 0

    for item in itens:
        nome = item.get("nome", "(sem nome)")
        acao = item.get("acao", "-")
        descricao = item.get("descricao", "")
        voltas = item.get("voltas", "-")
        print(f"- {nome} [{acao}] (voltas: {voltas}): {descricao}")
    return 0


def _comando_criar(args: argparse.Namespace) -> int:
    """Executa o fluxo de criação ou reaproveitamento de script a partir de um pedido."""
    planilhas = _interpretar_planilhas(args.planilha or [])
    llm = criar_llm_do_ambiente()
    orquestrador = Orquestrador(llm, PASTA_APROVADOS, modo=args.modo)
    resultado = orquestrador.fase1(
        args.pedido,
        planilhas,
        confirmar=_confirmar_interativo,
    )

    print(f"Situação: {resultado.situacao} (voltas: {resultado.voltas})")
    if resultado.script is not None:
        print(f"Script aprovado: {resultado.script}")
    for etapa in resultado.historico:
        print(f"  - {etapa}")

    return 1 if resultado.situacao == "reprovado" else 0


def _criar_parser() -> argparse.ArgumentParser:
    """Constrói o parser de argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        prog="python -m src.principal",
        description="Gera e lista automações em Python para planilhas.",
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    parser_criar = subparsers.add_parser("criar", help="Cria ou reaproveita um script.")
    parser_criar.add_argument("pedido", help="Descrição em português do que fazer nas planilhas.")
    parser_criar.add_argument(
        "--planilha",
        action="append",
        required=True,
        help="Par rotulo=CAMINHO (obrigatório informar origem=... e destino=...).",
    )
    parser_criar.add_argument(
        "--modo",
        choices=("dois_agentes", "um_agente"),
        default="dois_agentes",
        help="Modo de execução da Fase 1 (padrão: dois_agentes).",
    )

    subparsers.add_parser("listar", help="Lista os scripts aprovados disponíveis.")
    return parser


def executar_cli(argv: list[str] | None = None) -> int:
    """Ponto de entrada testável da interface de linha de comando.

    Recebe:
        argv: lista de argumentos (usa sys.argv[1:] se None).
    Devolve:
        Código de saída do processo (0 para sucesso/cancelamento, 1 para erro/reprovação).
    Garante:
        Erros esperados são exibidos de forma legível sem stack trace.
    """
    parser = _criar_parser()
    try:
        args = parser.parse_args(argv)
        if args.comando == "listar":
            return _comando_listar(PASTA_APROVADOS)
        if args.comando == "criar":
            return _comando_criar(args)
        return 1
    except (LLMIndisponivel, FichaInvalida, ValueError, FileNotFoundError, OSError) as erro:
        print(f"Erro: {erro}")
        return 1


def main() -> None:
    """Executa a CLI e encerra o processo com o código de retorno adequado."""
    sys.exit(executar_cli())


if __name__ == "__main__":
    main()
