"""Desenha os graficos das metricas do classificador em Python puro (sem matplotlib).

Le avaliacao/resultados.json (gerado por treinar_e_avaliar.py) e grava
avaliacao/graficos.html: uma pagina com os graficos em SVG, que abre em qualquer navegador.

Rodar: python avaliacao/graficos.py
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

PASTA = Path(__file__).resolve().parent
METRICAS = [("acuracia", "Acurácia"), ("precisao_macro", "Precisão"), ("recall_macro", "Recall"), ("f1_macro", "F1")]
CORES_VERSAO = ["#9aa3b2", "#0a5cff", "#00a05a"]
CLASSES = [("completar", "Completar"), ("trocar", "Trocar"), ("fora_do_escopo", "Fora do escopo")]


def barras_agrupadas(resultados: list[dict]) -> str:
    """Grafico 1: as 4 metricas, uma barra por versao em cada grupo."""
    w, h, esq, base, topo = 760, 360, 50, 300, 30
    grupo = (w - esq - 20) / len(METRICAS)
    larg = grupo * 0.8 / len(resultados)
    partes = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Métricas por versão">']
    for p in (0, 25, 50, 75, 100):
        y = base - (base - topo) * p / 100
        partes.append(f'<line x1="{esq}" x2="{w-20}" y1="{y}" y2="{y}" stroke="#e3e7ee"/>'
                      f'<text x="{esq-8}" y="{y+4}" text-anchor="end" font-size="12" fill="#5b6270">{p}%</text>')
    for i, (chave, rotulo) in enumerate(METRICAS):
        x0 = esq + i * grupo + grupo * 0.1
        for j, r in enumerate(resultados):
            v = r[chave]
            alt = (base - topo) * v
            x = x0 + j * larg
            partes.append(f'<rect x="{x:.1f}" y="{base-alt:.1f}" width="{larg-4:.1f}" height="{alt:.1f}" rx="3" '
                          f'fill="{CORES_VERSAO[j]}"><title>{escape(r["versao"])}: {v:.1%}</title></rect>'
                          f'<text x="{x+(larg-4)/2:.1f}" y="{base-alt-6:.1f}" text-anchor="middle" font-size="12" '
                          f'font-weight="700" fill="#111418">{v*100:.0f}</text>')
        partes.append(f'<text x="{x0+grupo*0.4:.1f}" y="{base+22}" text-anchor="middle" font-size="14" '
                      f'font-weight="600" fill="#111418">{rotulo}</text>')
    partes.append("</svg>")
    return "".join(partes)


def matriz(resultado: dict) -> str:
    """Grafico 2: matriz de confusao (linha = real, coluna = previsto)."""
    m, n = resultado["matriz"], len(CLASSES)
    total_linha = {r: sum(m[r].values()) for r, _ in CLASSES}
    cel, esq, topo = 78, 120, 44
    w, h = esq + cel * n + 10, topo + cel * n + 30
    partes = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Matriz de confusão {escape(resultado["versao"])}">',
              f'<text x="{esq+cel*n/2}" y="14" text-anchor="middle" font-size="12" fill="#5b6270">previsto</text>']
    for j, (_, rot) in enumerate(CLASSES):
        partes.append(f'<text x="{esq+j*cel+cel/2}" y="{topo-10}" text-anchor="middle" font-size="12" '
                      f'fill="#111418">{rot.split()[0]}</text>')
    for i, (real, rot) in enumerate(CLASSES):
        partes.append(f'<text x="{esq-8}" y="{topo+i*cel+cel/2+4}" text-anchor="end" font-size="12" '
                      f'fill="#111418">{rot.split()[0]}</text>')
        for j, (prev, _) in enumerate(CLASSES):
            q = m[real][prev]
            frac = q / total_linha[real] if total_linha[real] else 0
            cor = f"rgba(0,160,90,{0.12+0.88*frac:.2f})" if i == j else f"rgba(230,38,31,{0.08+0.92*frac:.2f})"
            tinta = "#fff" if frac > 0.5 else "#111418"
            partes.append(f'<rect x="{esq+j*cel}" y="{topo+i*cel}" width="{cel-4}" height="{cel-4}" rx="6" fill="{cor}"/>'
                          f'<text x="{esq+j*cel+cel/2-2}" y="{topo+i*cel+cel/2+6}" text-anchor="middle" font-size="18" '
                          f'font-weight="800" fill="{tinta}">{q}</text>')
    partes.append(f'<text x="14" y="{topo+cel*n/2}" font-size="12" fill="#5b6270" '
                  f'transform="rotate(-90 14 {topo+cel*n/2})" text-anchor="middle">real</text></svg>')
    return "".join(partes)


def f1_por_classe(resultados: list[dict]) -> str:
    """Grafico 3: F1 de cada classe, em linhas horizontais por versao."""
    w, esq, linha = 760, 140, 26
    h = 20 + len(CLASSES) * (len(resultados) * linha + 18)
    partes = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="F1 por classe">']
    y = 14
    for chave, rot in CLASSES:
        partes.append(f'<text x="0" y="{y+linha*len(resultados)/2+4}" font-size="14" font-weight="600" '
                      f'fill="#111418">{rot}</text>')
        for j, r in enumerate(resultados):
            v = r["por_classe"][chave]["f1"]
            largura = (w - esq - 60) * v
            partes.append(f'<rect x="{esq}" y="{y}" width="{largura:.1f}" height="{linha-8}" rx="4" fill="{CORES_VERSAO[j]}"/>'
                          f'<text x="{esq+largura+8:.1f}" y="{y+linha-12}" font-size="12" font-weight="700" '
                          f'fill="#111418">{v*100:.0f}%</text>')
            y += linha
        y += 18
    partes.append("</svg>")
    return "".join(partes)


def pagina(resultados: list[dict]) -> str:
    """Monta a pagina HTML completa com os 3 graficos e a legenda."""
    legenda = "".join(f'<span><i style="background:{CORES_VERSAO[j]}"></i>{escape(r["versao"])} '
                      f'({r["n_treino"]} exemplos)</span>' for j, r in enumerate(resultados))
    tabela = "".join(f"<tr><td>{escape(r['versao'])}</td><td>{r['n_treino']}</td>"
                     + "".join(f"<td>{r[k]:.1%}</td>" for k, _ in METRICAS) + "</tr>" for r in resultados)
    primeira, ultima = resultados[0], resultados[-1]
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Métricas do classificador</title>
<style>body{{margin:0;font:16px/1.5 system-ui,sans-serif;color:#111418;background:#fff}}
main{{max-width:900px;margin:0 auto;padding:28px 18px}}h1{{font-size:34px;line-height:1.1;margin:0 0 6px}}
h2{{font-size:20px;margin:34px 0 8px}}.sub{{color:#5b6270;margin:0 0 16px}}svg{{width:100%;height:auto}}
.leg{{display:flex;flex-wrap:wrap;gap:8px 20px;font-size:14px}}.leg i{{display:inline-block;width:14px;height:14px;
border-radius:3px;margin-right:6px;vertical-align:-2px}}.par{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:18px}}
table{{border-collapse:collapse;width:100%;font-size:15px}}td,th{{padding:6px 8px;border-bottom:1px solid #e3e7ee;text-align:right}}
td:first-child,th:first-child{{text-align:left}}</style></head><body><main>
<h1>De {primeira['f1_macro']:.0%} para {ultima['f1_macro']:.0%} de F1 em 3 versões</h1>
<p class="sub">Classificador de intenção (Naive Bayes, treinado do zero). Todas as versões medidas na mesma
base de teste: {ultima['n_teste']} pedidos escritos à mão, nunca usados no treino.</p>
<div class="leg">{legenda}</div>
<h2>1. As 4 métricas por versão</h2>{barras_agrupadas(resultados)}
<h2>2. Matriz de confusão: antes e depois</h2><p class="sub">Verde = acertos (diagonal). Vermelho = confusões.</p>
<div class="par"><div><b>{escape(primeira['versao'])}</b>{matriz(primeira)}</div>
<div><b>{escape(ultima['versao'])}</b>{matriz(ultima)}</div></div>
<h2>3. F1 de cada tipo de pedido</h2>{f1_por_classe(resultados)}
<h2>Tabela</h2><table><tr><th>Versão</th><th>Treino</th>{''.join(f'<th>{r}</th>' for _, r in METRICAS)}</tr>{tabela}</table>
</main></body></html>"""


def main() -> None:
    resultados = json.loads((PASTA / "resultados.json").read_text(encoding="utf-8"))
    saida = PASTA / "graficos.html"
    saida.write_text(pagina(resultados), encoding="utf-8")
    print(f"Gráficos gravados em {saida}")


if __name__ == "__main__":
    main()
