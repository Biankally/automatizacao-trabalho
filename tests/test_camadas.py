"""Garante a regra de camadas: cada arquivo so importa camadas abaixo dele.

Este teste le os imports de todos os arquivos de src/ sem executa-los.
Se alguem (ou alguma IA) fizer o nucleo importar os agentes, ou o
construtor importar o revisor, este teste falha e aponta o arquivo.
"""

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SRC = RAIZ / "src"

# Camada de cada pasta (numero menor = mais acima).
CAMADAS = {
    "src.principal": 1,
    "src.agentes.orquestrador": 2,
    "src.agentes.construtor": 3,
    "src.agentes.revisor": 3,
    "src.agentes.comum": 4,
    "src.nucleo": 5,
    "src.contratos": 6,
}
# Vizinhos na mesma camada que nao podem se importar.
PROIBIDOS = {
    ("src.agentes.construtor", "src.agentes.revisor"),
    ("src.agentes.revisor", "src.agentes.construtor"),
}


def _grupo(modulo: str) -> str | None:
    """Devolve a pasta (chave de CAMADAS) a que um modulo pertence."""
    candidatos = [g for g in CAMADAS if modulo == g or modulo.startswith(g + ".")]
    return max(candidatos, key=len) if candidatos else None


def _modulo_do_arquivo(arquivo: Path) -> str:
    partes = arquivo.relative_to(RAIZ).with_suffix("").parts
    if partes[-1] == "__init__":
        partes = partes[:-1]
    return ".".join(partes)


def _imports(arquivo: Path) -> list[tuple[int, str]]:
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    achados = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            achados += [(no.lineno, a.name) for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            achados.append((no.lineno, no.module))
    return achados


def test_regra_de_camadas():
    violacoes = []
    for arquivo in SRC.rglob("*.py"):
        origem = _grupo(_modulo_do_arquivo(arquivo))
        if origem is None:
            continue
        for linha, importado in _imports(arquivo):
            destino = _grupo(importado)
            if destino is None or destino == origem:
                continue
            if CAMADAS[destino] < CAMADAS[origem] or (origem, destino) in PROIBIDOS:
                violacoes.append(f"{arquivo.relative_to(RAIZ)}:{linha} importa {importado}")
    assert not violacoes, "Regra de camadas quebrada:\n" + "\n".join(violacoes)
