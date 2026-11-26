"""
nucleo.py — peças comuns das ferramentas de conformidade de planilhas
=====================================================================

Toda ferramenta segue a mesma linha de montagem:

    1 LER  ->  2 PADRONIZAR  ->  3 CASAR  ->  4 JULGAR  ->  5 AGIR  ->  6 RELATAR
                                                                 + CONFERIR

Este arquivo NÃO faz nenhuma tarefa sozinho. Ele dá as peças que todos os scripts usam,
para que todos falem a mesma língua (mesmo "padronizar", mesmo achado, mesmas cores,
mesmo relatório) e passem pelas mesmas conferências antes de entregar a saída.

As 5 garantias (conferidas automaticamente em toda execução):
  1. Completude  — toda linha lida termina em exatamente UM desfecho (nada some, nada conta 2x)
  2. Exatidão    — a saída é reaberta e comparada célula a célula com o original:
                   só mudou o que está nos achados aplicados, e para o valor exato
  3. Validade    — regras de cada script (achados fora_da_regra)
  4. Exceções    — problema no DADO vira achado pendente (você decide);
                   problema no PROCESSO trava a saída (arquivo sai como NAO_USE_...)
  5. Rastro      — todo achado aplicado corresponde a uma célula alterada, e vice-versa

Cada script pode somar provas próprias (ex.: refazer a conta por outro caminho, rodar de
novo sobre a saída e não achar nada para mudar).

Camada 5: não importa nada de src/agentes/. Nunca usa print.
Requisitos: openpyxl.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

VERSAO_NUCLEO = "1.0"


# =====================================================================
# Vocabulário fixo (todas as ferramentas usam os mesmos nomes)
# =====================================================================

SITUACOES = {
    "igual":            "O valor bate com a referência (só contado, não vira linha)",
    "diferente":        "O valor não bate com a referência",
    "vazio":            "A célula está vazia",
    "fora_da_regra":    "O valor quebra uma regra (formato, lista, cálculo)",
    "sem_par":          "A chave não existe na referência",
    "so_na_referencia": "A chave existe na referência e não existe aqui",
    "chave_repetida":   "A chave aparece mais de uma vez",
    "protegido":        "Fórmula, valor mascarado ou cancelado: não pode ser mexido",
    "pergunta":         "A ferramenta não consegue decidir sozinha",
    "fora_do_escopo":   "Ficou fora do recorte (só contado)",
    "excluido":         "O registro foi excluído",
}
ACOES = ("nenhuma", "completar", "trocar", "criar", "excluir", "gerar")
DECISOES = ("automatica", "pendente", "aceita", "ignorada")
SEVERIDADES = ("ERRO", "AVISO", "INFO")


class ErroConfiguracao(SystemExit):
    """Arquivo, aba ou coluna errados na configuração: nada é processado."""


class ErroProcesso(RuntimeError):
    """Algo que nunca deveria acontecer no processamento (bug ou arquivo inesperado)."""


# =====================================================================
# O achado: o registro de UMA decisão da etapa "julgar"
# =====================================================================

@dataclass
class Achado:
    # Onde?
    planilha: str                  # rótulo da planilha (ex.: "DESTINO", "ORIGEM")
    linha: int | None              # linha do Excel (None = achado da planilha inteira)
    chave: str                     # valor da chave da linha (já padronizado)
    coluna: str                    # coluna afetada ("" = a linha toda)
    # O que tinha e contra o quê?
    valor: Any
    referencia: str                # contra o que foi comparado (ex.: "ORIGEM linha 12")
    # O que se concluiu?
    situacao: str
    regra: str                     # identificador curto da regra (ex.: "completar.vazio")
    severidade: str
    mensagem: str
    # O que fazer?
    acao: str = "nenhuma"
    valor_novo: Any = None
    aplicado: bool = False
    decisao: str = "automatica"
    # Quem fez?
    ferramenta: str = ""

    def __post_init__(self):
        if self.situacao not in SITUACOES:
            raise ErroProcesso(f"Situação desconhecida: {self.situacao!r}")
        if self.acao not in ACOES:
            raise ErroProcesso(f"Ação desconhecida: {self.acao!r}")
        if self.decisao not in DECISOES:
            raise ErroProcesso(f"Decisão desconhecida: {self.decisao!r}")
        if self.severidade not in SEVERIDADES:
            raise ErroProcesso(f"Severidade desconhecida: {self.severidade!r}")
        if self.aplicado and self.acao == "nenhuma":
            raise ErroProcesso("Achado aplicado precisa ter uma ação")
        if self.aplicado and self.decisao == "pendente":
            raise ErroProcesso("Achado pendente não pode estar aplicado")

    @property
    def cor(self) -> str | None:
        """A cor diz a CONSEQUÊNCIA; a situação (texto) diz o motivo."""
        if self.decisao == "pendente":
            return "verificar"
        if self.aplicado:
            return {"criar": "entrou", "excluir": "saiu"}.get(self.acao, "mudou")
        if self.situacao == "excluido":
            return "saiu"
        return None


# =====================================================================
# Etapa 2 — PADRONIZAR (a "língua comum" para comparar; nunca altera o original)
# =====================================================================

VAZIOS = {"", "null", "nulo", "none", "nan", "nat", "<na>"}

# espaços "exóticos" que o SharePoint/Word colam e que parecem espaço comum
_ESPACOS = dict.fromkeys(map(ord, "         "
                                  "     　"), " ")
# caracteres sem largura: invisíveis, mas mudam o texto
_INVISIVEIS = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)


def vazio(v: Any) -> bool:
    """None, NaN e textos como "", "null", "nan" contam como vazio."""
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    if isinstance(v, str):
        return limpar_texto(v).casefold() in VAZIOS
    return False


def limpar_texto(s: str) -> str:
    """Forma canônica do texto: NFKC, espaços exóticos e invisíveis, espaços repetidos."""
    s = unicodedata.normalize("NFKC", s).translate(_ESPACOS).translate(_INVISIVEIS)
    return re.sub(r"\s+", " ", s).strip()


def sem_acento(s: str) -> str:
    """Tira os acentos: "José" vira "Jose"."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _data_texto(d: dt.date) -> str:
    texto = f"{d.day:02d}/{d.month:02d}/{d.year:04d}"
    if isinstance(d, dt.datetime) and (d.hour or d.minute or d.second):
        texto += f" {d.hour:02d}:{d.minute:02d}"
    return texto


