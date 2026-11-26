"""Interface no navegador para o agente de automacao de planilhas.

Rodar (na raiz do projeto, com o .venv ligado):
    pip install -r requirements-interface.txt
    streamlit run interface.py

Abre em http://localhost:8501. A mesma sequencia do fluxograma, em uma tela:
pedido -> ficha (conferida e editavel) -> Revisor e Construtor -> execucao local -> conferencia final.
Peca opcional: o nucleo do projeto nao depende do Streamlit.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from src.agentes import orquestrador as O  # noqa: E402
from src.agentes.comum import llm as L  # noqa: E402
from src.contratos.ficha import CasosProblema, Ficha  # noqa: E402
from dados_exemplo import gerar_exemplos  # noqa: E402

PASTA = Path(os.environ.get("INTERFACE_PASTA", RAIZ / "saida" / "interface"))
BIBLIOTECA = PASTA / "biblioteca"
PEDIDO_EXEMPLO = "Completar os e-mails que estão faltando no cadastro, usando a planilha do RH, pela matrícula"

PASSOS = [
    ("1", "Pedido", "classificar, mascarar, verificar"),
    ("2", "Ficha", "6 respostas"),
    ("3", "Conferência humana", "corrigir a ficha"),
    ("4", "Revisor", "escrever testes sem ver código"),
    ("5", "Construtor", "montar o script e testar"),
    ("6", "Biblioteca", "armazenar o aprovado"),
    ("7", "Execução local", "execução do script"),
    ("8", "Conferência final", "PODE USAR ou NÃO USE"),
]
ETAPA_POR_FASE = {"inicio": 0, "ficha": 2, "criado": 6, "executado": 8}

st.set_page_config(page_title="Agente de automação de planilhas", page_icon="📊", layout="wide")
ss = st.session_state
ss.setdefault("fase", "inicio")
ss.setdefault("log", [])


# ------------------------------------------------------------------ apoio
def respostas_gravadas(origem: Path, destino: Path, saida: Path) -> list[str]:
    """Respostas gravadas do LLM (modo sem internet), na ordem: busca, ficha, testes, 2 tentativas."""
    import demo
    demo.ORIGEM, demo.DESTINO, demo.SAIDA = origem, destino, saida
    return demo.respostas_gravadas()


def nova_pasta() -> Path:
    pasta = PASTA / "execucoes" / datetime.now().strftime("%Y%m%d-%H%M%S")
    (pasta / "planilhas").mkdir(parents=True, exist_ok=True)
    return pasta


def colunas_de(raio) -> list[str]:
    return [c.nome for c in raio.colunas]


def anotar(tipo: str, titulo: str, linhas: list[str]) -> None:
    """Guarda um bloco do passo a passo (fica na tela depois de recarregar)."""
    ss.log.append({"tipo": tipo, "titulo": titulo, "linhas": linhas})


def mostrar_log() -> None:
    for bloco in ss.log:
        icone = {"ok": "✅", "erro": "❌", "info": "🔹"}.get(bloco["tipo"], "🔹")
        with st.expander(f"{icone} {bloco['titulo']}", expanded=False):
            for linha in bloco["linhas"]:
                st.markdown(linha)


def barra_lateral() -> None:
    atual = ETAPA_POR_FASE[ss.fase]
    with st.sidebar:
        st.markdown("### Fluxo")
        st.caption("Orquestrador: chama cada passo, em ordem.")
        for i, (num, nome, frase) in enumerate(PASSOS, start=1):
            if i == 7:
                st.divider()
                st.caption("Fase 2 · local")
            elif i == 1:
                st.caption("Fase 1")
            marca = "✅" if i <= atual else ("🟢" if nome in ("Ficha", "Revisor", "Construtor") else "⚪")
            st.markdown(f"{marca} **{num}. {nome}**  \n<span style='color:gray;font-size:0.85em'>{frase}</span>",
                        unsafe_allow_html=True)
        st.divider()
        st.caption("🟢 = consulta o LLM (Groq), só com dados mascarados")
        if st.button("Recomeçar", width="stretch"):
            for chave in list(ss.keys()):
                del ss[chave]
            st.rerun()


def classificar(pedido: str) -> dict[str, float] | None:
    arq = RAIZ / "modelos" / "classificador.json"
    if not arq.exists():
        return None
    from src.agentes.comum.classificador import NaiveBayes
    return NaiveBayes.carregar(arq).probabilidades(pedido)


# ------------------------------------------------------------------ etapa 1: pedido
def tela_pedido() -> None:
    st.subheader("1 · Pedido")
    pedido = st.text_area("O que precisa ser feito?", PEDIDO_EXEMPLO, height=90)
    fonte = st.radio("Planilhas", ["Usar planilhas de exemplo (valores inventados)", "Enviar planilhas"],
                     horizontal=True)
    up_origem = up_destino = None
    if fonte.startswith("Enviar"):
        c1, c2 = st.columns(2)
        up_origem = c1.file_uploader("Origem: de onde vêm os dados", type=["xlsx"])
        up_destino = c2.file_uploader("Destino: planilha que vai ser corrigida", type=["xlsx"])
    sem_internet = st.toggle("Sem internet (respostas gravadas do LLM)", value=False,
                             help="Para apresentar sem depender da rede. Só com as planilhas de exemplo.")

    if not st.button("Analisar pedido", type="primary"):
        return
    if fonte.startswith("Enviar") and not (up_origem and up_destino):
        st.error("Envie as duas planilhas primeiro.")
        return
    if sem_internet and fonte.startswith("Enviar"):
        st.error("O modo sem internet funciona só com as planilhas de exemplo.")
        return

    pasta = nova_pasta()
    if fonte.startswith("Usar"):
        gerar_exemplos.main(pasta / "planilhas")
        origem = pasta / "planilhas" / "basico" / "rh.xlsx"
        destino = pasta / "planilhas" / "basico" / "cadastro.xlsx"
    else:
        origem = pasta / "planilhas" / up_origem.name
        destino = pasta / "planilhas" / up_destino.name
        origem.write_bytes(up_origem.getvalue())
        destino.write_bytes(up_destino.getvalue())
    saida = pasta / f"{destino.stem}_completado.xlsx"

    with st.status("Analisando o pedido…", expanded=True) as status:
        st.write("**Classificar** · modelo local treinado pelo grupo")
        probs = classificar(pedido)
        if probs:
            classe = max(probs, key=probs.get)
            st.bar_chart(pd.Series(probs, name="probabilidade"), horizontal=True, height=160)
            if classe == "fora_do_escopo":
                status.update(label="Pedido fora do escopo", state="error")
                st.error("O sistema não faz esse tipo de pedido. Nenhuma chamada ao LLM foi feita.")
                return
            st.write(f"Tipo identificado: **{classe}**")

        st.write("**Mascarar** · na sua máquina, antes de qualquer envio")
        planilhas = {"origem": origem, "destino": destino}
        raio_x, amostras = O._extrair_raio_x_e_amostras(planilhas)

        st.write("**Verificar** · busca na biblioteca e criação da ficha pelo LLM")
        if sem_internet:
            llm = L.LLMFalso(respostas_gravadas(origem, destino, saida))
        else:
            try:
                llm = L.criar_llm_do_ambiente()
            except Exception as erro:  # noqa: BLE001 (mostra o motivo na tela)
                status.update(label="LLM indisponível", state="error")
                st.error(f"Não foi possível conectar ao LLM ({type(erro).__name__}). "
                         "Confira o .env ou ligue o modo sem internet.")
                return
        orq = O.Orquestrador(llm, BIBLIOTECA, pasta_trabalho=pasta / "tentativas")
        indice = orq._ler_indice()
        try:
            decisao = O._chamar_decidir(orq._llm, pedido, raio_x, indice)
            ficha = O._chamar_preencher(orq._llm, pedido, raio_x, amostras)
        except Exception as erro:  # noqa: BLE001 (mostra o motivo na tela)
            status.update(label="Falha ao consultar o LLM", state="error")
            st.error(f"{type(erro).__name__}. Tente de novo ou ligue o modo sem internet.")
            return
        for p in ficha.planilhas:
            p.arquivo = str(origem if p.rotulo == "origem" else destino)
        ficha.saida = str(saida)
        ficha.pedido = pedido
        status.update(label="Ficha pronta para conferência", state="complete")

    ss.update(fase="ficha", pasta=pasta, origem=origem, destino=destino, raio_x=raio_x, amostras=amostras,
              decisao=decisao, ficha=ficha, orq=orq, probs=probs, log=[])
    anotar("info", "Pedido: classificar, mascarar, verificar", [
        f"Tipo: **{max(probs, key=probs.get) if probs else '—'}**",
        f"Biblioteca: {len(indice)} script(s) aprovado(s) · {decisao.motivo}",
    ])
    st.rerun()


def mostrar_mascaramento() -> None:
    with st.expander("O que o LLM recebe: só a estrutura, com valores inventados", expanded=False):
        for rotulo, raio, amostra in zip(("Origem", "Destino"), ss.raio_x, ss.amostras):
            st.markdown(f"**{rotulo}** · {raio.total_linhas} linhas")
            st.dataframe(pd.DataFrame(amostra), hide_index=True, width="stretch")


# ------------------------------------------------------------------ etapas 2 e 3: ficha
def tela_ficha() -> None:
    st.subheader("2 · Ficha  ·  3 · Conferência humana")
    st.caption("O LLM transformou o pedido nestas 6 respostas. Confira e corrija antes de continuar.")
    mostrar_mascaramento()
    f: Ficha = ss.ficha
    col_o, col_d = colunas_de(ss.raio_x[0]), colunas_de(ss.raio_x[1])

    for s in f.suposicoes:
        st.warning(f"Suposição do LLM: {s}")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1. Planilhas**")
        st.write(f"Origem: `{Path(ss.origem).name}`  ·  Destino: `{Path(ss.destino).name}`")
        st.markdown("**2. Chave** (coluna que liga as duas)")
        k1, k2 = st.columns(2)
        ch_o = k1.selectbox("na origem", col_o, index=col_o.index(f.chave.get("origem")) if f.chave.get("origem") in col_o else 0)
        ch_d = k2.selectbox("no destino", col_d, index=col_d.index(f.chave.get("destino")) if f.chave.get("destino") in col_d else 0)
        st.markdown("**3. Ação**")
        acao = st.radio("ação", ["completar", "trocar"], index=0 if f.acao == "completar" else 1, horizontal=True,
                        label_visibility="collapsed",
                        captions=["preencher só o que está vazio", "substituir o valor existente"])
    with c2:
        st.markdown("**4. Colunas** (origem → destino)")
        tabela = pd.DataFrame([{"origem": a, "destino": b} for a, b in f.colunas.items()])
        tabela = st.data_editor(tabela, num_rows="dynamic", hide_index=True, width="stretch",
                                column_config={"origem": st.column_config.SelectboxColumn(options=col_o),
                                               "destino": st.column_config.SelectboxColumn(options=col_d)})
        st.markdown("**5. Casos-problema**")
        cp = f.casos_problema
        zeros = st.checkbox("0048213 e 48213 são a mesma chave", value=cp.zeros_na_chave)
        acento = st.checkbox("ignorar acentos e maiúsculas na chave", value=cp.ignorar_acento_e_caixa)
        repetida = st.selectbox("chave repetida na origem", ["nao_alterar", "primeiro"],
                                index=0 if cp.chave_repetida == "nao_alterar" else 1,
                                format_func={"nao_alterar": "não alterar (marcar para revisão)",
                                             "primeiro": "usar o primeiro valor"}.get)
        st.markdown("**6. Saída**")
        nome_saida = st.text_input("nome do arquivo", Path(f.saida).name)

    b1, b2, _ = st.columns([2, 1, 3])
    if b2.button("Cancelar"):
        ss.fase = "inicio"
        st.rerun()
    if not b1.button("Confirmar ficha e criar script", type="primary"):
        return

    f.chave = {"origem": ch_o, "destino": ch_d}
    f.acao = acao
    f.colunas = {str(r["origem"]): str(r["destino"]) for _, r in tabela.dropna().iterrows()}
    f.casos_problema = CasosProblema(chave_repetida=repetida, ignorar_acento_e_caixa=acento, zeros_na_chave=zeros)
    f.saida = str(Path(ss.pasta) / (nome_saida if nome_saida.endswith(".xlsx") else nome_saida + ".xlsx"))
    problemas = f.problemas()
    if problemas:
        for p in problemas:
            st.error(p)
        return
    anotar("ok", "Ficha conferida e confirmada", [
        f"Chave: `{ch_o}` → `{ch_d}` · Ação: **{acao}** · Colunas: "
        + ", ".join(f"`{a}` → `{b}`" for a, b in f.colunas.items())])
    criar_script(f)


# ------------------------------------------------------------------ etapas 4, 5 e 6
def criar_script(ficha: Ficha) -> None:
    orig = {n: getattr(O, n) for n in ("_chamar_decidir", "_chamar_preencher", "_chamar_escrever_testes",
                                       "_chamar_gerar_corpo", "_chamar_executar_testes")}
    volta = {"n": 0}

    def nomes_testes(texto: str) -> list[str]:
        return [ln[4:ln.index("(")] for ln in texto.splitlines() if ln.startswith("def test_")]

    with st.status("Revisor e Construtor trabalhando…", expanded=True) as status:
        def testes(llm, f, kit):
            st.write("**4 · Revisor** escreve os testes lendo só a ficha")
            t = orig["_chamar_escrever_testes"](llm, f, kit)
            nomes = nomes_testes(t)
            st.write(" · ".join(f"`{n}`" for n in nomes))
            anotar("info", "Revisor: testes escritos sem ver o código", [f"□ `{n}`" for n in nomes])
            return t

        def gerar(llm, f, descricoes, exemplo=None, aviso_anterior=None):
            volta["n"] += 1
            st.write(f"**5 · Construtor** monta o script · tentativa {volta['n']}")
            linhas = []
            if aviso_anterior:
                motivo = aviso_anterior.splitlines()[-1]
                st.write(f"↩︎ Retorno recebido (sem dados): {motivo}")
                linhas.append(f"Retorno recebido: {motivo}")
            corpo = orig["_chamar_gerar_corpo"](llm, f, descricoes, exemplo=exemplo, aviso_anterior=aviso_anterior)
            usadas = [d.nome for d in descricoes if d.nome + "(" in corpo]
            st.write("Ações: " + " → ".join(f"`{u}`" for u in usadas))
            linhas.append("Ações: " + " → ".join(f"`{u}`" for u in usadas))
            anotar("info", f"Construtor · tentativa {volta['n']}", linhas)
            return corpo

        def executar(script, testes_arq, tempo_limite=60):
            r = orig["_chamar_executar_testes"](script, testes_arq, max(tempo_limite, 300))
            falhos = {x.teste for x in r.falhas}
            linhas = [("✔ " if n not in falhos else "✘ ") + f"`{n}`"
                      for n in nomes_testes(Path(testes_arq).read_text(encoding="utf-8"))]
            if r.total == 0:
                motivo = r.falhas[0].tipo_erro if r.falhas else "sem testes"
                resumo = f"os testes não terminaram ({motivo})"
            else:
                resumo = f"{r.total - len(r.falhas)} de {r.total} testes passaram"
            st.write(f"Testes: **{resumo}**")
            anotar("ok" if r.passou else "erro", f"Testes da tentativa {volta['n']}: {resumo}", linhas)
            return r

        O._chamar_decidir = lambda *a, **k: ss.decisao
        O._chamar_preencher = lambda *a, **k: ficha
        O._chamar_escrever_testes = testes
        O._chamar_gerar_corpo = gerar
        O._chamar_executar_testes = executar
        try:
            resultado = ss.orq.fase1(ficha.pedido, {"origem": ss.origem, "destino": ss.destino}, lambda f: ficha)
        except Exception as erro:  # noqa: BLE001 (mostra o motivo na tela)
            status.update(label="Falha durante a criação", state="error")
            st.error(f"{type(erro).__name__}: tente de novo ou ligue o modo sem internet.")
            return
        finally:
            for nome, funcao in orig.items():
                setattr(O, nome, funcao)

        if resultado.situacao == "aprovado":
            status.update(label=f"Script aprovado em {resultado.voltas} tentativa(s)", state="complete")
            anotar("ok", "Biblioteca: script, testes e ficha armazenados",
                   [f"`{resultado.script.parent.name}/` · script.py · test_script.py · ficha.json"])
        else:
            status.update(label="Script reprovado: nenhuma saída foi entregue", state="error")
            anotar("erro", "Reprovado após 3 tentativas", resultado.historico)

    ss.update(fase="criado", resultado=resultado)
    st.rerun()


def tela_criado() -> None:
    r = ss.resultado
    if r.situacao != "aprovado":
        st.error("O script não passou nos testes em 3 tentativas. Ele foi bloqueado e nenhuma planilha foi alterada.")
        return
    st.success(f"Script aprovado em {r.voltas} tentativa(s) e armazenado na biblioteca.")
    st.subheader("7 · Execução local")
    st.caption("Daqui em diante, sem internet e sem IA: o script roda na máquina, nas planilhas reais.")
    if st.button("Executar script", type="primary"):
        rodada = subprocess.run([sys.executable, str(r.script)], capture_output=True, text=True,
                                encoding="utf-8", timeout=180)
        ss.update(fase="executado", saida_script=rodada.stdout + rodada.stderr)
        st.rerun()


# ------------------------------------------------------------------ etapas 7 e 8
def tela_executado() -> None:
    f: Ficha = ss.resultado.ficha
    saida = Path(f.saida)
    relatorio = saida.with_name(saida.stem + "_RELATORIO.xlsx")
    bloqueada = saida.with_name("NAO_USE_" + saida.name)
    arquivo = saida if saida.exists() else bloqueada

    st.subheader("8 · Conferência final")
    if not relatorio.exists():
        st.error("O relatório não foi gerado.")
        st.code(ss.saida_script)
        return
    abas = pd.read_excel(relatorio, sheet_name=None)
    veredito = str(abas["Resumo"].columns[1])
    if "PODE" in veredito.upper():
        st.success(f"## ✅ {veredito}")
    else:
        st.error(f"## ⛔ {veredito}")

    conf = abas["Conferência"].copy()
    conf.insert(0, "", conf["Resultado"].map(lambda v: "✅" if str(v).strip() == "passou" else "❌"))
    st.markdown("**As 4 garantias** (o script confere o próprio resultado antes de entregar)")
    st.dataframe(conf, hide_index=True, width="stretch")

    st.markdown("**Antes × depois**")
    antes = pd.read_excel(ss.destino, dtype=str)
    depois = pd.read_excel(arquivo, dtype=str) if arquivo.exists() else antes
    mudou = (antes.fillna("") != depois.fillna("")).reindex_like(depois).fillna(False)
    estilo = depois.style.apply(lambda _: mudou.map(lambda m: "background-color:#c6efce" if m else ""), axis=None)
    a1, a2 = st.columns(2)
    a1.caption("Destino original (intacto)")
    a1.dataframe(antes, hide_index=True, width="stretch")
    a2.caption("Planilha gerada (verde = alterado)")
    a2.dataframe(estilo, hide_index=True, width="stretch")

    achados = abas.get("Achados")
    if achados is not None and not achados.empty:
        pend = achados[achados["aplicado"] != True]  # noqa: E712 (coluna vem do Excel)
        if not pend.empty:
            st.markdown("**Para revisar** (o script não decide sozinho)")
            st.dataframe(pend[["linha", "chave", "coluna", "situacao", "mensagem"]], hide_index=True,
                         width="stretch")

    enviado = ss.orq.registro.texto_enviado()
    reais = [str(v) for v in pd.read_excel(ss.origem, dtype=str).stack().tolist()
             if len(str(v)) > 4 and str(v) in enviado]
    st.info(f"Valores reais enviados ao LLM: **{len(reais)}**")

    d1, d2 = st.columns(2)
    if arquivo.exists():
        d1.download_button("Baixar planilha gerada", arquivo.read_bytes(), file_name=arquivo.name)
    d2.download_button("Baixar relatório", relatorio.read_bytes(), file_name=relatorio.name)


# ------------------------------------------------------------------ tela
st.title("Agente de automação de planilhas")
st.caption("Do pedido em português a um script testado, que roda sem internet e confere o próprio resultado.")
barra_lateral()
if ss.log:
    with st.container():
        st.markdown("##### Passo a passo")
        mostrar_log()
if ss.fase == "inicio":
    tela_pedido()
elif ss.fase == "ficha":
    tela_ficha()
elif ss.fase == "criado":
    tela_criado()
else:
    tela_executado()
