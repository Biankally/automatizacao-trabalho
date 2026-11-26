"""Execucao guiada do agente: do pedido em portugues a planilha pronta, passo a passo.

Rodar (na raiz do projeto, com o .venv ligado):
    python demo.py              # usa o LLM do .env; se falhar, usa as respostas gravadas
    python demo.py --offline    # respostas gravadas, sem internet
    python demo.py --direto     # nao espera Enter entre os passos

No fim, abre no navegador o painel saida/demo/painel.html (linha do tempo da execucao).
Usa so as planilhas inventadas de dados_exemplo/basico/.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if os.name == "nt":
    os.system("")                      # liga as cores no terminal do Windows

from openpyxl import load_workbook  # noqa: E402

from src.agentes import orquestrador as O  # noqa: E402
from src.agentes.comum import llm as L  # noqa: E402
from src.nucleo import disfarce  # noqa: E402
from dados_exemplo import gerar_exemplos  # noqa: E402
import rastro_phoenix as rastro  # noqa: E402

PEDIDO = "Completar os e-mails que estão faltando no cadastro, usando a planilha do RH, pela matrícula"
PASTA_DEMO = Path(os.environ.get("DEMO_PASTA", RAIZ / "saida" / "demo"))
ORIGEM = PASTA_DEMO / "planilhas" / "basico" / "rh.xlsx"
DESTINO = PASTA_DEMO / "planilhas" / "basico" / "cadastro.xlsx"
SAIDA = PASTA_DEMO / "cadastro_completado.xlsx"

AZ, VD, VM, AM, CI, NE, FIM = "\033[94m", "\033[92m", "\033[91m", "\033[93m", "\033[90m", "\033[1m", "\033[0m"
PASSOS: list[dict] = []
ESPERAR = True
ABRIR = True


def abrir(arquivo: Path) -> None:
    """Abre a planilha no programa padrao (Excel no Windows). Em outro sistema, so avisa."""
    if not ABRIR or not Path(arquivo).exists():
        return
    try:
        if os.name == "nt":
            os.startfile(str(arquivo))                      # noqa: S606 (abre no Excel)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(arquivo)], check=False)
    except OSError as erro:
        print(f"   {CI}(não consegui abrir {Path(arquivo).name}: {type(erro).__name__}){FIM}")


# ------------------------------------------------------------------ tela
def titulo(numero: int, nome: str, quem: str, frase: str) -> None:
    """Cabecalho grande de cada passo, e anota o passo para o painel."""
    cor = {"IA": VM, "Modelo": AZ, "Usuario": NE, "Codigo": VD}.get(quem, NE)
    print(f"\n{cor}{'━' * 64}{FIM}")
    rotulo = {"Usuario": "Usuário", "Codigo": "Código"}.get(quem, quem)
    print(f"{cor}{NE} PASSO {numero}  ·  {nome.upper()}{FIM}   {CI}[{rotulo}]{FIM}")
    print(f" {frase}")
    print(f"{cor}{'━' * 64}{FIM}")
    PASSOS.append({"n": numero, "nome": nome, "quem": quem, "frase": frase, "itens": [], "inicio": time.time()})


def item(texto: str, cor: str = "") -> None:
    """Uma linha de detalhe do passo (vai para a tela e para o painel)."""
    print(f"   {cor}{texto}{FIM if cor else ''}")
    if PASSOS:
        PASSOS[-1]["itens"].append(texto)


def pausa() -> None:
    if PASSOS:
        PASSOS[-1]["dur"] = time.time() - PASSOS[-1]["inicio"]
    if ESPERAR:
        input(f"\n   {CI}[Enter] para continuar{FIM}")


def barra(valor: float, largura: int = 24) -> str:
    cheio = round(valor * largura)
    return "█" * cheio + "░" * (largura - cheio)


# ------------------------------------------------------------------ respostas gravadas (sem internet)
def respostas_gravadas() -> list[str]:
    """O que o LLM responde em cada chamada, na ordem: busca, ficha, testes, funcao (2 voltas)."""
    busca = '{"reaproveitar": null, "parecido": null, "motivo": "nenhum script aprovado faz isso ainda"}'
    ficha = {
        "planilhas": [
            {"rotulo": "origem", "arquivo": str(ORIGEM), "aba": "Plan1", "linha_cabecalho": 1},
            {"rotulo": "destino", "arquivo": str(DESTINO), "aba": "Plan1", "linha_cabecalho": 1},
        ],
        "chave": {"origem": "Matricula", "destino": "Matricula"},
        "acao": "completar",
        "colunas": {"Email": "Email"},
        "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False,
                           "zeros_na_chave": True},
        "saida": str(SAIDA),
        "suposicoes": ["Matrículas com zeros à esquerda (ex.: 00123 e 123) são a mesma pessoa.",
                       "E-mail já preenchido com outro valor não deve ser trocado."],
    }
    testes = (
        "```python\n"
        "def test_basico_completa_email_vazio(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'a@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', None]])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert r.ok and not r.bloqueada\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'a@x.com'\n\n"
        "def test_borda_nao_troca_email_ja_preenchido(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'novo@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', 'velho@x.com']])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'velho@x.com'\n\n"
        "def test_borda_matricula_sem_par(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'a@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['2', None]])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert valor(r.saida, 'Matricula', '2', 'Email') is None\n"
        "    assert achados(r.relatorio, 'sem_par')\n"
        "```"
    )
    corpo = (
        "    p = config['planilhas']\n"
        "    origem = ler_planilha('origem', p['origem']['arquivo'], p['origem']['aba'], p['origem']['linha_cabecalho'])\n"
        "    destino = ler_planilha('destino', p['destino']['arquivo'], p['destino']['aba'], p['destino']['linha_cabecalho'])\n"
        "    registro = iniciar('completar_email', origem, destino)\n"
        "    pares = casar_por_chave(registro, origem, config['chave']['origem'], destino, config['chave']['destino'], config['casos_problema'])\n"
        "    for co, cd in config['colunas'].items():\n"
        "        {acao}(registro, pares, co, cd)\n"
        "    return finalizar(registro, pares, config['saida'], config['relatorio'])\n"
    )
    errada = "```python\ndef executar(config):\n" + corpo.replace("{acao}", "trocar_coluna") + "```"
    certa = "```python\ndef executar(config):\n" + corpo.replace("{acao}", "completar_coluna") + "```"
    return [busca, "Aqui está a ficha:\n```json\n" + json.dumps(ficha, ensure_ascii=False) + "\n```",
            testes, errada, certa]


# ------------------------------------------------------------------ narracao (embrulha as etapas do orquestrador)
def narrar() -> None:
    """Embrulha as funcoes do orquestrador para mostrar cada etapa na tela."""
    orig = {n: getattr(O, n) for n in ("_chamar_decidir", "_chamar_preencher", "_chamar_escrever_testes",
                                       "_chamar_gerar_corpo", "_chamar_executar_testes")}
    volta = {"n": 0}

    def decidir(llm, pedido, raio_x, indice):
        titulo(4, "Busca por script aprovado", "IA", "Consulta à biblioteca de scripts aprovados.")
        d = orig["_chamar_decidir"](llm, pedido, raio_x, indice)
        item(f"Biblioteca: {len(indice)} script(s) aprovado(s).")
        item(("→ Reaproveitar: " + str(d.reaproveitar)) if d.reaproveitar else "→ Criar um script novo.", AM)
        item(f"Motivo: {d.motivo}", CI)
        pausa()
        return d

    def preencher(llm, pedido, raio_x, amostras):
        titulo(5, "Ficha", "IA", "O pedido vira 6 respostas objetivas.")
        f = orig["_chamar_preencher"](llm, pedido, raio_x, amostras)
        item(f"1. Planilhas:  origem = RH   ·   destino = cadastro")
        item(f"2. Chave:      {f.chave.get('origem')} → {f.chave.get('destino')}")
        item(f"3. Ação:       {f.acao}")
        item(f"4. Colunas:    " + ", ".join(f"{a} → {b}" for a, b in f.colunas.items()))
        cp = f.casos_problema
        item(f"5. Casos:      zeros à esquerda = {'sim' if cp.zeros_na_chave else 'não'}; "
             f"chave repetida = {cp.chave_repetida}")
        item(f"6. Saída:      {Path(f.saida).name}")
        for s in f.suposicoes:
            item(f"   Suposição da IA: {s}", AM)
        pausa()
        return f

    def testes(llm, ficha, kit):
        titulo(7, "Revisor: escrita dos testes", "IA",
               "Segundo agente escreve testes a partir da ficha, sem acesso ao código.")
        t = orig["_chamar_escrever_testes"](llm, ficha, kit)
        for nome in [ln[4:ln.index("(")] for ln in t.splitlines() if ln.startswith("def test_")]:
            item(f"□ {nome}")
        pausa()
        return t

    def gerar(llm, ficha, descricoes, exemplo=None, aviso_anterior=None):
        volta["n"] += 1
        titulo(8, f"Construtor: montagem do script · tentativa {volta['n']}", "IA",
               "Combinação das 6 ações atômicas do catálogo.")
        if aviso_anterior:
            item(f"Retorno do Revisor (sem dados): {aviso_anterior.splitlines()[-1]}", AM)
        corpo = orig["_chamar_gerar_corpo"](llm, ficha, descricoes, exemplo=exemplo, aviso_anterior=aviso_anterior)
        usadas = [d.nome for d in descricoes if d.nome + "(" in corpo]
        item("Ações usadas: " + "  →  ".join(usadas), AZ)
        pausa()
        return corpo

    def executar(script, testes_arq, tempo_limite=60):
        titulo(9, f"Execução dos testes · tentativa {volta['n']}", "Codigo",
               "O pytest executa os testes do Revisor no script candidato.")
        r = orig["_chamar_executar_testes"](script, testes_arq, tempo_limite)
        falhos = {f.teste for f in r.falhas}
        texto = Path(testes_arq).read_text(encoding="utf-8")
        for nome in [ln[4:ln.index("(")] for ln in texto.splitlines() if ln.startswith("def test_")]:
            item(("✘ " if nome in falhos else "✔ ") + nome, VM if nome in falhos else VD)
        item(f"{r.total - len(r.falhas)} de {r.total} passaram.", VD if r.passou else VM)
        if not r.passou:
            item("→ Retorno ao Construtor.", AM)
        pausa()
        return r

    O._chamar_decidir = com_rastro("Busca no livro", "CHAIN", decidir)
    O._chamar_preencher = com_rastro("Ficha", "CHAIN", preencher)
    O._chamar_escrever_testes = com_rastro("Revisor · escreve testes", "AGENT", testes)
    O._chamar_gerar_corpo = com_rastro("Construtor · monta script", "AGENT", gerar)
    O._chamar_executar_testes = com_rastro("pytest · roda testes", "TOOL", executar)


def _resumo(valor) -> str:
    """Texto curto de um resultado, para o rastro."""
    if hasattr(valor, "para_json"):
        return valor.para_json()
    if hasattr(valor, "aviso"):
        return "todos passaram" if valor.passou else valor.aviso()
    if hasattr(valor, "motivo"):
        return f"reaproveitar={valor.reaproveitar} · {valor.motivo}"
    return str(valor)


def com_rastro(nome: str, tipo: str, funcao):
    """Embrulha uma etapa num trecho do Phoenix (sem efeito se o Phoenix estiver desligado)."""
    def embrulhada(*args, **kwargs):
        with rastro.etapa(nome, tipo) as span:
            resultado = funcao(*args, **kwargs)
            rastro.saida(span, _resumo(resultado))
            return resultado
    return embrulhada


# ------------------------------------------------------------------ planilha antes x depois
def tabela_emails(arquivo: Path) -> dict[str, str | None]:
    ws = load_workbook(arquivo, data_only=True).worksheets[0]
    cab = [c.value for c in ws[1]]
    im, ie, inome = cab.index("Matricula"), cab.index("Email"), cab.index("Nome")
    return {f"{r[im]} {r[inome]}": r[ie] for r in ws.iter_rows(min_row=2, values_only=True)}


# ------------------------------------------------------------------ o roteiro
def rodar(llm, modo: str) -> dict:
    """Executa a demonstracao inteira e devolve os dados para o painel."""
    shutil.rmtree(PASTA_DEMO, ignore_errors=True)
    PASTA_DEMO.mkdir(parents=True)
    PASSOS.clear()
    gerar_exemplos.main(PASTA_DEMO / "planilhas")

    titulo(1, "Pedido", "Usuario", "Pedido em linguagem natural e as duas planilhas.")
    item(f"“{PEDIDO}”", NE)
    item(f"Planilhas: {ORIGEM.name} (RH) e {DESTINO.name} (cadastro)", CI)
    item("Cadastro antes da execução: e-mails vazios.", AM)
    abrir(DESTINO)
    pausa()

    titulo(2, "Classificador", "Modelo", "Modelo treinado do zero identifica o tipo de pedido. Execução local.")
    arq_modelo = RAIZ / "modelos" / "classificador.json"
    classe = "completar"
    if arq_modelo.exists():
        from src.agentes.comum.classificador import NaiveBayes
        modelo = NaiveBayes.carregar(arq_modelo)
        with rastro.etapa("Classificador (modelo local)", "TOOL", PEDIDO) as span:
            probs = modelo.probabilidades(PEDIDO)
            rastro.saida(span, probs)
        classe = max(probs, key=probs.get)
        for c, p in sorted(probs.items(), key=lambda x: -x[1]):
            item(f"{c:<15} {barra(p)} {p:6.1%}", VD if c == classe else CI)
    else:
        item("(modelo ainda não treinado: rode python avaliacao/treinar_e_avaliar.py)", AM)
    if classe == "fora_do_escopo":
        item("→ Fora do escopo: execução encerrada sem chamar o LLM.", VM)
        pausa()
        return {"modo": modo, "situacao": "fora_do_escopo"}
    item(f"→ Tipo “{classe}”: dentro do escopo.", VD)
    pausa()

    titulo(3, "Observação da planilha", "Codigo", "A IA recebe só nomes de colunas e exemplos inventados. Nenhum dado real.")
    for arq, rot in ((ORIGEM, "RH"), (DESTINO, "cadastro")):
        rx = disfarce.raio_x(str(arq), "Plan1")
        item(f"{rot}: {rx.total_linhas} linhas", NE)
        for c in rx.colunas:
            item(f"   {c.nome:<10} {c.tipo:<6} {c.pct_vazios:3.0f}% vazio   ex.: {c.exemplo}", CI)
    pausa()

    orq = O.Orquestrador(llm, PASTA_DEMO / "livro", pasta_trabalho=PASTA_DEMO / "tentativas")

    def confirmar(ficha):
        titulo(6, "Conferência da ficha", "Usuario", "Nada segue sem confirmação.")
        for p in ficha.planilhas:                         # garante os arquivos da demo
            p.arquivo = str(ORIGEM if p.rotulo == "origem" else DESTINO)
        ficha.saida = str(SAIDA)
        if ESPERAR:
            resp = input(f"   {NE}Confirmar? [Enter = sim / n = cancelar] {FIM}").strip().lower()
            if resp == "n":
                return None
        item("✔ Ficha confirmada.", VD)
        pausa_sem_enter()
        return ficha

    antes = tabela_emails(DESTINO)
    resultado = orq.fase1(PEDIDO, {"origem": ORIGEM, "destino": DESTINO}, confirmar)
    if resultado.situacao != "aprovado":
        titulo(10, "Resultado", "Codigo", f"Situação: {resultado.situacao}")
        for h in resultado.historico:
            item(h)
        pausa()
        return {"modo": modo, "situacao": resultado.situacao, "historico": resultado.historico}

    titulo(10, "Aprovação", "Codigo", "Script aprovado e salvo na biblioteca para reúso.")
    item(f"Tentativas: {resultado.voltas}", VD)
    item(f"Salvo em: biblioteca/{resultado.script.parent.name}", CI)
    pausa()

    titulo(11, "Fase 2 · Execução do script", "Codigo", "Sem IA e sem internet.")
    rodada = subprocess.run([sys.executable, str(resultado.script)], capture_output=True, text=True,
                            encoding="utf-8", timeout=120)
    for linha in rodada.stdout.strip().splitlines():
        item(linha, VD if "PODE USAR" in linha else "")
    pausa()

    titulo(12, "Antes × depois", "Codigo", "Só mudou o que devia. Original intacto.")
    depois = tabela_emails(SAIDA) if SAIDA.exists() else {}
    linhas = []
    for pessoa, valor_antes in antes.items():
        valor_depois = depois.get(pessoa)
        if valor_antes == valor_depois:
            estado = "pendência: já tinha outro e-mail" if valor_antes and "antigo" in str(valor_antes) else \
                ("sem par no RH" if valor_antes is None else "igual")
            cor = AM if "pend" in estado or "sem par" in estado else CI
        else:
            estado, cor = "completado", VD
        item(f"{pessoa:<24} {str(valor_antes or '—'):<28} → {str(valor_depois or '—'):<28} {estado}", cor)
        linhas.append({"pessoa": pessoa, "antes": valor_antes, "depois": valor_depois, "estado": estado})
    relatorio = SAIDA.with_name(SAIDA.stem + "_RELATORIO.xlsx")
    item("Planilha final (cores indicam as mudanças) e relatório (Resumo, Conferência, Achados).", AM)
    abrir(SAIDA)
    abrir(relatorio)
    pausa()

    enviado = orq.registro.texto_enviado()
    vazados = [v for v in tabela_emails(ORIGEM).values() if v and v in enviado]
    return {"modo": modo, "situacao": "aprovado", "voltas": resultado.voltas, "linhas": linhas,
            "vazados": len(vazados), "chamadas": enviado.count("[") or None,
            "resumo": rodada.stdout.strip(), "relatorio": str(SAIDA.with_name(SAIDA.stem + "_RELATORIO.xlsx"))}


def pausa_sem_enter() -> None:
    if PASSOS:
        PASSOS[-1]["dur"] = time.time() - PASSOS[-1]["inicio"]


# ------------------------------------------------------------------ painel HTML
def painel(dados: dict) -> Path:
    """Grava saida/demo/painel.html: linha do tempo dos passos + antes x depois."""
    cor = {"IA": "#e6261f", "Modelo": "#0a5cff", "Usuario": "#111418", "Codigo": "#00a05a"}
    cartoes = "".join(
        f'<li style="--c:{cor.get(p["quem"], "#111418")}"><div class="n">{p["n"]}</div><div><h3>{html.escape(p["nome"])}'
        f' <small>{html.escape(p["quem"].replace("Usuario", "Usuário").replace("Codigo", "Código"))} · '
        f'{p.get("dur", 0):.1f}s</small></h3>'
        f'<p>{html.escape(p["frase"])}</p><pre>{html.escape(chr(10).join(p["itens"]))}</pre></div></li>'
        for p in PASSOS)
    linhas = "".join(
        f'<tr class="{ "ok" if l["estado"] == "completado" else "pend" if "pend" in l["estado"] or "sem par" in l["estado"] else ""}">'
        f'<td>{html.escape(l["pessoa"])}</td><td>{html.escape(str(l["antes"] or "—"))}</td>'
        f'<td>{html.escape(str(l["depois"] or "—"))}</td><td>{html.escape(l["estado"])}</td></tr>'
        for l in dados.get("linhas", []))
    completados = sum(1 for l in dados.get("linhas", []) if l["estado"] == "completado")
    modo = "LLM real" if dados["modo"] == "real" else "respostas gravadas"
    doc = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Painel da demonstração</title>
<style>body{{margin:0;font:16px/1.5 system-ui,sans-serif;color:#111418;background:#fff}}main{{max-width:980px;margin:0 auto;padding:28px 18px}}
h1{{font-size:34px;margin:0}}.sub{{color:#5b6270;margin:4px 0 20px}}.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:26px}}
.kpi{{border:2px solid #e3e7ee;border-radius:12px;padding:12px 16px}}.kpi b{{display:block;font-size:30px;line-height:1.1}}.kpi span{{color:#5b6270;font-size:14px}}
ol{{list-style:none;padding:0;margin:0;border-left:4px solid #e3e7ee}}li{{display:flex;gap:14px;margin:0 0 14px -18px}}
.n{{flex:none;width:32px;height:32px;border-radius:50%;background:var(--c);color:#fff;font-weight:800;display:grid;place-items:center}}
h3{{margin:2px 0 0;font-size:18px}}h3 small{{color:#5b6270;font-weight:500;font-size:13px}}li p{{margin:2px 0 6px;color:#5b6270}}
pre{{margin:0;background:#f3f5f8;border-left:4px solid var(--c);border-radius:6px;padding:8px 12px;white-space:pre-wrap;font-size:13px}}
table{{border-collapse:collapse;width:100%;font-size:14px}}td,th{{padding:7px 8px;border-bottom:1px solid #e3e7ee;text-align:left}}
tr.ok td{{background:#e5f4e4}}tr.pend td{{background:#f9eeda}}h2{{margin:30px 0 10px}}</style></head><body><main>
<h1>Do pedido à planilha pronta</h1><p class="sub">Execução de {time.strftime('%d/%m/%Y %H:%M')} · modo: {modo}</p>
<div class="kpis"><div class="kpi"><b>{html.escape(dados['situacao'])}</b><span>resultado</span></div>
<div class="kpi"><b>{dados.get('voltas', '—')}</b><span>tentativa(s) até passar nos testes</span></div>
<div class="kpi"><b>{completados}</b><span>e-mails completados</span></div>
<div class="kpi"><b>{dados.get('vazados', '—')}</b><span>dados reais enviados à IA</span></div></div>
<h2>Linha do tempo</h2><ol>{cartoes}</ol>
<h2>Planilha: antes × depois</h2><table><tr><th>Pessoa</th><th>Antes</th><th>Depois</th><th>O que aconteceu</th></tr>{linhas}</table>
</main></body></html>"""
    destino = PASTA_DEMO / "painel.html"
    destino.write_text(doc, encoding="utf-8")
    return destino