def _numero_texto(n: float) -> str:
    if float(n).is_integer():
        return str(int(n))
    return repr(round(float(n), 9))


@dataclass(frozen=True)
class Opcoes:
    """O que conta como 'igual'. Os padrões são os mesmos dos scripts antigos."""
    ignorar_acento: bool = True       # "José" = "JOSE"
    ignorar_caixa: bool = True        # "jose" = "JOSE"
    numeros_flexiveis: bool = True    # "1234,00" = 1234 = 1234.0
    datas_flexiveis: bool = True      # "2026-09-01" = "1/9/2026" = data do Excel
    zeros_chave: int = 0              # chave só com dígitos: completa com zeros à esquerda


def padronizar(v: Any, op: Opcoes = Opcoes()) -> str:
    """Transforma qualquer valor em texto comparável. Vazio vira ""."""
    if vazio(v):
        return ""
    if isinstance(v, bool):
        return "VERDADEIRO" if v else "FALSO"
    if isinstance(v, (dt.datetime, dt.date)):
        return _data_texto(v)
    if isinstance(v, (int, float)):
        return _numero_texto(v) if op.numeros_flexiveis else str(v)
    t = limpar_texto(str(v))
    if op.datas_flexiveis:
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::\d{2})?)?", t)
        if m:
            hora = f" {int(m.group(4)):02d}:{m.group(5)}" if m.group(4) and (int(m.group(4)) or int(m.group(5))) else ""
            t = f"{int(m.group(3)):02d}/{int(m.group(2)):02d}/{m.group(1)}{hora}"
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})( .*)?", t)
        if m:
            t = f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}{m.group(4) or ''}"
    if op.numeros_flexiveis and re.fullmatch(r"-?\d+([.,]\d+)?", t):
        t = _numero_texto(float(t.replace(",", ".")))
    if op.ignorar_acento:
        t = sem_acento(t)
    if op.ignorar_caixa:
        t = t.upper()
    return t


