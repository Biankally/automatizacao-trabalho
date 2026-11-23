"""Testes do gerador de código do Construtor (src/agentes/construtor/gerador.py)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.agentes.comum.execucao import CodigoRecusado
from src.agentes.comum.llm import LLMFalso
from src.agentes.construtor.gerador import gerar_corpo
from src.contratos.ficha import CasosProblema, Ficha, PlanilhaDaFicha


@dataclass(frozen=True)
class _DescricaoFalsa:
    nome: str
    assinatura: str
    uso: str
    retorna: str
    exemplo: str

    def linha_da_aula(self) -> str:
        return f"- {self.assinatura}: {self.uso} (retorna {self.retorna}) | Ex: {self.exemplo}"


def _descricoes_exemplo() -> list[_DescricaoFalsa]:
    return [
        _DescricaoFalsa(
            nome="ler_planilha",
            assinatura="ler_planilha(rotulo, arquivo, aba, linha_cabecalho)",
            uso="Lê uma aba da planilha",
            retorna="Tabela",
            exemplo="origem = ler_planilha('origem', 'a.xlsx', 'Plan1', 1)",
        ),
        _DescricaoFalsa(
            nome="iniciar",
            assinatura="iniciar(ferramenta, origem, destino)",
            uso="Inicia o registro de auditoria",
            retorna="Registro",
            exemplo="reg = iniciar('ferramenta', origem, destino)",
        ),
        _DescricaoFalsa(
            nome="casar_por_chave",
            assinatura="casar_por_chave(registro, origem, col_o, destino, col_d, casos_problema)",
            uso="Casa linhas pela coluna-chave",
            retorna="Pares",
            exemplo="pares = casar_por_chave(reg, origem, 'ID', destino, 'ID', config['casos_problema'])",
        ),
        _DescricaoFalsa(
            nome="completar_coluna",
            assinatura="completar_coluna(registro, pares, coluna_origem, coluna_destino)",
            uso="Preenche células vazias no destino",
            retorna="None",
            exemplo="completar_coluna(reg, pares, 'Email', 'Email')",
        ),
        _DescricaoFalsa(
            nome="finalizar",
            assinatura="finalizar(registro, pares, saida, relatorio)",
            uso="Aplica alterações, confere e salva saída e relatório",
            retorna="Resumo",
            exemplo="return finalizar(reg, pares, config['saida'], config['relatorio'])",
        ),
    ]


def _ficha_exemplo() -> Ficha:
    return Ficha(
        pedido="Completar email do cadastro usando RH pela matrícula",
        planilhas=[
            PlanilhaDaFicha("origem", "rh.xlsx", "Plan1", 1),
            PlanilhaDaFicha("destino", "cadastro.xlsx", "Plan1", 1),
        ],
        chave={"origem": "Matricula", "destino": "Matricula"},
        acao="completar",
        colunas={"Email": "Email"},
        casos_problema=CasosProblema(zeros_na_chave=True),
        saida="saida/cadastro_completado.xlsx",
    )


def test_gerar_corpo_retorna_funcao_valida_e_envia_aula_com_exemplo() -> None:
    # prepara
    codigo_esperado = (
        "def executar(config):\n"
        "    p = config['planilhas']\n"
        "    origem = ler_planilha('origem', p['origem']['arquivo'], p['origem']['aba'], p['origem']['linha_cabecalho'])\n"
        "    destino = ler_planilha('destino', p['destino']['arquivo'], p['destino']['aba'], p['destino']['linha_cabecalho'])\n"
        "    reg = iniciar('completar_email', origem, destino)\n"
        "    pares = casar_por_chave(reg, origem, config['chave']['origem'], destino, config['chave']['destino'], config['casos_problema'])\n"
        "    for col_o, col_d in config['colunas'].items():\n"
        "        completar_coluna(reg, pares, col_o, col_d)\n"
        "    return finalizar(reg, pares, config['saida'], config['relatorio'])"
    )
    resposta_llm = f"Segue a implementação:\n```python\n{codigo_esperado}\n```"
    llm = LLMFalso([resposta_llm])
    exemplo = "def executar(config):\n    return None"

    # age
    corpo = gerar_corpo(
        llm,
        _ficha_exemplo(),
        _descricoes_exemplo(),  # type: ignore[arg-type]
        exemplo=exemplo,
    )

    # confere
    assert corpo == codigo_esperado
    assert len(llm.recebido) == 1
    prompt_enviado = llm.recebido[0][-1]["content"]
    assert "ler_planilha" in prompt_enviado
    assert "completar_coluna" in prompt_enviado
    assert "def executar(config):" in prompt_enviado
    assert "saida/cadastro_completado.xlsx" in prompt_enviado


def test_gerar_corpo_inclui_aviso_anterior_na_nova_tentativa() -> None:
    # prepara
    resposta_llm = (
        "```python\n"
        "def executar(config):\n"
        "    return config['saida']\n"
        "```"
    )
    llm = LLMFalso([resposta_llm])
    aviso = "Falharam 1 de 2 testes:\n- test_borda_nao_sobrescreve_preenchido: AssertionError na linha 14"

    # age
    corpo = gerar_corpo(
        llm,
        _ficha_exemplo(),
        _descricoes_exemplo(),  # type: ignore[arg-type]
        aviso_anterior=aviso,
    )

    # confere
    assert "def executar(config):" in corpo
    ultima_mensagem = llm.recebido[-1][-1]["content"]
    assert "test_borda_nao_sobrescreve_preenchido" in ultima_mensagem
    assert "AssertionError" in ultima_mensagem


@pytest.mark.parametrize(
    "resposta_invalida",
    [
        "Sem bloco de codigo python",
        "```python\nimport os\ndef executar(config):\n    return 1\n```",
        "```python\ndef outra_funcao(config):\n    return 1\n```",
        "```python\ndef executar(config):\n    return funcao_fora_do_catalogo(config)\n```",
    ],
)
def test_gerar_corpo_recusa_codigo_perigoso_ou_fora_do_catalogo(
    resposta_invalida: str,
) -> None:
    # prepara
    llm = LLMFalso([resposta_invalida])

    # age e confere
    with pytest.raises(CodigoRecusado):
        gerar_corpo(llm, _ficha_exemplo(), _descricoes_exemplo())  # type: ignore[arg-type]
