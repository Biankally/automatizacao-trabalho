"""Teste termômetro: o sistema inteiro, do pedido ao script rodando.

Enquanto alguma peça não existir, este teste é PULADO (aparece como "skipped").
Quando todas existirem, ele roda o caminho completo com o LLM falso:

  Fase 1: pedido -> busca -> ficha -> confirmação -> testes do Revisor ->
          função do Construtor -> script montado -> pytest -> script aprovado
  Fase 2: roda o script aprovado num processo separado (como a pessoa faria)
          e confere a planilha de saída célula por célula.

Também confere a privacidade: nenhum valor das planilhas chega ao LLM.
Se este teste passa, o sistema executa de ponta a ponta.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

orquestrador = pytest.importorskip("src.agentes.orquestrador", reason="orquestrador ainda não existe")
llm_mod = pytest.importorskip("src.agentes.comum.llm", reason="llm.py ainda não existe")
openpyxl = pytest.importorskip("openpyxl")

# Valores que NUNCA podem aparecer no que foi enviado ao LLM (RN-02).
EMAILS_REAIS = ["ana.silva@exemplo.com", "bruno.costa@exemplo.com"]


def _planilha(caminho: Path, linhas: list[list]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan1"
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)
    return caminho


def _respostas_do_llm(origem: Path, destino: Path, saida: Path) -> list[str]:
    """O que um LLM devolveria em cada chamada, na ordem do fluxo (seção 5 da Estrutura)."""
    busca = '{"reaproveitar": null, "parecido": null, "motivo": "nenhum script aprovado serve"}'
    ficha = {
        "planilhas": [
            {"rotulo": "origem", "arquivo": str(origem), "aba": "Plan1", "linha_cabecalho": 1},
            {"rotulo": "destino", "arquivo": str(destino), "aba": "Plan1", "linha_cabecalho": 1},
        ],
        "chave": {"origem": "Matricula", "destino": "Matricula"},
        "acao": "completar",
        "colunas": {"Email": "Email"},
        "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False,
                           "zeros_na_chave": True},
        "saida": str(saida),
        "suposicoes": ["Matricula 0048213 e 48213 sao a mesma pessoa."],
    }
    # Resposta "suja": texto antes e crases, como um LLM real costuma fazer.
    ficha_suja = "Aqui esta a ficha:\n```json\n" + json.dumps(ficha) + "\n```"
    testes = (
        "```python\n"
        "def test_basico_completa_vazio(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'a@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', None]])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert r.ok and not r.bloqueada\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'a@x.com'\n"
        "\n"
        "def test_borda_nao_sobrescreve_preenchido(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'novo@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', 'velho@x.com']])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'velho@x.com'\n"
        "    assert achados(r.relatorio, 'diferente')\n"
        "```"
    )
    funcao = (
        "```python\n"
        "def executar(config):\n"
        "    p = config['planilhas']\n"
        "    origem = ler_planilha('origem', p['origem']['arquivo'], p['origem']['aba'], p['origem']['linha_cabecalho'])\n"
        "    destino = ler_planilha('destino', p['destino']['arquivo'], p['destino']['aba'], p['destino']['linha_cabecalho'])\n"
        "    registro = iniciar('completar_email', origem, destino)\n"
        "    pares = casar_por_chave(registro, origem, config['chave']['origem'], destino, config['chave']['destino'], config['casos_problema'])\n"
        "    for coluna_origem, coluna_destino in config['colunas'].items():\n"
        "        completar_coluna(registro, pares, coluna_origem, coluna_destino)\n"
        "    return finalizar(registro, pares, config['saida'], config['relatorio'])\n"
        "```"
    )
    return [busca, ficha_suja, testes, funcao]


def test_ponta_a_ponta_criar_aprovar_e_rodar(tmp_path):
    origem = _planilha(tmp_path / "rh.xlsx", [
        ["Matricula", "Email"],
        ["0048213", EMAILS_REAIS[0]],
        ["0051007", EMAILS_REAIS[1]],
    ])
    destino = _planilha(tmp_path / "cadastro.xlsx", [
        ["Matricula", "Nome", "Email"],
        ["48213", "Pessoa Um", None],                 # vazio -> deve ser completado
        ["51007", "Pessoa Dois", "ja@tem.com"],       # preenchido -> não muda (pendência)
        ["99999", "Pessoa Tres", None],               # sem par na origem
    ])
    saida = tmp_path / "saida" / "cadastro_completado.xlsx"
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()

    llm = llm_mod.LLMFalso(_respostas_do_llm(origem, destino, saida))
    orq = orquestrador.Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    # ---- Fase 1 ----
    resultado = orq.fase1("completar o email do cadastro com o do RH, pela matricula",
                          {"origem": origem, "destino": destino},
                          confirmar=lambda ficha: ficha)
    assert resultado.situacao == "aprovado", resultado.historico
    assert resultado.script.exists()
    indice = json.loads((aprovados / "indice.json").read_text(encoding="utf-8"))
    assert [i["nome"] for i in indice] == [resultado.script.parent.name]

    # ---- Privacidade: nenhum valor real foi ao LLM ----
    enviado = orq.registro.texto_enviado()
    for email in EMAILS_REAIS:
        assert email not in enviado

    # ---- Fase 2: a pessoa roda o script aprovado, num processo separado ----
    rodada = subprocess.run([sys.executable, str(resultado.script)], cwd=tmp_path,
                            capture_output=True, text=True, timeout=120)
    assert rodada.returncode == 0, rodada.stderr
    assert saida.exists(), "a saída não foi gravada (ou virou NAO_USE_)"

    ws = openpyxl.load_workbook(saida).worksheets[0]
    emails = {str(ws.cell(r, 1).value): ws.cell(r, 3).value for r in range(2, ws.max_row + 1)}
    assert emails["48213"] == EMAILS_REAIS[0]        # completado (zeros à esquerda ignorados)
    assert emails["51007"] == "ja@tem.com"           # não sobrescreveu
    assert emails["99999"] is None                   # sem par: ficou vazio


def test_ponta_a_ponta_corrige_na_segunda_volta(tmp_path):
    """O Construtor erra (usa 'trocar'), o Revisor pega, o aviso volta sem dados e a 2ª volta acerta."""
    origem = _planilha(tmp_path / "rh.xlsx", [["Matricula", "Email"], ["0048213", EMAILS_REAIS[0]]])
    destino = _planilha(tmp_path / "cadastro.xlsx", [["Matricula", "Email"], ["48213", None]])
    saida = tmp_path / "saida" / "out.xlsx"
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()

    respostas = _respostas_do_llm(origem, destino, saida)
    certa = respostas[3]
    errada = certa.replace("completar_coluna(", "trocar_coluna(")
    llm = llm_mod.LLMFalso(respostas[:3] + [errada, certa])
    orq = orquestrador.Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    resultado = orq.fase1("completar o email", {"origem": origem, "destino": destino},
                          confirmar=lambda ficha: ficha)
    assert resultado.situacao == "aprovado", resultado.historico
    assert resultado.voltas == 2

    # O pedido da 2ª volta ao Construtor diz QUAL teste falhou, mas sem os valores do teste.
    segunda_volta = llm.recebido[-1][-1]["content"]
    assert "test_borda_nao_sobrescreve_preenchido" in segunda_volta
    assert "velho@x.com" not in segunda_volta and "novo@x.com" not in segunda_volta


def test_ponta_a_ponta_reprova_depois_de_3_voltas(tmp_path):
    origem = _planilha(tmp_path / "rh.xlsx", [["Matricula", "Email"], ["1", "a@x.com"]])
    destino = _planilha(tmp_path / "cadastro.xlsx", [["Matricula", "Email"], ["1", None]])
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    respostas = _respostas_do_llm(origem, destino, tmp_path / "out.xlsx")
    errada = respostas[3].replace("completar_coluna(", "trocar_coluna(")
    llm = llm_mod.LLMFalso(respostas[:3] + [errada] * 3)
    orq = orquestrador.Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "trabalho")

    resultado = orq.fase1("completar", {"origem": origem, "destino": destino}, confirmar=lambda f: f)
    assert resultado.situacao == "reprovado" and resultado.voltas == 3
    assert not (aprovados / "indice.json").exists()    # nada reprovado vai para a biblioteca


def test_ponta_a_ponta_cancelado_quando_pessoa_recusa(tmp_path):
    origem = _planilha(tmp_path / "rh.xlsx", [["Matricula", "Email"], ["1", "a@x.com"]])
    destino = _planilha(tmp_path / "cadastro.xlsx", [["Matricula", "Email"], ["1", None]])
    llm = llm_mod.LLMFalso(_respostas_do_llm(origem, destino, tmp_path / "out.xlsx")[:2])
    orq = orquestrador.Orquestrador(llm, tmp_path, pasta_trabalho=tmp_path / "trabalho")
    resultado = orq.fase1("completar", {"origem": origem, "destino": destino}, confirmar=lambda f: None)
    assert resultado.situacao == "cancelado"


def test_ponta_a_ponta_reaproveita_script_aprovado(tmp_path):
    """2º pedido parecido: a busca indica o script aprovado e nenhum código novo é pedido ao LLM."""
    origem = _planilha(tmp_path / "rh.xlsx", [["Matricula", "Email"], ["0048213", EMAILS_REAIS[0]]])
    destino = _planilha(tmp_path / "cadastro.xlsx", [["Matricula", "Email"], ["48213", None]])
    aprovados = tmp_path / "aprovados"
    aprovados.mkdir()
    r1 = _respostas_do_llm(origem, destino, tmp_path / "s1" / "out.xlsx")
    orq = orquestrador.Orquestrador(llm_mod.LLMFalso(r1), aprovados, pasta_trabalho=tmp_path / "t1")
    primeiro = orq.fase1("completar o email", {"origem": origem, "destino": destino}, confirmar=lambda f: f)
    nome = primeiro.script.parent.name

    r2 = _respostas_do_llm(origem, destino, tmp_path / "s2" / "out.xlsx")
    busca = json.dumps({"reaproveitar": nome, "parecido": None, "motivo": "mesma tarefa"})
    llm = llm_mod.LLMFalso([busca, r2[1], r2[2]])          # sem resposta de código: não pode ser pedida
    orq2 = orquestrador.Orquestrador(llm, aprovados, pasta_trabalho=tmp_path / "t2")
    segundo = orq2.fase1("preencher emails vazios", {"origem": origem, "destino": destino}, confirmar=lambda f: f)
    assert segundo.situacao == "aprovado" and segundo.voltas == 1
    assert "s2" in segundo.script.read_text(encoding="utf-8")      # CONFIG trocado para a nova saída