def chave_de(linha: "Linha", colunas: list[str], op: Opcoes = Opcoes()) -> str:
    """Chave simples ou composta ("ABC | 123"). Se alguma parte estiver vazia, devolve "".

    Zeros à esquerda: com zeros_chave=0, o texto "0048213" continua diferente de "48213"
    (a chave é um código, não um número). Com zeros_chave>0, os dois são completados com
    zeros até esse tamanho e passam a ser iguais.
    """
    partes = []
    for c in colunas:
        bruto = linha.valores.get(c)
        p = padronizar(bruto, op)
        if not op.zeros_chave and isinstance(bruto, str) and limpar_texto(bruto).isdigit():
            p = limpar_texto(bruto)
        if op.zeros_chave and p.isdigit():
            p = p.zfill(op.zeros_chave)
        partes.append(p)
    return "" if any(p == "" for p in partes) else " | ".join(partes)


# =====================================================================
# Etapa 1 — LER
# =====================================================================

@dataclass
class Linha:
    n: int                              # número da linha no Excel
    valores: dict[str, Any]             # coluna -> valor visível (resultado das fórmulas)


@dataclass
class Tabela:
    rotulo: str                         # "ORIGEM", "DESTINO"...
    arquivo: str
    aba: str
    linha_cab: int
    colunas: dict[str, int]             # nome -> número da coluna (1 = A)
    linhas: list[Linha]
    formulas: set[tuple[int, int]] = field(default_factory=set)   # (linha, coluna) com fórmula
    linhas_vazias: int = 0

    def exigir(self, nomes: list[str]) -> None:
        faltando = [n for n in nomes if n not in self.colunas]
        if faltando:
            raise ErroConfiguracao(
                f"❌ {self.rotulo}: coluna(s) não existem na aba '{self.aba}' de '{self.arquivo}': "
                f"{faltando}\n   Colunas que existem: {list(self.colunas)}")


def ler_aba(rotulo: str, arquivo: str, aba: str, linha_cab: int = 1) -> Tabela:
    """Lê uma aba guardando valores visíveis e onde há fórmula. Cabeçalho duplicado = erro."""
    if not os.path.exists(arquivo):
        raise ErroConfiguracao(f"❌ {rotulo}: arquivo não encontrado: {arquivo}")
    wb_f = load_workbook(arquivo, data_only=False)     # para saber onde há fórmula
    wb_v = load_workbook(arquivo, data_only=True)      # para ler o valor visível
    if aba not in wb_v.sheetnames:
        raise ErroConfiguracao(f"❌ {rotulo}: aba '{aba}' não existe em '{arquivo}'. Abas: {wb_v.sheetnames}")
    ws_f, ws_v = wb_f[aba], wb_v[aba]

    colunas: dict[str, int] = {}
    repetidos = []
    for c in range(1, ws_v.max_column + 1):
        nome = ws_v.cell(linha_cab, c).value
        nome = "" if nome is None else limpar_texto(str(nome))
        if not nome:
            continue
        if nome in colunas:
            repetidos.append(nome)
        colunas.setdefault(nome, c)
    if repetidos:
        raise ErroConfiguracao(f"❌ {rotulo}: nomes de coluna repetidos na linha {linha_cab}: {repetidos}")

    linhas, formulas, vazias = [], set(), 0
    for r in range(linha_cab + 1, ws_v.max_row + 1):
        valores = {}
        for nome, c in colunas.items():
            bruto = ws_f.cell(r, c).value
            if isinstance(bruto, str) and bruto.startswith("="):
                formulas.add((r, c))
            valores[nome] = ws_v.cell(r, c).value
        if all(vazio(v) for v in valores.values()):
            vazias += 1
            continue
        linhas.append(Linha(r, valores))
    return Tabela(rotulo, arquivo, aba, linha_cab, colunas, linhas, formulas, vazias)


# =====================================================================
# Etapa 3 — CASAR
# =====================================================================

def indexar(tabela: Tabela, colunas: list[str], op: Opcoes = Opcoes()):
    """chave -> [linhas com essa chave]; e a lista das linhas sem chave."""
    indice: dict[str, list[Linha]] = {}
    sem_chave: list[Linha] = []
    for l in tabela.linhas:
        k = chave_de(l, colunas, op)
        if k:
            indice.setdefault(k, []).append(l)
        else:
            sem_chave.append(l)
    return indice, sem_chave


# =====================================================================
# Etapa 4 — JULGAR: o registro guarda achados e o desfecho de cada linha
# =====================================================================

