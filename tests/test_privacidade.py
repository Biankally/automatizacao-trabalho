"""Privacidade (RN-02, QC-04 e QC-05): nenhum valor das planilhas sai da máquina.

Roda a Fase 1 inteira com o LLM falso e procura, em tudo o que foi enviado ao LLM
(registro.texto_enviado()), cada valor das planilhas. Enquanto o orquestrador ou o
disfarce não existirem, os testes aparecem como "skipped".
"""

import json
from pathlib import Path

import pytest

orquestrador = pytest.importorskip("src.agentes.orquestrador", reason="orquestrador ainda não existe")
pytest.importorskip("src.nucleo.disfarce", reason="disfarce.py ainda não existe")
pytest.importorskip("src.nucleo.catalogo", reason="catalogo.py ainda não existe")
openpyxl = pytest.importorskip("openpyxl")

from src.agentes.comum.llm import LLMFalso  # noqa: E402

# Valores inventados, mas fáceis de achar se vazarem. Nenhum pode aparecer no que foi enviado.
ORIGEM = [
    ["Matricula", "Email", "Telefone"],
    ["7350091", "fulano.secreto@exemplo.com", "61 98765-4321"],
    ["7350092", "beltrana.oculta@exemplo.com", "61 91234-5678"],
]
DESTINO = [
    ["Matricula", "Nome", "Email"],
    ["7350091", "Fulano Secreto da Silva", None],
    ["7350092", "Beltrana Oculta Souza", "antigo.sigiloso@exemplo.com"],
]
VALORES = sorted({str(v) for linha in ORIGEM[1:] + DESTINO[1:] for v in linha if v})


def _planilha(caminho: Path, linhas: list[list]) -> Path:
    livro = openpyxl.Workbook()
    livro.active.title = "Plan1"
    for linha in linhas:
        livro.active.append(linha)
    livro.save(caminho)
    return caminho


def _respostas(origem: Path, destino: Path, saida: Path, funcao_errada: bool = False) -> list[str]:
    """Respostas do LLM na ordem do fluxo: busca, ficha, testes, função (uma ou duas voltas)."""
    busca = '{"reaproveitar": null, "parecido": null, "motivo": "nada parecido"}'
    ficha = json.dumps({
        "planilhas": [
            {"rotulo": "origem", "arquivo": str(origem), "aba": "Plan1", "linha_cabecalho": 1},
            {"rotulo": "destino", "arquivo": str(destino), "aba": "Plan1", "linha_cabecalho": 1},
        ],
        "chave": {"origem": "Matricula", "destino": "Matricula"},
        "acao": "completar",
        "colunas": {"Email": "Email"},
        "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False,
                           "zeros_na_chave": False},
        "saida": str(saida),
        "suposicoes": [],
    })
    testes = (
        "```python\n"
        "def test_basico_completa(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'a@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', None]])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'a@x.com'\n"
        "\n"
        "def test_borda_mantem_preenchido(tmp_path):\n"
        "    o = criar_planilha(tmp_path, 'o.xlsx', ['Matricula', 'Email'], [['1', 'novo@x.com']])\n"
        "    d = criar_planilha(tmp_path, 'd.xlsx', ['Matricula', 'Email'], [['1', 'velho@x.com']])\n"
        "    r = rodar_script(SCRIPT, config_teste(FICHA, {'origem': o, 'destino': d}, tmp_path))\n"
        "    assert valor(r.saida, 'Matricula', '1', 'Email') == 'velho@x.com'\n"
        "```"
    )
    certa = (
        "```python\n"
        "def executar(config):\n"
        "    p = config['planilhas']\n"
        "    origem = ler_planilha('origem', p['origem']['arquivo'], p['origem']['aba'], p['origem']['linha_cabecalho'])\n"
        "    destino = ler_planilha('destino', p['destino']['arquivo'], p['destino']['aba'], p['destino']['linha_cabecalho'])\n"
        "    registro = iniciar('completar', origem, destino)\n"
        "    pares = casar_por_chave(registro, origem, config['chave']['origem'], destino, config['chave']['destino'], config['casos_problema'])\n"
        "    for co, cd in config['colunas'].items():\n"
        "        completar_coluna(registro, pares, co, cd)\n"
        "    return finalizar(registro, pares, config['saida'], config['relatorio'])\n"
        "```"
    )
    funcoes = [certa.replace("completar_coluna(", "trocar_coluna("), certa] if funcao_errada else [certa]
    return [busca, ficha, testes] + funcoes


def _rodar(tmp_path: Path, funcao_errada: bool = False):
    origem = _planilha(tmp_path / "origem.xlsx", ORIGEM)
    destino = _planilha(tmp_path / "destino.xlsx", DESTINO)
    llm = LLMFalso(_respostas(origem, destino, tmp_path / "saida" / "out.xlsx", funcao_errada))
    orq = orquestrador.Orquestrador(llm, tmp_path / "aprovados", pasta_trabalho=tmp_path / "trabalho")
    resultado = orq.fase1("completar o email do destino com o da origem, pela matricula",
                          {"origem": origem, "destino": destino}, confirmar=lambda ficha: ficha)
    return orq, resultado


def test_privacidade_nenhum_valor_vai_ao_llm(tmp_path):
    orq, resultado = _rodar(tmp_path)

    assert resultado.situacao == "aprovado", resultado.historico
    enviado = orq.registro.texto_enviado()
    vazados = [v for v in VALORES if v in enviado]
    assert vazados == [], f"valores das planilhas foram enviados ao LLM: {len(vazados)}"


def test_privacidade_aviso_da_segunda_volta_sem_valores_dos_testes(tmp_path):
    """QC-05: quando um teste falha, o Construtor recebe o nome do teste, nunca os valores dele."""
    orq, resultado = _rodar(tmp_path, funcao_errada=True)

    assert resultado.situacao == "aprovado" and resultado.voltas == 2, resultado.historico
    enviado = orq.registro.texto_enviado()
    assert "test_borda_mantem_preenchido" in enviado
    assert "velho@x.com" not in enviado and "novo@x.com" not in enviado
    assert [v for v in VALORES if v in enviado] == []


def test_privacidade_registro_salvo_sem_valores(tmp_path):
    orq, _ = _rodar(tmp_path)
    arquivo = tmp_path / "registro.json"

    orq.registro.salvar(str(arquivo))

    texto = arquivo.read_text(encoding="utf-8")
    enviado = "".join(m["content"] for c in json.loads(texto) for m in c["mensagens"])
    assert [v for v in VALORES if v in enviado] == []
