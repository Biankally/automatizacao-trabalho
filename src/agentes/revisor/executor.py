"""Executor do Revisor: roda os testes gerados contra um script e resume o resultado.

Não usa LLM. O resumo traz só o nome de cada teste, o tipo do erro e a linha,
nunca a mensagem do erro (que pode conter valores das planilhas de teste).

Camada 3. Especificação: docs/estrutura.md, seção 4.6.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
TEMPO_LIMITE_PADRAO = 60
CODIGO_NENHUM_TESTE = 5  # código de saída do pytest quando não coleta nenhum teste
MENSAGEM_COLETA = "collection failure"  # como o pytest marca erro ao importar o arquivo de testes

# Última linha útil de um traceback do pytest: "caminho/arquivo.py:12: AssertionError".
# Linhas que começam com espaço, ">" ou "E " são código ou mensagem e são ignoradas.
_LINHA_DO_ERRO = re.compile(r"^(?![\s>]|E\s)(?P<arquivo>.+):(?P<linha>\d+): (?P<tipo>[A-Za-z_][\w.]*)$")
# Plano B, para erros de coleta (ex.: sintaxe): "E   SyntaxError: ..." -> só o tipo.
_TIPO_NA_MENSAGEM = re.compile(r"^E\s+(?P<tipo>[A-Za-z_]\w*(?:Error|Exception))\b")


@dataclass
class Falha:
    """Um teste que não passou.

    Recebe: nome do teste, tipo do erro e a linha (None quando não se sabe).
    """

    teste: str
    tipo_erro: str
    linha: int | None


@dataclass
class ResultadoTestes:
    """Resumo de uma execução do pytest, sem nenhum valor das planilhas."""

    passou: bool
    total: int
    falhas: list[Falha] = field(default_factory=list)

    def aviso(self) -> str:
        """Monta o texto que volta ao Construtor quando os testes falham.

        Devolve:
            "Falharam 1 de 2 testes:\\n- test_borda_x: AssertionError na linha 12",
            ou "Todos os N testes passaram." quando passou.
        Garante:
            só contém nomes de teste, tipos de erro e números de linha.
        """
        if self.passou:
            return f"Todos os {self.total} testes passaram."
        total = max(self.total, len(self.falhas))
        linhas = [f"Falharam {len(self.falhas)} de {total} testes:"]
        for falha in self.falhas:
            onde = f" na linha {falha.linha}" if falha.linha is not None else ""
            linhas.append(f"- {falha.teste}: {falha.tipo_erro}{onde}")
        return "\n".join(linhas)


def executar(script: Path, testes: Path, tempo_limite: int = TEMPO_LIMITE_PADRAO) -> ResultadoTestes:
    """Roda o arquivo de testes contra o script, num processo separado.

    Recebe:
        script: o script candidato (passado aos testes por SCRIPT_SOB_TESTE).
        testes: o arquivo pytest gerado pelo Revisor.
        tempo_limite: segundos até desistir da execução.
    Devolve:
        ResultadoTestes com o total de testes e as falhas (nome, tipo, linha).
    Garante:
        usa sys.executable; não lê a mensagem dos erros; teste pulado conta como
        falha (TestePulado); tempo esgotado vira TempoEsgotado; nenhum teste
        coletado vira NenhumTeste.
    """
    with tempfile.TemporaryDirectory() as pasta_temporaria:
        xml = Path(pasta_temporaria) / "resultado.xml"
        comando = [
            sys.executable, "-m", "pytest", str(Path(testes).resolve()), "-q",
            "-p", "no:cacheprovider",
            "-c", str(RAIZ / "pyproject.toml"),
            "--rootdir", str(RAIZ),
            f"--junitxml={xml}",
        ]
        ambiente = {
            **os.environ,
            "SCRIPT_SOB_TESTE": str(Path(script).resolve()),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        try:
            processo = subprocess.run(comando, cwd=RAIZ, env=ambiente, capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      timeout=tempo_limite)
        except subprocess.TimeoutExpired:
            return ResultadoTestes(False, 0, [Falha("(todos)", "TempoEsgotado", None)])

        if not xml.is_file():
            return ResultadoTestes(False, 0, [Falha("(todos)", "ErroNoPytest", None)])
        total, falhas = _ler_junit(xml)

    if total == 0:
        tipo = "NenhumTeste" if processo.returncode in (0, CODIGO_NENHUM_TESTE) else "ErroNoPytest"
        return ResultadoTestes(False, 0, falhas or [Falha("(todos)", tipo, None)])
    passou = processo.returncode == 0 and not falhas
    return ResultadoTestes(passou, total, falhas)


def _ler_junit(xml: Path) -> tuple[int, list[Falha]]:
    """Lê o relatório JUnit do pytest.

    Devolve: (total de testes, falhas). Erros de coleta entram como falhas e não somam ao total.
    """
    raiz = ET.parse(xml).getroot()
    total = 0
    falhas: list[Falha] = []
    for caso in raiz.iter("testcase"):
        nome = caso.get("name") or "(coleta)"
        problema = caso.find("failure")
        if problema is None:
            problema = caso.find("error")
        pulado = caso.find("skipped")
        eh_coleta = problema is not None and problema.get("message", "").startswith(MENSAGEM_COLETA)
        if not eh_coleta:
            total += 1
        if problema is not None:
            tipo, linha = _tipo_e_linha(problema.text or "")
            falhas.append(Falha(nome, tipo or ("ErroNaColeta" if eh_coleta else "Erro"), linha))
        elif pulado is not None:
            falhas.append(Falha(nome, "TestePulado", None))
    return total, falhas


def _tipo_e_linha(traceback: str) -> tuple[str | None, int | None]:
    """Acha o tipo do erro e a linha na ÚLTIMA linha útil do traceback.

    Garante: devolve só um nome de tipo e um número; o resto do texto é descartado.
    """
    linhas = traceback.splitlines()
    for linha in reversed(linhas):
        achado = _LINHA_DO_ERRO.match(linha.rstrip())
        if achado:
            return achado["tipo"].rsplit(".", 1)[-1], int(achado["linha"])
    for linha in linhas:
        achado = _TIPO_NA_MENSAGEM.match(linha)
        if achado:
            return achado["tipo"], None
    return None, None
