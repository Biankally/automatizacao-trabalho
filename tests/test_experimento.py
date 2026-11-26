"""O experimento mede certo: com respostas corretas, as 10 tarefas passam; com uma acao errada, Pass cai."""

import importlib.util
import json
from pathlib import Path

from src.agentes.comum.llm import LLMFalso

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("experimento", RAIZ / "avaliacao" / "experimento.py")
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)

TROCAR = {"t02_trocar_email", "t08_trocar_setor"}


def respostas(t, modo, acao_errada=False):
    acao = "trocar" if t["id"] in TROCAR else "completar"
    colunas = [c for c in t["destino"][0] if c != t["chave"] and c in t["origem"][0]]
    ficha = {"planilhas": [{"rotulo": "origem", "arquivo": "o.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
                           {"rotulo": "destino", "arquivo": "d.xlsx", "aba": "Plan1", "linha_cabecalho": 1}],
             "chave": {"origem": t["origem"][0][0], "destino": t["chave"]}, "acao": acao,
             "colunas": {c: c for c in colunas},
             "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": t["id"] == "t06_acentos_maiusculas",
                                "zeros_na_chave": True}, "saida": "s.xlsx", "suposicoes": []}
    k = t["chave"]
    testes = ("```python\ndef test_basico_roda(tmp_path):\n"
              f"    o = criar_planilha(tmp_path, 'o.xlsx', {t['origem'][0]!r}, {t['origem'][1:2]!r})\n"
              f"    d = criar_planilha(tmp_path, 'd.xlsx', {t['destino'][0]!r}, {t['destino'][1:2]!r})\n"
              "    ex = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
              "    assert ex.ok\n\n"
              "def test_borda_relatorio(tmp_path):\n"
              f"    o = criar_planilha(tmp_path, 'o.xlsx', {t['origem'][0]!r}, {t['origem'][1:2]!r})\n"
              f"    d = criar_planilha(tmp_path, 'd.xlsx', {t['destino'][0]!r}, {t['destino'][1:2]!r})\n"
              "    ex = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
              "    assert ex.relatorio.exists()\n```")
    usar = ("trocar_coluna" if acao == "completar" else "completar_coluna") if acao_errada else f"{acao}_coluna"
    funcao = ("```python\ndef executar(config):\n    p = config['planilhas']\n"
              "    o = ler_planilha('origem', p['origem']['arquivo'], p['origem']['aba'], p['origem']['linha_cabecalho'])\n"
              "    d = ler_planilha('destino', p['destino']['arquivo'], p['destino']['aba'], p['destino']['linha_cabecalho'])\n"
              "    r = iniciar('x', o, d)\n"
              "    pares = casar_por_chave(r, o, config['chave']['origem'], d, config['chave']['destino'], config['casos_problema'])\n"
              f"    for a, b in config['colunas'].items():\n        {usar}(r, pares, a, b)\n"
              "    return finalizar(r, pares, config['saida'], config['relatorio'])\n```")
    busca = '{"reaproveitar": null, "parecido": null, "motivo": "vazio"}'
    seq = [busca, json.dumps(ficha)] + ([testes] if modo == "dois_agentes" else []) + [funcao]
    return seq


def test_gabaritos_coerentes_com_o_sistema(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "PASTA", tmp_path)
    for t in E.TAREFAS:
        r = E.rodar_tarefa(LLMFalso(respostas(t, "dois_agentes")), t, "dois_agentes")
        assert r["exec"] and r["pass"], (t["id"], r)


def test_sabotagem_acao_errada_derruba_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "PASTA", tmp_path)
    t = next(x for x in E.TAREFAS if x["id"] == "t09_nao_sobrescrever")
    r = E.rodar_tarefa(LLMFalso(respostas(t, "um_agente", acao_errada=True)), t, "um_agente")
    assert r["exec"] and not r["pass"] and r["diferencas"] == ["1.Email"]
