"""Classificador de intencao: um modelo Naive Bayes treinado do zero, em Python puro.

Le o pedido e diz o tipo: "completar", "trocar" ou "fora_do_escopo".
Roda local, sem internet e sem LLM. E o primeiro modelo treinado pelo grupo.

Como funciona (Naive Bayes multinomial):
1. Treino: conta quantas vezes cada palavra aparece em cada classe.
2. Previsao: para cada classe, soma log P(classe) + log P(palavra | classe) de cada palavra.
   Ganha a classe com a maior soma. Palavra nunca vista recebe uma contagem pequena
   (suavizacao de Laplace, o "alfa"), para nao zerar a conta.

Tambem traz as metricas (acuracia, precisao, recall, F1, matriz de confusao)
e a leitura das bases de pedidos em avaliacao/pedidos/.

Camada 4: so biblioteca padrao.
"""

from __future__ import annotations

import json
import math
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

CLASSES = ["completar", "trocar", "fora_do_escopo"]
RAIZ = Path(__file__).resolve().parents[3]
PASTA_BASES = RAIZ / "avaliacao" / "pedidos"

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "e", "em", "no",
    "na", "nos", "nas", "por", "pra", "para", "pelo", "pela", "pelos", "pelas", "com", "que", "se",
    "me", "eu", "voce", "isso", "esse", "essa", "este", "esta", "ao", "aos", "tem", "ter", "favor",
    "planilha", "planilhas", "coluna", "colunas", "linha", "linhas",
}
SUFIXOS = ("amentos", "imentos", "amento", "imento", "acoes", "acao", "mente", "ados", "idos",
           "ando", "endo", "indo", "ado", "ido", "ar", "er", "ir", "as", "es", "is", "os", "a", "e", "o", "s")

CONFIG_V1 = {"nome": "v1 inicial", "sem_acento": False, "stopwords": False, "radical": False,
             "bigramas": False, "alfa": 1.0}
CONFIG_V2 = {"nome": "v2 ajustado", "sem_acento": True, "stopwords": True, "radical": True,
             "bigramas": True, "alfa": None}          # None: alfa escolhido por validacao cruzada no treino


class ModeloNaoTreinado(Exception):
    """O modelo foi usado antes de treinar()."""


def normalizar(texto: str) -> str:
    """Minusculas, sem acento e com espacos simples. Usado para comparar pedidos."""
    sem = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    return " ".join(re.findall(r"[a-z0-9]+", sem))


def _radical(palavra: str) -> str:
    """Corta um sufixo comum ("atualizar" -> "atualiz"), mantendo pelo menos 4 letras."""
    for s in SUFIXOS:
        if palavra.endswith(s) and len(palavra) - len(s) >= 4:
            return palavra[: -len(s)]
    return palavra


def tokenizar(texto: str, config: dict) -> list[str]:
    """Quebra o texto em pedacos (tokens) segundo a configuracao da versao.

    Recebe: o texto e a configuracao (CONFIG_V1, CONFIG_V2...).
    Devolve: a lista de tokens.
    """
    base = texto.lower()
    if config.get("sem_acento"):
        base = "".join(c for c in unicodedata.normalize("NFD", base) if unicodedata.category(c) != "Mn")
    palavras = re.findall(r"[a-z0-9à-ÿ]+", base)
    if config.get("stopwords"):
        palavras = [p for p in palavras if p not in STOPWORDS]
    if config.get("radical"):
        palavras = [_radical(p) for p in palavras]
    tokens = list(palavras)
    if config.get("bigramas"):
        tokens += [f"{a}_{b}" for a, b in zip(palavras, palavras[1:])]
    return tokens