class Registro:
    """Guarda tudo o que foi decidido: os achados e o desfecho de cada linha lida."""

    def __init__(self, ferramenta: str):
        self.ferramenta = ferramenta
        self.achados: list[Achado] = []
        self.esperadas: dict[str, set[int]] = {}          # rótulo -> linhas que precisam de desfecho
        self.desfechos: dict[tuple[str, int], list[str]] = {}
        self.iguais: Counter = Counter()                  # coluna -> nº de células iguais

    def esperar(self, tabela: Tabela) -> None:
        self.esperadas[tabela.rotulo] = {l.n for l in tabela.linhas}

    def desfecho(self, rotulo: str, linha: int, texto: str) -> None:
        self.desfechos.setdefault((rotulo, linha), []).append(texto)

    def igual(self, coluna: str) -> None:
        self.iguais[coluna] += 1

    def achar(self, **campos) -> Achado:
        a = Achado(ferramenta=self.ferramenta, **campos)
        self.achados.append(a)
        return a

    def aplicados(self) -> list[Achado]:
        return [a for a in self.achados if a.aplicado]

    def pendentes(self) -> list[Achado]:
        return [a for a in self.achados if a.decisao == "pendente"]


# =====================================================================
# Etapa 5 — AGIR (sempre numa cópia; nunca em fórmula; tudo anotado)
# =====================================================================

COR = {"entrou": "C6EFCE", "mudou": "FFEB9C", "saiu": "FFC7CE", "valor": "F4B084", "verificar": "A5A5A5"}
_FILL = {k: PatternFill("solid", fgColor=v) for k, v in COR.items()}
_FONTE_VERIFICAR = Font(bold=True, color="FFFFFF")
_BORDA_DUPLA = Border(*(Side(style="double", color="3F3F3F"),) * 4)
_AZUL = PatternFill("solid", fgColor="2457D6")
ABA_LEGENDA = "Legenda (conformidade)"


def _hash(caminho: str) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()[:16]


class CopiaSegura:
    """Cópia do arquivo de destino onde as alterações são feitas e anotadas."""

    def __init__(self, tabela: Tabela):
        self.tabela = tabela
        self.wb = load_workbook(tabela.arquivo, keep_vba=tabela.arquivo.lower().endswith(".xlsm"))
        self.ws = self.wb[tabela.aba]
        self.alteradas: dict[tuple[int, int], Any] = {}   # (linha, coluna) -> valor escrito

    def aplicar(self, achado: Achado) -> None:
        if not achado.aplicado or achado.linha is None:
            raise ErroProcesso("Só achados aplicados, com linha, podem ser escritos")
        c = self.tabela.colunas[achado.coluna]
        if (achado.linha, c) in self.tabela.formulas:
            raise ErroProcesso(f"Tentativa de escrever sobre fórmula: linha {achado.linha}, {achado.coluna}")
        if (achado.linha, c) in self.alteradas:
            raise ErroProcesso(f"Célula alterada duas vezes: linha {achado.linha}, {achado.coluna}")
        self.ws.cell(achado.linha, c).value = achado.valor_novo
        self.alteradas[(achado.linha, c)] = achado.valor_novo

    def pintar(self, registro: Registro) -> None:
        """Linha: entrou/mudou/saiu. Célula: laranja no valor que mudou; Verificar Célula no pendente."""
        ws, cols = self.ws, self.tabela.colunas
        ultima = max(cols.values())
        linhas_cor: dict[int, str] = {}
        for a in registro.achados:
            if a.planilha != self.tabela.rotulo or a.linha is None or a.cor in (None, "verificar"):
                continue
            atual = linhas_cor.get(a.linha)
            ordem = ["mudou", "entrou", "saiu"]                 # saiu > entrou > mudou
            if atual is None or ordem.index(a.cor) > ordem.index(atual):
                linhas_cor[a.linha] = a.cor
        for r, cor in linhas_cor.items():
            for c in range(1, ultima + 1):
                ws.cell(r, c).fill = _FILL[cor]
        for a in registro.achados:
            if a.planilha != self.tabela.rotulo or a.linha is None:
                continue
            c = cols.get(a.coluna)
            if a.cor == "verificar":
                alvo = [c] if c else list(range(1, ultima + 1))
                for cc in alvo:
                    cel = ws.cell(a.linha, cc)
                    cel.fill, cel.font, cel.border = _FILL["verificar"], _FONTE_VERIFICAR, _BORDA_DUPLA
            elif a.aplicado and c:
                ws.cell(a.linha, c).fill = _FILL["valor"]

    def salvar(self, caminho: str) -> None:
        if ABA_LEGENDA in self.wb.sheetnames:
            del self.wb[ABA_LEGENDA]
        _escrever_legenda(self.wb.create_sheet(ABA_LEGENDA))
        self.wb.save(caminho)