def main() -> None:
    global ESPERAR
    ap = argparse.ArgumentParser(description="Execução guiada do agente.")
    ap.add_argument("--offline", action="store_true", help="respostas gravadas, sem internet")
    ap.add_argument("--direto", action="store_true", help="não espera Enter entre os passos")
    ap.add_argument("--sem-navegador", action="store_true", help="não abre o painel no fim")
    ap.add_argument("--phoenix", action="store_true", help="manda o rastro para o Phoenix (localhost:6006)")
    ap.add_argument("--sem-planilhas", action="store_true", help="não abre as planilhas no Excel")
    args = ap.parse_args()
    global ABRIR
    ESPERAR = not args.direto
    ABRIR = not (args.sem_planilhas or args.direto)
    narrar()
    com_phoenix = args.phoenix and rastro.ligar()
    if args.phoenix and not com_phoenix:
        print(f"  {AM}Phoenix não instalado: seguindo sem rastro (pip install -r requirements-phoenix.txt).{FIM}")

    def executar_demo(llm, modo):
        if com_phoenix:
            llm = rastro.LLMRastreado(llm, os.environ.get("LLM_MODELO", "respostas-gravadas") if modo == "real"
                                      else "respostas-gravadas")
        with rastro.etapa("Demonstração · do pedido à planilha", "AGENT", PEDIDO) as span:
            dados = rodar(llm, modo)
            rastro.saida(span, {k: dados.get(k) for k in ("situacao", "voltas", "vazados")})
        return dados

    print(f"\n{NE}  AGENTE DE AUTOMAÇÃO DE PLANILHAS{FIM}")
    dados = None
    if not args.offline:
        try:
            llm = L.criar_llm_do_ambiente()
            print(f"  {CI}LLM: {os.environ.get('LLM_MODELO')}{FIM}")
            dados = executar_demo(llm, "real")
        except KeyboardInterrupt:
            raise
        except Exception as erro:                                     # noqa: BLE001 (troca para respostas gravadas, com aviso)
            print(f"\n  {AM}O LLM real não respondeu ({type(erro).__name__}). "
                  f"Execução refeita com respostas gravadas.{FIM}")
            dados = None
    if dados is not None and dados.get("situacao") not in ("aprovado", "fora_do_escopo"):
        print(f"\n  {AM}Script reprovado em 3 tentativas: bloqueado, nenhuma saída incorreta entregue.{FIM}")
        print(f"  {AM}Execução refeita com respostas gravadas.{FIM}")
        if ESPERAR:
            input(f"   {CI}[Enter] para continuar{FIM}")
        dados = None
    if dados is None:
        dados = executar_demo(L.LLMFalso(respostas_gravadas()), "offline")
    arquivo = painel(dados)
    print(f"\n{VD}{NE}  Painel: {arquivo}{FIM}\n")
    if com_phoenix:
        print(f"{AZ}{NE}  Rastro no Phoenix: http://localhost:6006 (projeto {rastro.PROJETO}){FIM}\n")
    if not args.sem_navegador:
        webbrowser.open(arquivo.as_uri())
        if com_phoenix:
            webbrowser.open("http://localhost:6006")


if __name__ == "__main__":
    main()