class NaiveBayes:
    """O modelo. treinar() aprende as contagens; prever() escolhe a classe."""

    def __init__(self, config: dict) -> None:
        self.config = dict(config)
        self.classes: list[str] = []
        self.priori: dict[str, float] = {}
        self.contagens: dict[str, dict[str, int]] = {}
        self.totais: dict[str, int] = {}
        self.vocabulario: set[str] = set()

    def treinar(self, exemplos: list[tuple[str, str]]) -> "NaiveBayes":
        """Aprende com os exemplos (texto, classe).

        Recebe: a lista de exemplos.
        Devolve: o proprio modelo, ja treinado.
        Garante: se o alfa da configuracao for None, escolhe o melhor alfa por
                 validacao cruzada usando SO os exemplos de treino.
        """
        if self.config.get("alfa") is None:
            self.config["alfa"] = escolher_alfa(exemplos, self.config)
        por_classe = Counter(c for _, c in exemplos)
        self.classes = sorted(por_classe)
        self.priori = {c: por_classe[c] / len(exemplos) for c in self.classes}
        self.contagens = {c: Counter() for c in self.classes}
        for texto, c in exemplos:
            self.contagens[c].update(tokenizar(texto, self.config))
        self.contagens = {c: dict(v) for c, v in self.contagens.items()}
        self.totais = {c: sum(v.values()) for c, v in self.contagens.items()}
        self.vocabulario = {t for v in self.contagens.values() for t in v}
        return self

    def _pontos(self, texto: str) -> dict[str, float]:
        if not self.classes:
            raise ModeloNaoTreinado("chame treinar() antes de prever()")
        alfa, v = self.config["alfa"], len(self.vocabulario) or 1
        tokens = tokenizar(texto, self.config)
        return {c: math.log(self.priori[c]) + sum(
            math.log((self.contagens[c].get(t, 0) + alfa) / (self.totais[c] + alfa * v)) for t in tokens)
            for c in self.classes}

    def probabilidades(self, texto: str) -> dict[str, float]:
        """Devolve a probabilidade de cada classe (somam 1)."""
        pontos = self._pontos(texto)
        maior = max(pontos.values())
        exps = {c: math.exp(p - maior) for c, p in pontos.items()}
        total = sum(exps.values())
        return {c: e / total for c, e in exps.items()}

    def prever(self, texto: str) -> str:
        """Devolve a classe mais provavel do pedido."""
        pontos = self._pontos(texto)
        return max(pontos, key=pontos.get)

    def salvar(self, caminho: Path | str) -> None:
        """Grava o modelo treinado em JSON (utf-8)."""
        dados = {"config": self.config, "classes": self.classes, "priori": self.priori,
                 "contagens": self.contagens}
        Path(caminho).write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: Path | str) -> "NaiveBayes":
        """Le um modelo gravado por salvar()."""
        dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
        m = cls(dados["config"])
        m.classes, m.priori, m.contagens = dados["classes"], dados["priori"], dados["contagens"]
        m.totais = {c: sum(v.values()) for c, v in m.contagens.items()}
        m.vocabulario = {t for v in m.contagens.values() for t in v}
        return m


def escolher_alfa(exemplos: list[tuple[str, str]], config: dict, opcoes=(0.05, 0.1, 0.3, 0.5, 1.0),
                  dobras: int = 5, semente: int = 7) -> float:
    """Escolhe o alfa com a maior acuracia media em validacao cruzada (so no treino)."""
    embaralhados = list(exemplos)
    random.Random(semente).shuffle(embaralhados)
    melhor, melhor_acc = opcoes[0], -1.0
    for alfa in opcoes:
        cfg = dict(config, alfa=alfa)
        accs = []
        for k in range(dobras):
            val = embaralhados[k::dobras]
            trein = [e for i, e in enumerate(embaralhados) if i % dobras != k]
            if not val or len({c for _, c in trein}) < 2:
                continue
            m = NaiveBayes(cfg).treinar(trein)
            accs.append(acuracia([c for _, c in val], [m.prever(t) for t, _ in val]))
        media = sum(accs) / len(accs) if accs else 0.0
        if media > melhor_acc:
            melhor, melhor_acc = alfa, media
    return melhor


# ---------- metricas ----------

def acuracia(reais: list[str], previstos: list[str]) -> float:
    """Fracao de acertos."""
    return sum(r == p for r, p in zip(reais, previstos)) / len(reais)


def matriz_confusao(reais: list[str], previstos: list[str], classes: list[str]) -> dict[str, dict[str, int]]:
    """matriz[real][previsto] = quantidade."""
    m = {r: {p: 0 for p in classes} for r in classes}
    for r, p in zip(reais, previstos):
        m[r][p] += 1
    return m


def relatorio(reais: list[str], previstos: list[str], classes: list[str]) -> dict:
    """Acuracia, precisao/recall/F1 por classe, medias macro e a matriz de confusao.

    precisao = dos que o modelo disse "X", quantos eram X
    recall   = dos que eram X, quantos o modelo achou
    F1       = media harmonica das duas (2*P*R / (P+R))
    """
    m = matriz_confusao(reais, previstos, classes)
    por = {}
    for c in classes:
        vp = m[c][c]
        previstos_c = sum(m[r][c] for r in classes)
        reais_c = sum(m[c].values())
        p = vp / previstos_c if previstos_c else 0.0
        r = vp / reais_c if reais_c else 0.0
        f = 2 * p * r / (p + r) if p + r else 0.0
        por[c] = {"precisao": p, "recall": r, "f1": f, "suporte": reais_c}
    return {
        "acuracia": acuracia(reais, previstos),
        "precisao_macro": sum(v["precisao"] for v in por.values()) / len(classes),
        "recall_macro": sum(v["recall"] for v in por.values()) / len(classes),
        "f1_macro": sum(v["f1"] for v in por.values()) / len(classes),
        "por_classe": por,
        "matriz": m,
    }


def avaliar(modelo: NaiveBayes, teste: list[tuple[str, str]]) -> dict:
    """Roda o modelo na base de teste e devolve o relatorio de metricas."""
    reais = [c for _, c in teste]
    return relatorio(reais, [modelo.prever(t) for t, _ in teste], CLASSES)


def carregar_base(nome: str) -> list[tuple[str, str]]:
    """Le avaliacao/pedidos/<nome>.json: lista de [texto, classe]."""
    dados = json.loads((PASTA_BASES / f"{nome}.json").read_text(encoding="utf-8"))
    return [(t, c) for t, c in dados]