# =====================================================================
# CONFERIR — as garantias
# =====================================================================

@dataclass
class Conferencia:
    """O resultado de uma garantia: nome, se passou e o detalhe."""

    nome: str
    ok: bool
    detalhe: str


def conferir_completude(reg: Registro) -> Conferencia:
    """Garantia 1: toda linha lida tem exatamente um desfecho."""
    faltando, duplicadas = [], []
    for rotulo, linhas in reg.esperadas.items():
        for n in linhas:
            d = reg.desfechos.get((rotulo, n), [])
            if not d:
                faltando.append(f"{rotulo} {n}")
            elif len(d) > 1:
                duplicadas.append(f"{rotulo} {n}")
    sobrando = [f"{r} {n}" for (r, n) in reg.desfechos if n not in reg.esperadas.get(r, set())]
    total = sum(len(v) for v in reg.esperadas.values())
    ok = not (faltando or duplicadas or sobrando)
    det = f"{total} linha(s) lidas, {total - len(faltando)} com desfecho"
    if faltando:
        det += f" · SEM desfecho: {faltando[:10]}"
    if duplicadas:
        det += f" · desfecho DUPLO: {duplicadas[:10]}"
    if sobrando:
        det += f" · desfecho de linha que não foi lida: {sobrando[:10]}"
    return Conferencia("Completude (nada sumiu, nada contou 2x)", ok, det)


def _mesmo_valor(a: Any, b: Any) -> bool:
    """Igualdade ESTRITA (para provar que a célula não mudou): só tolera 7 == 7.0 e None == ""."""
    if a is None or a == "":
        return b is None or b == ""
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b or a == b and type(a) is type(b)
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    if type(a) is type(b) and not isinstance(a, (str, dt.date)):   # ex.: fórmula de matriz do openpyxl
        return getattr(a, "text", str(a)) == getattr(b, "text", str(b))
    return a == b


def conferir_exatidao(tabela: Tabela, saida: str, alteradas: dict[tuple[int, int], Any]) -> Conferencia:
    """Garantia 2: reabre a saída e compara TODAS as células de TODAS as abas com o original."""
    wb_o = load_workbook(tabela.arquivo, data_only=False)
    wb_s = load_workbook(saida, data_only=False)
    problemas = []
    abas_o = wb_o.sheetnames
    abas_s = [a for a in wb_s.sheetnames if a != ABA_LEGENDA]
    if abas_o != abas_s:
        problemas.append(f"abas diferentes: original {abas_o} × saída {abas_s}")
    conferidas = 0
    for nome in abas_o:
        if nome not in wb_s.sheetnames:
            continue
        wo, wsa = wb_o[nome], wb_s[nome]
        for r in range(1, max(wo.max_row, wsa.max_row) + 1):
            for c in range(1, max(wo.max_column, wsa.max_column) + 1):
                vo, vs = wo.cell(r, c).value, wsa.cell(r, c).value
                conferidas += 1
                if nome == tabela.aba and (r, c) in alteradas:
                    if not _mesmo_valor(alteradas[(r, c)], vs):
                        problemas.append(f"{nome}!{wsa.cell(r, c).coordinate}: devia ser "
                                         f"{alteradas[(r, c)]!r}, está {vs!r}")
                elif not _mesmo_valor(vo, vs):
                    problemas.append(f"{nome}!{wsa.cell(r, c).coordinate}: mudou sem achado "
                                     f"({vo!r} → {vs!r})")
    ok = not problemas
    det = (f"{conferidas} célula(s) conferidas; {len(alteradas)} alteração(ões) esperada(s)"
           + ("" if ok else f" · {len(problemas)} problema(s): {problemas[:8]}"))
    return Conferencia("Exatidão (só mudou o que devia, para o valor certo)", ok, det)


