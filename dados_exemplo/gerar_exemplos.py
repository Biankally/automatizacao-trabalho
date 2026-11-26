"""Gera as planilhas de exemplo, com dados INVENTADOS.

basico/          rh.xlsx (origem) e cadastro.xlsx (destino): o caso da demonstracao.
casos_problema/  um par origem/destino para cada caso estranho:
                 vazios, chave_repetida, acentos_maiusculas, zeros_a_esquerda, formulas.

Rodar: python dados_exemplo/gerar_exemplos.py
Garante: os mesmos arquivos toda vez; nenhum dado real.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

PASTA = Path(__file__).resolve().parent
AZUL = PatternFill("solid", fgColor="2457D6")

RH = [
    ["Matricula", "Nome", "Email", "Telefone"],
    ["0048213", "Ana Ribeiro", "ana.ribeiro@exemplo.com", "61 90000-0001"],
    ["0051007", "Bruno Teixeira", "bruno.teixeira@exemplo.com", "61 90000-0002"],
    ["0052310", "Carla Mendes", "carla.mendes@exemplo.com", "61 90000-0003"],
    ["0053421", "Diego Lima", "diego.lima@exemplo.com", "61 90000-0004"],
    ["0054532", "Elisa Prado", "elisa.prado@exemplo.com", "61 90000-0005"],
    ["0055643", "Fabio Nunes", "fabio.nunes@exemplo.com", "61 90000-0006"],
    ["0056754", "Gabriela Rocha", "gabriela.rocha@exemplo.com", "61 90000-0007"],
    ["0057865", "Heitor Alves", "heitor.alves@exemplo.com", "61 90000-0008"],
    ["0058976", "Iara Campos", "iara.campos@exemplo.com", "61 90000-0009"],
    ["0059087", "Joao Pires", "joao.pires@exemplo.com", "61 90000-0010"],
]
CADASTRO = [
    ["Matricula", "Nome", "Setor", "Email"],
    ["48213", "Ana Ribeiro", "Financeiro", None],                          # zero a esquerda + vazio
    ["51007", "Bruno Teixeira", "Compras", "bruno.teixeira@exemplo.com"],   # igual
    ["52310", "Carla Mendes", "RH", None],                                  # vazio
    ["53421", "Diego Lima", "TI", "diego.antigo@exemplo.com"],              # preenchido diferente
    ["54532", "Elisa Prado", "Juridico", None],                             # vazio
    ["55643", "Fabio Nunes", "TI", None],                                   # vazio
    ["56754", "Gabriela Rocha", "Compras", "gabriela.rocha@exemplo.com"],   # igual
    ["57865", "Heitor Alves", "Financeiro", None],                          # vazio
    ["99001", "Lia Souza", "Estagio", None],                                # sem par no RH
]

CASOS = {
    "vazios": ([["Mat", "Email"], ["1", "a@x.com"], ["2", None], ["3", "c@x.com"]],
               [["Mat", "Email"], ["1", None], ["2", None], ["3", None]]),
    "chave_repetida": ([["Mat", "Email"], ["1", "um@x.com"], ["1", "outro@x.com"], ["2", "dois@x.com"]],
                       [["Mat", "Email"], ["1", None], ["2", None]]),
    "acentos_maiusculas": ([["Nome", "Setor"], ["JOSÉ SILVA", "TI"], ["maria souza", "RH"]],
                           [["Nome", "Setor"], ["jose silva", None], ["Maria Souza", None]]),
    "zeros_a_esquerda": ([["Mat", "Email"], ["0048213", "a@x.com"], ["0000007", "b@x.com"]],
                         [["Mat", "Email"], ["48213", None], ["7", None]]),
    "formulas": ([["Mat", "Valor"], ["1", 10], ["2", 20]],
                 [["Mat", "Valor"], ["1", "=5+5"], ["2", None]]),
}


def gravar(caminho: Path, linhas: list[list]) -> Path:
    """Grava uma planilha simples com cabecalho destacado."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = "Plan1"
    for linha in linhas:
        ws.append(linha)
    for cel in ws[1]:
        cel.font, cel.fill = Font(bold=True, color="FFFFFF"), AZUL
    for col in "ABCD":
        ws.column_dimensions[col].width = 28
    wb.save(caminho)
    return caminho


def main(pasta: Path = PASTA) -> list[Path]:
    """Gera todas as planilhas em `pasta` (padrao: dados_exemplo/) e devolve os caminhos."""
    feitos = [gravar(pasta / "basico" / "rh.xlsx", RH), gravar(pasta / "basico" / "cadastro.xlsx", CADASTRO)]
    for nome, (origem, destino) in CASOS.items():
        feitos.append(gravar(pasta / "casos_problema" / nome / "origem.xlsx", origem))
        feitos.append(gravar(pasta / "casos_problema" / nome / "destino.xlsx", destino))
    return feitos


if __name__ == "__main__":
    for arquivo in main():
        print(arquivo.relative_to(PASTA.parent))
