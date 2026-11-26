"""Treina as 3 versoes do classificador e mede todas na MESMA base de teste.

| Versao        | Base de treino      | Configuracao                                   |
| v1 inicial    | treino_v1 (pequena) | so separa palavras; alfa = 1                   |
| v2 ajustado   | treino_v1 (pequena) | sem acento, sem stopwords, radical, bigramas;  |
|               |                     | alfa escolhido por validacao cruzada no treino |
| v3 ampliada   | treino_v3 (grande)  | igual a v2                                     |

Rodar: python avaliacao/treinar_e_avaliar.py
Grava: avaliacao/resultados.json e modelos/classificador.json (o modelo v3, usado pelo sistema).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes.comum import classificador as C  # noqa: E402

VERSOES = [
    ("v1 inicial", "treino_v1", C.CONFIG_V1),
    ("v2 ajustado", "treino_v1", C.CONFIG_V2),
    ("v3 base ampliada", "treino_v3", C.CONFIG_V2),
]


def main() -> None:
    teste = C.carregar_base("teste")
    resultados = []
    modelo_final = None
    for nome, base, config in VERSOES:
        treino = C.carregar_base(base)
        modelo = C.NaiveBayes(config).treinar(treino)
        r = C.avaliar(modelo, teste)
        erros = [{"pedido": t, "real": c, "previsto": modelo.prever(t)} for t, c in teste if modelo.prever(t) != c]
        resultados.append({"versao": nome, "base_treino": base, "n_treino": len(treino), "n_teste": len(teste),
                           "alfa": modelo.config["alfa"], **r, "erros": erros})
        modelo_final = modelo
    (RAIZ / "avaliacao" / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
    modelo_final.salvar(RAIZ / "modelos" / "classificador.json")

    print(f"Base de teste: {len(teste)} pedidos escritos a mao (nunca usados no treino)\n")
    print(f"{'Versao':<18}{'Treino':>7}{'Acuracia':>10}{'Precisao':>10}{'Recall':>8}{'F1':>7}")
    for r in resultados:
        print(f"{r['versao']:<18}{r['n_treino']:>7}{r['acuracia']:>10.1%}{r['precisao_macro']:>10.1%}"
              f"{r['recall_macro']:>8.1%}{r['f1_macro']:>7.1%}")
    final = resultados[-1]
    print(f"\nMatriz de confusao ({final['versao']}): linha = real, coluna = previsto")
    print(" " * 16 + "".join(f"{c[:10]:>12}" for c in C.CLASSES))
    for real in C.CLASSES:
        print(f"{real:<16}" + "".join(f"{final['matriz'][real][p]:>12}" for p in C.CLASSES))


if __name__ == "__main__":
    main()