def conferir_rastro(reg: Registro, alteradas: dict[tuple[int, int], Any], tabela: Tabela) -> Conferencia:
    """Garantia 5: cada achado aplicado tem sua célula alterada, e cada célula alterada tem seu achado."""
    dos_achados = {(a.linha, tabela.colunas[a.coluna]) for a in reg.aplicados() if a.planilha == tabela.rotulo}
    sem_celula = dos_achados - set(alteradas)
    sem_achado = set(alteradas) - dos_achados
    ok = not (sem_celula or sem_achado) and len(dos_achados) == len(reg.aplicados())
    det = f"{len(reg.aplicados())} achado(s) aplicado(s) × {len(alteradas)} célula(s) alterada(s)"
    if sem_celula:
        det += f" · achado sem alteração: {sorted(sem_celula)[:8]}"
    if sem_achado:
        det += f" · alteração sem achado: {sorted(sem_achado)[:8]}"
    return Conferencia("Rastro (toda alteração tem achado, e vice-versa)", ok, det)


# =====================================================================
# Etapa 6 — RELATAR
# =====================================================================

LEGENDA = [
    ("entrou", "Linha que entrou"),
    ("mudou", "Linha que mudou"),
    ("saiu", "Linha que saiu (excluída)"),
    ("valor", "O valor exato que mudou"),
    ("verificar", "Verificar Célula: precisa de você (motivo na coluna Situação / aba Achados)"),
    (None, "Sem cor: não mudou"),
]


def _escrever_legenda(ws) -> None:
    ws.append(["Cor", "Significado"])
    for cel in ws[1]:
        cel.font, cel.fill = Font(bold=True, color="FFFFFF"), _AZUL
    for cor, texto in LEGENDA:
        ws.append(["", texto])
        cel = ws.cell(ws.max_row, 1)
        if cor:
            cel.fill = _FILL[cor]
            if cor == "verificar":
                cel.font, cel.border = _FONTE_VERIFICAR, _BORDA_DUPLA
    ws.append([])
    ws.append(["A cor diz o que ACONTECEU. O MOTIVO está escrito (coluna Situação / aba Achados)."])
    ws.append([])
    ws.append(["Situação", "Quando"])
    for cel in ws[ws.max_row]:
        cel.font, cel.fill = Font(bold=True, color="FFFFFF"), _AZUL
    for s, d in SITUACOES.items():
        ws.append([s, d])
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 80


def _cabecalho(ws, larguras: list[int]) -> None:
    for i, cel in enumerate(ws[1]):
        cel.font, cel.fill = Font(bold=True, color="FFFFFF"), _AZUL
        cel.alignment = Alignment(vertical="center", wrap_text=True)
        if i < len(larguras):
            ws.column_dimensions[cel.column_letter].width = larguras[i]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _texto(v: Any) -> Any:
    if isinstance(v, (dt.datetime, dt.date)):
        return _data_texto(v)
    return v


CAMPOS_ACHADO = ["planilha", "linha", "chave", "coluna", "valor", "referencia", "situacao", "regra",
                 "severidade", "mensagem", "acao", "valor_novo", "aplicado", "decisao", "ferramenta"]


