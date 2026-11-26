"""Experimento do agente, no padrao do SheetCopilot (NeurIPS 2023).

10 tarefas com gabarito, cada uma rodada pelo agente completo (Fase 1 + Fase 2), em dois modos:
- dois_agentes: Construtor + Revisor (ate 3 voltas)
- um_agente:   so o Construtor (sem testes), como linha de base

Metricas (definicoes do SheetCopilot, adaptadas):
- Exec: o script gerado roda sem erro e grava a saida (nao NAO_USE_).
- Pass: a planilha final bate EXATAMENTE com o gabarito (todas as celulas conferidas).
- Voltas: tentativas ate a aprovacao (so no modo dois_agentes).

Rodar (raiz do projeto, .env com o LLM):
    python avaliacao/experimento.py                 # os dois modos
    python avaliacao/experimento.py --modo dois_agentes
Grava: avaliacao/experimento_resultados.json e avaliacao/experimento.html (graficos).
Planilhas e scripts: saida/experimento/ (dados inventados).
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from openpyxl import Workbook, load_workbook  # noqa: E402

PASTA = RAIZ / "saida" / "experimento"

# Cada tarefa: pedido, planilhas (origem, destino), coluna-chave do destino e o gabarito
# do destino depois da execucao: {chave: {coluna: valor esperado}}.
TAREFAS = [
    {"id": "t01_completar_email", "pedido": "Completar os e-mails vazios do cadastro com os da planilha do RH, pela matrícula",
     "origem": [["Matricula", "Email"], ["1", "a@x.com"], ["2", "b@x.com"], ["3", "c@x.com"]],
     "destino": [["Matricula", "Email"], ["1", None], ["2", "b@x.com"], ["3", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": "a@x.com"}, "2": {"Email": "b@x.com"}, "3": {"Email": "c@x.com"}}},
    {"id": "t02_trocar_email", "pedido": "Atualizar o e-mail do cadastro com o do RH, pela matrícula, mesmo quando já estiver preenchido",
     "origem": [["Matricula", "Email"], ["1", "novo1@x.com"], ["2", "novo2@x.com"]],
     "destino": [["Matricula", "Email"], ["1", "velho1@x.com"], ["2", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": "novo1@x.com"}, "2": {"Email": "novo2@x.com"}}},
    {"id": "t03_completar_telefone", "pedido": "Preencher os telefones que faltam no cadastro usando a base do RH, ligando pelo CPF",
     "origem": [["CPF", "Telefone"], ["111", "61 90000-0001"], ["222", "61 90000-0002"]],
     "destino": [["CPF", "Nome", "Telefone"], ["111", "Ana", None], ["222", "Beto", None]],
     "chave": "CPF", "gabarito": {"111": {"Telefone": "61 90000-0001"}, "222": {"Telefone": "61 90000-0002"}}},
    {"id": "t04_zeros_a_esquerda", "pedido": "Completar o e-mail do cadastro com o do RH pela matrícula; no RH a matrícula tem zeros à esquerda",
     "origem": [["Matricula", "Email"], ["0048213", "ana@x.com"], ["0000007", "sete@x.com"]],
     "destino": [["Matricula", "Email"], ["48213", None], ["7", None]],
     "chave": "Matricula", "gabarito": {"48213": {"Email": "ana@x.com"}, "7": {"Email": "sete@x.com"}}},
    {"id": "t05_chave_repetida", "pedido": "Completar o e-mail do cadastro pelo RH, pela matrícula; se a matrícula aparecer repetida no RH com e-mails diferentes, não alterar",
     "origem": [["Matricula", "Email"], ["1", "um@x.com"], ["1", "outro@x.com"], ["2", "dois@x.com"]],
     "destino": [["Matricula", "Email"], ["1", None], ["2", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": None}, "2": {"Email": "dois@x.com"}}},
    {"id": "t06_acentos_maiusculas", "pedido": "Completar o setor do cadastro com o da planilha de lotação, pelo nome, ignorando acentos e maiúsculas",
     "origem": [["Nome", "Setor"], ["JOSÉ SILVA", "TI"], ["maria souza", "RH"]],
     "destino": [["Nome", "Setor"], ["jose silva", None], ["Maria Souza", None]],
     "chave": "Nome", "gabarito": {"jose silva": {"Setor": "TI"}, "Maria Souza": {"Setor": "RH"}}},
    {"id": "t07_duas_colunas", "pedido": "Completar e-mail e telefone que faltam no cadastro usando o RH, pela matrícula",
     "origem": [["Matricula", "Email", "Telefone"], ["1", "a@x.com", "61 1111-1111"], ["2", "b@x.com", "61 2222-2222"]],
     "destino": [["Matricula", "Email", "Telefone"], ["1", None, None], ["2", "b@x.com", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": "a@x.com", "Telefone": "61 1111-1111"},
                                       "2": {"Email": "b@x.com", "Telefone": "61 2222-2222"}}},
    {"id": "t08_trocar_setor", "pedido": "Trocar o setor do cadastro pelo setor atual da planilha de lotação, pela matrícula",
     "origem": [["Matricula", "Setor"], ["1", "Financeiro"], ["2", "Jurídico"]],
     "destino": [["Matricula", "Setor"], ["1", "Compras"], ["2", "Jurídico"]],
     "chave": "Matricula", "gabarito": {"1": {"Setor": "Financeiro"}, "2": {"Setor": "Jurídico"}}},
    {"id": "t09_nao_sobrescrever", "pedido": "Completar somente os e-mails em branco do cadastro com os do RH, pela matrícula, sem mexer nos que já existem",
     "origem": [["Matricula", "Email"], ["1", "rh1@x.com"], ["2", "rh2@x.com"]],
     "destino": [["Matricula", "Email"], ["1", "cadastro1@x.com"], ["2", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": "cadastro1@x.com"}, "2": {"Email": "rh2@x.com"}}},
    {"id": "t10_sem_par", "pedido": "Completar os e-mails do cadastro com os do RH pela matrícula; matrícula que não está no RH fica como está",
     "origem": [["Matricula", "Email"], ["1", "a@x.com"]],
     "destino": [["Matricula", "Email"], ["1", None], ["9", None]],
     "chave": "Matricula", "gabarito": {"1": {"Email": "a@x.com"}, "9": {"Email": None}}},
]


def gravar(caminho: Path, linhas: list[list]) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan1"
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)
    return caminho


def conferir(saida: Path, chave: str, gabarito: dict) -> tuple[bool, list[str]]:
    """Compara a planilha final com o gabarito. Devolve (passou, diferencas)."""
    ws = load_workbook(saida, data_only=True).worksheets[0]
    cab = [c.value for c in ws[1]]
    linhas = {str(r[cab.index(chave)]): r for r in ws.iter_rows(min_row=2, values_only=True)}
    difs = []
    for k, esperado in gabarito.items():
        linha = linhas.get(k)
        if linha is None:
            difs.append(f"{k}: linha sumiu")
            continue
        for col, valor in esperado.items():
            obtido = linha[cab.index(col)] if col in cab else "<coluna sumiu>"
            if (obtido or None) != (valor or None):
                difs.append(f"{k}.{col}")
    return not difs, difs


def rodar_tarefa(llm, tarefa: dict, modo: str) -> dict:
    """Roda Fase 1 + Fase 2 de uma tarefa e mede Exec, Pass e voltas."""
    from src.agentes.orquestrador import Orquestrador

    base = PASTA / modo / tarefa["id"]
    shutil.rmtree(base, ignore_errors=True)
    origem = gravar(base / "origem.xlsx", tarefa["origem"])
    destino = gravar(base / "destino.xlsx", tarefa["destino"])
    saida = base / "saida.xlsx"
    orq = Orquestrador(llm, base / "biblioteca", modo=modo, pasta_trabalho=base / "tentativas")

    def confirmar(ficha):
        for p in ficha.planilhas:                     # conferencia: corrige so os caminhos dos arquivos
            p.arquivo = str(origem if p.rotulo == "origem" else destino)
        ficha.saida = str(saida)
        return ficha

    r = {"tarefa": tarefa["id"], "modo": modo, "aprovado": False, "exec": False, "pass": False,
         "voltas": None, "erro": None, "diferencas": []}
    inicio = time.time()
    try:
        res = orq.fase1(tarefa["pedido"], {"origem": origem, "destino": destino}, confirmar)
        r["aprovado"] = res.situacao == "aprovado"
        r["voltas"] = res.voltas
        if res.script:
            rodada = subprocess.run([sys.executable, str(res.script)], capture_output=True, text=True,
                                    encoding="utf-8", timeout=180)
            r["exec"] = rodada.returncode == 0 and saida.exists()
            if r["exec"]:
                r["pass"], r["diferencas"] = conferir(saida, tarefa["chave"], tarefa["gabarito"])
            else:
                r["erro"] = "script falhou" if rodada.returncode else "saida NAO_USE_"
        else:
            r["erro"] = res.situacao
    except Exception as erro:  # noqa: BLE001 (uma tarefa que quebra conta como falha e o experimento segue)
        r["erro"] = type(erro).__name__
    r["segundos"] = round(time.time() - inicio, 1)
    return r


def resumo(resultados: list[dict], modo: str) -> dict:
    rs = [r for r in resultados if r["modo"] == modo]
    if not rs:
        return {}
    voltas = [r["voltas"] for r in rs if r["aprovado"] and r["voltas"]]
    return {"modo": modo, "n": len(rs),
            "exec": sum(r["exec"] for r in rs) / len(rs),
            "pass": sum(r["pass"] for r in rs) / len(rs),
            "voltas_media": round(sum(voltas) / len(voltas), 2) if voltas else None}


def pagina(resumos: list[dict], resultados: list[dict], modelo: str) -> str:
    nomes = {"dois_agentes": "Construtor + Revisor", "um_agente": "Só Construtor"}
    cores = {"dois_agentes": "#0a5cff", "um_agente": "#9aa3b2"}
    barras = ""
    for met, rot in (("exec", "Exec"), ("pass", "Pass")):
        barras += f'<div class="g"><h3>{rot}</h3>'
        for s in resumos:
            barras += (f'<div class="l"><span>{nomes[s["modo"]]}</span><div class="b"><i style="width:{s[met]*100:.0f}%;'
                       f'background:{cores[s["modo"]]}"></i></div><b>{s[met]:.0%}</b></div>')
        barras += "</div>"
    linhas = "".join(
        f'<tr><td>{html.escape(r["tarefa"])}</td><td>{nomes[r["modo"]]}</td><td>{"sim" if r["exec"] else "não"}</td>'
        f'<td>{"sim" if r["pass"] else "não"}</td><td>{r["voltas"] or "—"}</td>'
        f'<td>{html.escape(r["erro"] or ", ".join(r["diferencas"]) or "")}</td></tr>' for r in resultados)
    return f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8"><title>Experimento</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{margin:0;font:16px/1.5 system-ui,sans-serif;color:#111418}}main{{max-width:900px;margin:0 auto;padding:28px 18px}}
h1{{font-size:32px;margin:0}}.sub{{color:#5b6270}}.g{{margin:22px 0}}.l{{display:grid;grid-template-columns:190px 1fr 60px;gap:12px;align-items:center;margin:8px 0}}
.b{{background:#eef1f5;border-radius:6px;height:26px}}.b i{{display:block;height:100%;border-radius:6px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:6px 8px;border-bottom:1px solid #e3e7ee;text-align:left}}</style></head>
<body><main><h1>Experimento: {resumos[0]["n"]} tarefas com gabarito</h1>
<p class="sub">Modelo: {html.escape(modelo)} · Exec = o script roda e grava a saída · Pass = a planilha final bate com o gabarito</p>
{barras}<h2>Tarefa por tarefa</h2><table><tr><th>Tarefa</th><th>Modo</th><th>Exec</th><th>Pass</th><th>Voltas</th><th>Observação</th></tr>{linhas}</table>
</main></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Experimento do agente (Exec e Pass, com e sem Revisor).")
    ap.add_argument("--modo", choices=["dois_agentes", "um_agente", "ambos"], default="ambos")
    ap.add_argument("--tarefas", type=int, default=len(TAREFAS), help="quantas tarefas rodar (padrao: todas)")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    from src.agentes.comum.llm import criar_llm_do_ambiente
    import os
    llm = criar_llm_do_ambiente()
    modelo = os.environ.get("LLM_MODELO", "?")
    modos = ["dois_agentes", "um_agente"] if args.modo == "ambos" else [args.modo]
    resultados = []
    for modo in modos:
        for t in TAREFAS[: args.tarefas]:
            r = rodar_tarefa(llm, t, modo)
            resultados.append(r)
            print(f"{modo:<13} {t['id']:<24} exec={'S' if r['exec'] else 'N'} pass={'S' if r['pass'] else 'N'} "
                  f"voltas={r['voltas'] or '-'} {r['segundos']}s {r['erro'] or ''}")
    resumos = [resumo(resultados, m) for m in modos]
    (RAIZ / "avaliacao" / "experimento_resultados.json").write_text(
        json.dumps({"modelo": modelo, "resumos": resumos, "resultados": resultados}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    (RAIZ / "avaliacao" / "experimento.html").write_text(pagina(resumos, resultados, modelo), encoding="utf-8")
    print()
    for s in resumos:
        print(f"{s['modo']:<13} Exec {s['exec']:.0%}  Pass {s['pass']:.0%}  voltas médias {s['voltas_media']}")
    print("Gráficos: avaliacao/experimento.html")


if __name__ == "__main__":
    main()
