"""Contrato da Ficha: as 6 respostas que definem um pedido sobre planilhas.

A ficha e a "comanda" do sistema. O LLM preenche, a pessoa confere,
o Construtor e o Revisor leem, e o script recebe a ficha convertida em CONFIG.

Camada 6: importa so a biblioteca padrao. Especificacao: docs/estrutura.md, secao 4.2.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import PurePath
from typing import Literal

ACOES = ("completar", "trocar")
CHAVE_REPETIDA = ("nao_alterar", "primeiro")
ROTULOS = ("origem", "destino")
SUFIXO_RELATORIO = "_RELATORIO.xlsx"


class FichaInvalida(Exception):
    """A ficha nao pode ser lida: JSON quebrado ou campos com formato impossivel."""


@dataclass
class PlanilhaDaFicha:
    """Uma planilha usada no pedido.

    Recebe: rotulo ("origem" ou "destino"), arquivo, aba e a linha do cabecalho.
    """

    rotulo: str
    arquivo: str
    aba: str
    linha_cabecalho: int = 1


@dataclass
class CasosProblema:
    """O que fazer nos casos estranhos (pergunta 5 da ficha).

    Recebe:
        chave_repetida: "nao_alterar" (padrao) ou "primeiro".
        ignorar_acento_e_caixa: True faz "JOSE" e "josé" serem a mesma chave.
        zeros_na_chave: True faz "0048213" e "48213" serem a mesma chave.
    """

    chave_repetida: Literal["nao_alterar", "primeiro"] = "nao_alterar"
    ignorar_acento_e_caixa: bool = False
    zeros_na_chave: bool = False


def _relatorio_de(saida: str) -> str:
    """Troca a extensao da saida por _RELATORIO.xlsx, mantendo as barras como vieram.

    Recebe: o caminho da saida, por exemplo "saida/cadastro.xlsx".
    Devolve: "saida/cadastro_RELATORIO.xlsx".
    Garante: nao troca "/" por "\\" no Windows (por isso nao usa str(Path(...))).
    """
    sufixo = PurePath(saida).suffix
    base = saida[: len(saida) - len(sufixo)] if sufixo else saida
    return base + SUFIXO_RELATORIO


@dataclass
class Ficha:
    """A comanda: as 6 respostas do pedido, mais o texto original e as suposicoes.

    Campos numerados = as 6 perguntas:
        1. planilhas  2. chave  3. acao  4. colunas  5. casos_problema  6. saida
    """

    pedido: str
    planilhas: list[PlanilhaDaFicha]
    chave: dict[str, str]
    acao: str
    colunas: dict[str, str]
    casos_problema: CasosProblema
    saida: str
    suposicoes: list[str] = field(default_factory=list)
    confirmada: bool = False

    def problemas(self) -> list[str]:
        """Confere se a ficha esta completa e coerente.

        Recebe: nada (olha os proprios campos).
        Devolve: uma frase por problema, comecando pelo nome do campo.
        Garante: lista vazia significa ficha valida; nao altera a ficha.
        """
        achados: list[str] = []

        rotulos = sorted(p.rotulo for p in self.planilhas)
        if rotulos != sorted(ROTULOS):
            achados.append("planilhas: precisa de exatamente uma 'origem' e um 'destino'")
        for p in self.planilhas:
            if not p.arquivo or not p.aba:
                achados.append(f"planilhas: '{p.rotulo}' sem arquivo ou aba")

        if set(self.chave) != set(ROTULOS) or not all(self.chave.values()):
            achados.append("chave: informe a coluna-chave da origem e do destino")

        if self.acao not in ACOES:
            achados.append(f"acao: deve ser 'completar' ou 'trocar', veio '{self.acao}'")

        if not self.colunas or not all(self.colunas) or not all(self.colunas.values()):
            achados.append("colunas: informe pelo menos uma coluna origem -> destino")
        if self.chave.get("destino") in self.colunas.values():
            achados.append("colunas: a coluna-chave do destino nao pode ser alterada")

        if self.casos_problema.chave_repetida not in CHAVE_REPETIDA:
            achados.append("casos_problema.chave_repetida: deve ser 'nao_alterar' ou 'primeiro'")

        if not self.saida:
            achados.append("saida: informe o arquivo de saida")

        return achados

    def perguntas(self) -> list[str]:
        """Transforma cada problema numa pergunta para a pessoa.

        Recebe: nada.
        Devolve: uma pergunta por item de problemas(), na mesma ordem.
        Garante: len(perguntas()) == len(problemas()).
        """
        return [f"Pode corrigir? {p}" for p in self.problemas()]

    def para_config(self, arquivos: dict[str, str] | None = None,
                    saida: str | None = None) -> dict:
        """Monta o CONFIG que o script gerado recebe (formato da secao 4.2).

        Recebe:
            arquivos: opcional, troca o arquivo de uma planilha pelo rotulo,
                      ex.: {"origem": "teste/o.xlsx"}. O que nao vier fica igual.
            saida: opcional, troca o arquivo de saida.
        Devolve: um dicionario novo com planilhas, chave, acao, colunas,
                 casos_problema, saida e relatorio.
        Garante: nao altera a ficha (tudo e copiado); relatorio = saida + _RELATORIO.xlsx.
        """
        arquivos = arquivos or {}
        saida_final = str(saida or self.saida)
        return {
            "planilhas": {
                p.rotulo: {
                    "arquivo": str(arquivos.get(p.rotulo, p.arquivo)),
                    "aba": p.aba,
                    "linha_cabecalho": p.linha_cabecalho,
                }
                for p in self.planilhas
            },
            "chave": dict(self.chave),
            "acao": self.acao,
            "colunas": dict(self.colunas),
            "casos_problema": asdict(self.casos_problema),
            "saida": saida_final,
            "relatorio": _relatorio_de(saida_final),
        }

    def para_json(self) -> str:
        """Transforma a ficha em texto JSON, para salvar ou mostrar.

        Recebe: nada.
        Devolve: o JSON com todos os campos, identado.
        Garante: acentos ficam legiveis ("endereço", nao "endere\\u00e7o").
        """
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def de_json(cls, texto: str) -> "Ficha":
        """Le uma ficha a partir de texto JSON.

        Recebe: o texto JSON (por exemplo, o que para_json() devolveu).
        Devolve: a Ficha.
        Garante: de_json(f.para_json()) == f; sem pedido, suposicoes ou confirmada,
                 usa "", [] e False; qualquer texto quebrado lanca FichaInvalida.
        """
        try:
            dados = json.loads(texto)
            if not isinstance(dados, dict):
                raise TypeError("a ficha precisa ser um objeto JSON")
            return cls(
                pedido=dados.get("pedido", ""),
                planilhas=[PlanilhaDaFicha(**p) for p in dados["planilhas"]],
                chave=dados["chave"],
                acao=dados["acao"],
                colunas=dados["colunas"],
                casos_problema=CasosProblema(**dados.get("casos_problema", {})),
                saida=dados["saida"],
                suposicoes=dados.get("suposicoes", []),
                confirmada=dados.get("confirmada", False),
            )
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as erro:
            raise FichaInvalida(type(erro).__name__) from erro
