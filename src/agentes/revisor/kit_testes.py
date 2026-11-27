"""Kit de testes do Revisor: peças prontas e seguras para os testes que o LLM escreve.

Os testes gerados não podem importar nada (a conferência AST proíbe). O cabeçalho
fixo do arquivo de testes faz `from src.agentes.revisor.kit_testes import *`, e só
as peças listadas em __all__ ficam disponíveis.

Camada 3. Especificação: docs/estrutura.md, seção 4.6.
"""

from __future__ import annotations

import importlib.util
import json
import os
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import openpyxl

from src.contratos.ficha import Ficha

__all__ = [
    "Execucao", "script_sob_teste", "criar_planilha", "config_teste",
    "rodar_script", "valor", "achados",
]

VARIAVEL_SCRIPT = "SCRIPT_SOB_TESTE"
PREFIXO_BLOQUEIO = "NAO_USE_"
ABA_ACHADOS = "Achados"
COLUNA_SITUACAO = "situacao"
NOME_SAIDA_TESTE = "saida.xlsx"
ABA_PADRAO = "Plan1"


class ScriptNaoInformado(Exception):
    """A variável SCRIPT_SOB_TESTE não foi definida (o executor sempre a define)."""


@dataclass
class Execucao:
    """O que aconteceu ao rodar o script num teste.

    ok: o script disse que deu certo. saida/relatorio: onde os arquivos ficaram.
    bloqueada: a saída virou NAO_USE_ (uma conferência do núcleo falhou).
    """

    ok: bool
    saida: Path
    relatorio: Path
    bloqueada: bool


def script_sob_teste() -> Path:
    """Devolve o caminho do script que está sendo testado.

    Devolve: Path lido da variável de ambiente SCRIPT_SOB_TESTE.
    Lança: ScriptNaoInformado se a variável não existir.
    """
    valor_variavel = os.environ.get(VARIAVEL_SCRIPT)
    if not valor_variavel:
        raise ScriptNaoInformado(f"defina {VARIAVEL_SCRIPT} com o caminho do script")
    return Path(valor_variavel)


def criar_planilha(pasta: Path, nome: str, cabecalho: list[str], linhas: list[list],
                   aba: str = ABA_PADRAO) -> Path:
    """Cria uma planilha .xlsx pequena, inventada dentro do teste.

    Recebe:
        pasta: onde gravar (nos testes, sempre tmp_path).
        nome: nome do arquivo, ex.: "origem.xlsx".
        cabecalho: nomes das colunas (linha 1).
        linhas: uma lista por linha; None vira célula vazia.
        aba: nome da única aba.
    Devolve: o caminho do arquivo criado.
    """
    livro = openpyxl.Workbook()
    planilha = livro.active
    planilha.title = aba
    planilha.append(list(cabecalho))
    for linha in linhas:
        planilha.append(list(linha))
    caminho = Path(pasta) / nome
    livro.save(caminho)
    return caminho


def config_teste(ficha: dict, arquivos: dict, pasta: Path) -> dict:
    """Monta o CONFIG da ficha apontando para as planilhas do teste.

    Recebe:
        ficha: a ficha como dicionário (FICHA no arquivo de testes).
        arquivos: {"origem": caminho, "destino": caminho} das planilhas criadas no teste.
        pasta: onde gravar a saída (nos testes, tmp_path).
    Devolve:
        o CONFIG (formato de docs/estrutura.md, 4.2) com a saída em pasta/saida.xlsx.
    Garante:
        usa a primeira aba de cada planilha e linha_cabecalho=1, sem depender da aba da
        ficha; não altera a ficha recebida.
    """
    modelo = Ficha.de_json(json.dumps(ficha))
    textos = {rotulo: str(caminho) for rotulo, caminho in arquivos.items()}
    config = modelo.para_config(arquivos=textos, saida=str(Path(pasta) / NOME_SAIDA_TESTE))
    for rotulo, caminho in textos.items():
        config["planilhas"][rotulo]["aba"] = _primeira_aba(Path(caminho))
        config["planilhas"][rotulo]["linha_cabecalho"] = 1
    return config


