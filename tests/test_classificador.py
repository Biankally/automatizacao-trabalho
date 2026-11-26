"""Testes do classificador de intencao (src/agentes/comum/classificador.py).

O classificador e um modelo Naive Bayes treinado do zero, em Python puro.
Aqui provamos que ele aprende, que as metricas estao certas (conferidas a mao)
e que a avaliacao percebe quando o modelo e sabotado.
"""

import json

import pytest

from src.agentes.comum import classificador as C

TREINO = [
    ("completar o email vazio com o do rh", "completar"),
    ("preencha os telefones que faltam", "completar"),
    ("complete o cpf onde estiver em branco", "completar"),
    ("atualize o email com o do rh", "trocar"),
    ("substitua o telefone pelo da base nova", "trocar"),
    ("corrija o cargo usando a planilha do rh", "trocar"),
    ("faca um grafico das vendas", "fora_do_escopo"),
    ("some a coluna de valores", "fora_do_escopo"),
    ("apague as linhas repetidas", "fora_do_escopo"),
]


# ---------- tokenizar ----------

def test_tokenizar_v1_so_separa_palavras():
    assert C.tokenizar("Preencha os E-mails!", C.CONFIG_V1) == ["preencha", "os", "e", "mails"]


def test_tokenizar_v2_tira_acento_stopwords_e_corta_sufixo():
    tokens = C.tokenizar("Atualizá os endereços da planilha", C.CONFIG_V2)
    assert "os" not in tokens and "da" not in tokens            # stopwords
    assert "atualiz" in tokens                                    # sem acento e sem sufixo
    assert any(t.startswith("endereco") or t.startswith("enderec") for t in tokens)


def test_tokenizar_v2_cria_bigramas():
    tokens = C.tokenizar("onde estiver vazio", C.CONFIG_V2)
    assert any("_" in t for t in tokens)


# ---------- treinar e prever ----------

def test_aprende_exemplos_simples():
    m = C.NaiveBayes(C.CONFIG_V1).treinar(TREINO)
    assert m.prever("preencha o email que falta") == "completar"
    assert m.prever("substitua o email pelo do rh") == "trocar"
    assert m.prever("faca um grafico") == "fora_do_escopo"


def test_probabilidades_somam_um():
    m = C.NaiveBayes(C.CONFIG_V2).treinar(TREINO)
    p = m.probabilidades("complete o telefone")
    assert set(p) == {"completar", "trocar", "fora_do_escopo"}
    assert abs(sum(p.values()) - 1) < 1e-9


def test_palavra_nunca_vista_nao_quebra():
    m = C.NaiveBayes(C.CONFIG_V1).treinar(TREINO)
    assert m.prever("xyzzy qwerty") in m.classes


def test_prever_sem_treinar_da_erro():
    with pytest.raises(C.ModeloNaoTreinado):
        C.NaiveBayes(C.CONFIG_V1).prever("oi")


def test_salvar_e_carregar_da_o_mesmo_resultado(tmp_path):
    m = C.NaiveBayes(C.CONFIG_V2).treinar(TREINO)
    arq = tmp_path / "modelo.json"
    m.salvar(arq)
    m2 = C.NaiveBayes.carregar(arq)
    for texto, _ in TREINO:
        assert m2.probabilidades(texto) == pytest.approx(m.probabilidades(texto))
    assert json.loads(arq.read_text(encoding="utf-8"))["config"]["bigramas"] is True


# ---------- metricas (conferidas a mao) ----------

REAL = ["a", "a", "a", "b", "b", "c"]
PREV = ["a", "a", "b", "b", "c", "c"]


def test_acuracia():
    assert C.acuracia(REAL, PREV) == pytest.approx(4 / 6)


def test_matriz_de_confusao():
    m = C.matriz_confusao(REAL, PREV, ["a", "b", "c"])
    assert m == {"a": {"a": 2, "b": 1, "c": 0}, "b": {"a": 0, "b": 1, "c": 1}, "c": {"a": 0, "b": 0, "c": 1}}


def test_precisao_recall_f1_por_classe():
    r = C.relatorio(REAL, PREV, ["a", "b", "c"])
    assert r["por_classe"]["a"]["precisao"] == pytest.approx(1.0)          # 2 de 2 previstos
    assert r["por_classe"]["a"]["recall"] == pytest.approx(2 / 3)          # 2 de 3 reais
    assert r["por_classe"]["a"]["f1"] == pytest.approx(0.8)
    assert r["por_classe"]["b"]["precisao"] == pytest.approx(0.5)
    assert r["por_classe"]["c"]["recall"] == pytest.approx(1.0)
    media = (0.8 + 0.5 + 2 / 3) / 3
    assert r["f1_macro"] == pytest.approx(media)


def test_classe_nunca_prevista_tem_precisao_zero_sem_quebrar():
    r = C.relatorio(["a", "b"], ["a", "a"], ["a", "b"])
    assert r["por_classe"]["b"]["precisao"] == 0.0 and r["por_classe"]["b"]["f1"] == 0.0


# ---------- base de dados ----------

def test_bases_nao_se_misturam():
    """Nenhum pedido do teste pode estar no treino (senao a metrica mente)."""
    teste = {C.normalizar(t) for t, _ in C.carregar_base("teste")}
    for nome in ("treino_v1", "treino_v3"):
        treino = {C.normalizar(t) for t, _ in C.carregar_base(nome)}
        assert not (teste & treino), f"pedidos repetidos entre teste e {nome}"


def test_bases_tem_as_tres_classes():
    for nome in ("treino_v1", "treino_v3", "teste"):
        assert {r for _, r in C.carregar_base(nome)} == set(C.CLASSES)


def test_base_ampliada_e_maior():
    assert len(C.carregar_base("treino_v3")) > 3 * len(C.carregar_base("treino_v1"))


# ---------- sabotagem ----------

def test_sabotagem_rotulos_embaralhados_derrubam_a_acuracia():
    """Treinar com respostas trocadas tem que piorar o modelo: prova que a metrica mede algo."""
    treino = C.carregar_base("treino_v3")
    teste = C.carregar_base("teste")
    bom = C.avaliar(C.NaiveBayes(C.CONFIG_V2).treinar(treino), teste)
    rotulos = [r for _, r in treino]
    girados = rotulos[1:] + rotulos[:1]
    ruim = C.avaliar(C.NaiveBayes(C.CONFIG_V2).treinar(list(zip([t for t, _ in treino], girados))), teste)
    assert ruim["acuracia"] < bom["acuracia"] - 0.2


def test_sabotagem_metrica_acusa_previsao_constante():
    teste = C.carregar_base("teste")
    reais = [r for _, r in teste]
    r = C.relatorio(reais, ["completar"] * len(reais), C.CLASSES)
    assert r["f1_macro"] < 0.4


# ---------- graficos ----------

def test_graficos_mostram_as_tres_versoes(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("graficos", C.RAIZ / "avaliacao" / "graficos.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    teste = C.carregar_base("teste")
    resultados = []
    for nome, base, cfg in [("v1", "treino_v1", C.CONFIG_V1), ("v3", "treino_v3", C.CONFIG_V2)]:
        treino = C.carregar_base(base)
        r = C.avaliar(C.NaiveBayes(cfg).treinar(treino), teste)
        resultados.append({"versao": nome, "n_treino": len(treino), "n_teste": len(teste), **r})
    html = g.pagina(resultados)
    assert html.startswith("<!DOCTYPE html>") and html.count("<svg") == 4    # barras + 2 matrizes + F1
    assert "v1" in html and "v3" in html