def gravar_relatorio(caminho: str, reg: Registro, conferencias: list[Conferencia],
                     info: list[tuple[str, Any]], saida_final: str) -> None:
    ok = all(c.ok for c in conferencias)
    wb = Workbook()
    _escrever_legenda(wb.active)
    wb.active.title = "Legenda"

    ws = wb.create_sheet("Resumo")
    ws.append(["RESULTADO", "PODE USAR" if ok else "NÃO USE — uma ou mais conferências falharam"])
    ws.cell(1, 2).fill = _FILL["entrou"] if ok else _FILL["saiu"]
    ws.cell(1, 1).font = ws.cell(1, 2).font = Font(bold=True)
    ws.append(["Arquivo gerado", saida_final])
    ws.append(["Gerado em", dt.datetime.now().strftime("%d/%m/%Y %H:%M")])
    ws.append(["Ferramenta", reg.ferramenta])
    ws.append(["Núcleo", VERSAO_NUCLEO])
    for k, v in info:
        ws.append([k, _texto(v) if not isinstance(v, (list, dict, tuple)) else str(v)])
    ws.append([])
    ws.append(["Achados por situação", "Quantidade"])
    for s, n in sorted(Counter(a.situacao for a in reg.achados).items(), key=lambda x: -x[1]):
        ws.append([s, n])
    ws.append(["igual (só contado)", sum(reg.iguais.values())])
    ws.append([])
    ws.append(["Desfecho das linhas", "Quantidade"])
    for (rot, d), n in sorted(Counter((r, v[0]) for (r, _), v in reg.desfechos.items()).items()):
        ws.append([f"{rot}: {d}", n])
    ws.append([])
    ws.append(["Aplicados", len(reg.aplicados())])
    ws.append(["Pendentes (precisam de você)", len(reg.pendentes())])
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 90

    wc = wb.create_sheet("Conferência")
    wc.append(["Conferência", "Resultado", "Detalhe"])
    for c in conferencias:
        wc.append([c.nome, "passou" if c.ok else "FALHOU", c.detalhe])
        wc.cell(wc.max_row, 2).fill = _FILL["entrou"] if c.ok else _FILL["saiu"]
    _cabecalho(wc, [52, 12, 120])

    wa = wb.create_sheet("Achados")
    wa.append(CAMPOS_ACHADO)
    for a in reg.achados:
        wa.append([_texto(getattr(a, k)) for k in CAMPOS_ACHADO])
        cor = a.cor
        if cor:
            cel = wa.cell(wa.max_row, CAMPOS_ACHADO.index("situacao") + 1)
            cel.fill = _FILL[cor]
            if cor == "verificar":
                cel.font = _FONTE_VERIFICAR
    _cabecalho(wa, [10, 8, 24, 22, 22, 22, 16, 22, 10, 60, 11, 22, 9, 11, 16])

    wi = wb.create_sheet("Iguais por coluna")
    wi.append(["Coluna", "Células iguais"])
    for col, n in reg.iguais.most_common():
        wi.append([col, n])
    _cabecalho(wi, [30, 16])
    wb.save(caminho)


# =====================================================================
# Fechamento comum: salvar, conferir, nomear e relatar
# =====================================================================

def finalizar(reg: Registro, copia: CopiaSegura, saida: str, relatorio: str,
              info: list[tuple[str, Any]], provas: list[Callable[[str], Conferencia]] = ()) -> tuple[bool, str]:
    """Salva, confere e dá o nome final à saída.

    Recebe: o registro, a cópia com as alterações, os caminhos da saída e do relatório,
            informações extras para o relatório e provas extras (opcionais).
    Devolve: (ok, caminho_final). ok=False quando alguma conferência falhou.
    Garante: o original nunca é alterado; a saída só tem o nome pedido se TODAS as
             conferências passarem, senão sai como NAO_USE_<nome>; nada é impresso na tela
             (quem mostra o resultado é o Resumo do catálogo).
    """
    destino = copia.tabela.arquivo
    if Path(saida).resolve() == Path(destino).resolve():
        raise ErroConfiguracao("❌ A SAÍDA não pode ser o próprio arquivo de destino (o original nunca é alterado).")
    hash_antes = _hash(destino)
    pasta, nome = os.path.split(os.path.abspath(saida))
    tmp = os.path.join(pasta, "~tmp_" + nome)
    copia.pintar(reg)
    copia.salvar(tmp)

    conferencias = [conferir_completude(reg),
                    conferir_exatidao(copia.tabela, tmp, copia.alteradas),
                    conferir_rastro(reg, copia.alteradas, copia.tabela)]
    for prova in provas:
        try:
            conferencias.append(prova(tmp))
        except Exception as e:                      # prova que quebra = processo com problema
            conferencias.append(Conferencia(getattr(prova, "__name__", "prova"), False, f"a prova quebrou: {e!r}"))
    intocado = _hash(destino) == hash_antes
    conferencias.append(Conferencia("Original intocado", intocado,
                                    "o arquivo de destino original não foi modificado" if intocado
                                    else "O ARQUIVO ORIGINAL FOI MODIFICADO"))
    ok = all(c.ok for c in conferencias)
    final = saida if ok else os.path.join(pasta, "NAO_USE_" + nome)
    for antigo in (saida, os.path.join(pasta, "NAO_USE_" + nome)):
        if os.path.exists(antigo):
            os.remove(antigo)                       # não deixa resultado velho com nome de bom
    os.replace(tmp, final)
    gravar_relatorio(relatorio, reg, conferencias, info + [("Destino (hash)", hash_antes)], final)

    return ok, final