def rodar_script(script: Path, config: dict) -> Execucao:
    """Carrega o script e chama executar(config), como a pessoa faria.

    Recebe:
        script: o script sob teste (SCRIPT no arquivo de testes).
        config: o CONFIG, normalmente vindo de config_teste().
    Devolve:
        Execucao com ok, caminhos da saída e do relatório e se a saída foi bloqueada.
    Garante:
        carrega o script do zero a cada chamada; um erro do script sobe sem ser escondido.
    """
    nome_modulo = f"script_sob_teste_{uuid.uuid4().hex}"
    especificacao = importlib.util.spec_from_file_location(nome_modulo, Path(script))
    if especificacao is None or especificacao.loader is None:
        raise ImportError(f"não foi possível carregar {script}")
    modulo = importlib.util.module_from_spec(especificacao)
    especificacao.loader.exec_module(modulo)
    resumo = modulo.executar(config)

    saida = Path(config["saida"])
    relatorio = Path(config["relatorio"])
    saida_do_resumo = getattr(resumo, "saida", None)
    caminho_bloqueio = saida.with_name(PREFIXO_BLOQUEIO + saida.name)

    if saida_do_resumo and Path(saida_do_resumo).name.startswith(PREFIXO_BLOQUEIO):
        bloqueada, saida_real = True, Path(saida_do_resumo)
    elif not saida.exists() and caminho_bloqueio.exists():
        bloqueada, saida_real = True, caminho_bloqueio
    else:
        bloqueada, saida_real = False, saida

    ok = bool(getattr(resumo, "ok", saida_real.exists() and not bloqueada))
    return Execucao(ok=ok and not bloqueada, saida=saida_real, relatorio=relatorio,
                    bloqueada=bloqueada)


def valor(saida: Path, coluna_chave: str, chave: Any, coluna: str) -> Any:
    """Lê uma célula da planilha de saída.

    Recebe:
        saida: a planilha (r.saida).
        coluna_chave: nome da coluna-chave, ex.: "Matricula".
        chave: o valor da chave da linha procurada, ex.: "1".
        coluna: a coluna cujo valor se quer.
    Devolve:
        o valor da célula (None se vazia).
    Garante:
        comparação exata da chave (só ignora número x texto: 1 e "1" são iguais;
        "01" e "1" não são). Usa a primeira aba que tem a coluna-chave no cabecalho.
    Lança: KeyError se a coluna ou a chave não existir.
    """
    livro = openpyxl.load_workbook(Path(saida), data_only=True)
    try:
        for planilha in livro.worksheets:
            cabecalho = [c.value for c in next(planilha.iter_rows(max_row=1), [])]
            if coluna_chave not in cabecalho:
                continue
            if coluna not in cabecalho:
                raise KeyError(f"coluna '{coluna}' não existe na saída")
            i_chave, i_coluna = cabecalho.index(coluna_chave), cabecalho.index(coluna)
            for linha in planilha.iter_rows(min_row=2, values_only=True):
                if i_chave < len(linha) and _texto(linha[i_chave]) == _texto(chave):
                    return linha[i_coluna] if i_coluna < len(linha) else None
            raise KeyError(f"chave não encontrada na coluna '{coluna_chave}'")
        raise KeyError(f"coluna-chave '{coluna_chave}' não existe na saída")
    finally:
        livro.close()


