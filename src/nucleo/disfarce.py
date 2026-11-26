"""Disfarce: descreve uma planilha para o LLM sem revelar nenhum valor.

raio_x() conta linhas, tipos e vazios de cada coluna, com um exemplo INVENTADO.
amostra_disfarcada() devolve algumas linhas com cada valor trocado por outro de mesmo
formato: letra vira outra letra, digito vira outro digito, zero a esquerda continua zero,
pontuacao (@ . - /) continua igual, data anda alguns dias.

Camada 5: usa so o nucleo e a biblioteca padrao. Especificacao: docs/estrutura.md, secao 4.3.
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass
from typing import Any

from src.nucleo import nucleo as N

LETRAS = "abcdefghijklmnopqrstuvwxyz"


@dataclass
class ColunaRaioX:
    """Uma coluna descrita sem valores reais."""

    nome: str
    tipo: str           # "texto", "numero", "data" ou "vazio"
    pct_vazios: float
    exemplo: str        # INVENTADO: mesmo formato, outro conteudo


@dataclass
class RaioX:
    """A planilha inteira descrita sem valores reais."""

    arquivo: str
    aba: str
    total_linhas: int
    colunas: list[ColunaRaioX]

    def para_texto(self) -> str:
        """Devolve o texto que vai no prompt: uma linha por coluna."""
        linhas = [f"Planilha (aba '{self.aba}'), {self.total_linhas} linhas:"]
        for c in self.colunas:
            linhas.append(f"- {c.nome}: {c.tipo}, {c.pct_vazios:.0f}% vazios, "
                          f"exemplo inventado: {c.exemplo}")
        return "\n".join(linhas)


def _inventar(valor: Any, rnd: random.Random) -> str:
    """Troca o conteudo e mantem o formato. Vazio continua vazio."""
    if N.vazio(valor):
        return ""
    if isinstance(valor, (dt.date, dt.datetime)):
        return (valor + dt.timedelta(days=rnd.randint(1, 400))).isoformat()
    texto, saida = str(valor), []
    for i, ch in enumerate(texto):
        zero_a_esquerda = ch == "0" and all(c == "0" for c in texto[:i])
        if ch.isdigit():
            saida.append("0" if zero_a_esquerda else str(rnd.randint(1, 9)))
        elif ch.isalpha():
            letra = rnd.choice(LETRAS)
            saida.append(letra.upper() if ch.isupper() else letra)
        else:
            saida.append(ch)
    novo = "".join(saida)
    return novo if novo != texto else "x" + novo


def _tipo(valores: list[Any]) -> str:
    """Diz o tipo da coluna olhando so os valores preenchidos."""
    cheios = [v for v in valores if not N.vazio(v)]
    if not cheios:
        return "vazio"
    if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in cheios):
        return "numero"
    if all(isinstance(v, (dt.date, dt.datetime)) for v in cheios):
        return "data"
    return "texto"


def raio_x(arquivo: str, aba: str, linha_cabecalho: int = 1) -> RaioX:
    """Descreve a planilha.

    Recebe: o arquivo, a aba e a linha do cabecalho.
    Devolve: o RaioX (nomes das colunas, tipos, % de vazios e um exemplo inventado).
    Garante: nenhum valor da planilha aparece no RaioX; so os nomes das colunas.
    """
    tabela = N.ler_aba("X", str(arquivo), aba, linha_cabecalho)
    rnd = random.Random(42)
    colunas = []
    for nome in tabela.colunas:
        valores = [linha.valores.get(nome) for linha in tabela.linhas]
        n_vazios = sum(N.vazio(v) for v in valores)
        primeiro = next((v for v in valores if not N.vazio(v)), None)
        colunas.append(ColunaRaioX(nome, _tipo(valores), 100 * n_vazios / max(len(valores), 1),
                                   _inventar(primeiro, rnd)))
    return RaioX(str(arquivo), aba, len(tabela.linhas), colunas)


def amostra_disfarcada(arquivo: str, aba: str, linha_cabecalho: int = 1,
                       n: int = 30, semente: int = 42) -> list[dict]:
    """Sorteia ate n linhas e disfarca cada valor.

    Recebe: o arquivo, a aba, a linha do cabecalho, quantas linhas e a semente do sorteio.
    Devolve: uma lista de {coluna: valor inventado}.
    Garante: nenhum valor original aparece; a mesma semente da sempre a mesma amostra.
    """
    tabela = N.ler_aba("X", str(arquivo), aba, linha_cabecalho)
    rnd = random.Random(semente)
    linhas = rnd.sample(tabela.linhas, min(n, len(tabela.linhas)))
    return [{k: _inventar(v, rnd) for k, v in linha.valores.items()} for linha in linhas]