def achados(relatorio: Path, situacao: str | None = None) -> list[dict]:
    """Lê as linhas da aba "Achados" do relatório.

    Recebe:
        relatorio: o relatório (r.relatorio).
        situacao: opcional; filtra por situação, ex.: "diferente", "sem_par".
    Devolve:
        uma lista de dicionários (cabecalho -> valor), um por achado.
    Garante:
        a coluna de situação é achada sem depender de acento ou maiúscula
        ("Situação", "situacao"); o filtro também.
    Lança: KeyError se não houver a aba Achados (ou a coluna de situação, ao filtrar).
    """
    livro = openpyxl.load_workbook(Path(relatorio), data_only=True)
    try:
        if ABA_ACHADOS not in livro.sheetnames:
            raise KeyError(f"o relatório não tem a aba '{ABA_ACHADOS}'")
        linhas = list(livro[ABA_ACHADOS].iter_rows(values_only=True))
    finally:
        livro.close()
    if not linhas:
        return []
    cabecalho = [str(c) if c is not None else "" for c in linhas[0]]
    registros = [dict(zip(cabecalho, linha)) for linha in linhas[1:]
                 if any(v is not None for v in linha)]
    if situacao is None:
        return registros
    coluna = next((c for c in cabecalho if _sem_acento(c) == COLUNA_SITUACAO), None)
    if coluna is None:
        raise KeyError("a aba Achados não tem a coluna de situação")
    return [r for r in registros if _sem_acento(str(r.get(coluna) or "")) == _sem_acento(situacao)]


def _primeira_aba(caminho: Path) -> str:
    """Nome da primeira aba de uma planilha."""
    livro = openpyxl.load_workbook(caminho, read_only=True)
    try:
        return livro.sheetnames[0]
    finally:
        livro.close()


def _texto(valor_celula: Any) -> str:
    """Texto de uma célula para comparar chaves: 48213.0 vira "48213"; None vira ""."""
    if valor_celula is None:
        return ""
    if isinstance(valor_celula, float) and valor_celula.is_integer():
        return str(int(valor_celula))
    return str(valor_celula).strip()


def _sem_acento(texto: str) -> str:
    """Minúsculas sem acento e sem espaços nas pontas."""
    normal = unicodedata.normalize("NFKD", texto.strip().lower())
    return "".join(c for c in normal if not unicodedata.combining(c))


DESCRICAO_KIT = """\
Peças disponíveis nos testes (já importadas; não escreva import):

- FICHA: a ficha confirmada, como dicionário (mesmos campos do JSON da ficha).
- SCRIPT: o caminho do script que está sendo testado.
- tmp_path: pasta temporária do pytest; receba como parâmetro do teste e grave tudo nela.

- criar_planilha(pasta, nome, cabecalho, linhas, aba="Plan1") -> caminho
    Cria uma planilha pequena inventada. linhas é uma lista de listas; None = célula vazia.
    Use chaves como texto ("1", "0048213") e os MESMOS nomes de coluna da ficha.
    Ex.: o = criar_planilha(tmp_path, "o.xlsx", ["Matricula", "Email"], [["1", "a@x.com"]])

- config_teste(FICHA, {"origem": o, "destino": d}, tmp_path) -> config
    O CONFIG da ficha apontando para as planilhas do teste; a saída fica em tmp_path.

- rodar_script(SCRIPT, config) -> r
    Roda o script. r.ok (deu certo), r.bloqueada (a saída virou NAO_USE_ porque uma
    conferência falhou), r.saida e r.relatorio (caminhos).

- valor(r.saida, coluna_chave, chave, coluna) -> valor da célula (None se vazia)
    Ex.: assert valor(r.saida, "Matricula", "1", "Email") == "a@x.com"

- achados(r.relatorio, situacao=None) -> lista de achados (dicionários)
    Situações possíveis: diferente, vazio, sem_par, so_na_referencia, chave_repetida,
    protegido, fora_da_regra, pergunta, fora_do_escopo, excluido.
    Use só a quantidade ou se a lista está vazia: assert achados(r.relatorio, "sem_par")

Nomes dos testes: test_basico_* (o caso normal do pedido) e test_borda_* (casos estranhos).
"""
