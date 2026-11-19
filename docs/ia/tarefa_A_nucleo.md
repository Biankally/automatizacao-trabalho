# Pedido para a IA — Pessoa A (Núcleo e documentação)

Cole na IA, nesta ordem: (1) o conteúdo de `AGENTS.md`, (2) este arquivo, (3) o arquivo que você vai alterar, se ele já existir.
Peça UM arquivo por vez, na ordem dos dias.

---

Você vai me ajudar a construir a camada de base de um projeto Python. Siga o AGENTS.md acima à risca.
Para cada arquivo: escreva primeiro o teste, depois a implementação. Não mude nenhuma assinatura abaixo.
Não use nenhuma biblioteca além de pandas, openpyxl, pytest e a biblioteca padrão.

## Meus arquivos, na ordem

### Qui 19 — `src/contratos/ficha.py` (primeiro arquivo do projeto; os outros dependem dele)

```python
@dataclass
class PlanilhaDaFicha:
    rotulo: str                # "origem" ou "destino"
    arquivo: str
    aba: str
    linha_cabecalho: int = 1

@dataclass
class CasosProblema:
    chave_repetida: Literal["nao_alterar", "primeiro"] = "nao_alterar"
    ignorar_acento_e_caixa: bool = False
    zeros_na_chave: bool = False

@dataclass
class Ficha:
    pedido: str
    planilhas: list[PlanilhaDaFicha]
    chave: dict[str, str]                     # rótulo -> coluna-chave
    acao: Literal["completar", "trocar"]
    colunas: dict[str, str]                   # coluna da origem -> coluna do destino
    casos_problema: CasosProblema
    saida: str
    suposicoes: list[str] = field(default_factory=list)
    confirmada: bool = False

    def problemas(self) -> list[str]          # lista vazia = ficha válida
    def perguntas(self) -> list[str]          # o que perguntar à pessoa quando falta algo
    def para_json(self) -> str
    @classmethod
    def de_json(cls, texto: str) -> "Ficha"   # lança FichaInvalida se o JSON não servir

class FichaInvalida(Exception): ...
```

Teste (`tests/test_contrato_ficha.py`): ficha válida; cada uma das 6 respostas faltando; ação inválida; JSON quebrado; `de_json(para_json(f)) == f`.

Também na quinta: `pyproject.toml` (pytest com `testpaths=["tests"]`, `pythonpath=["."]`), `requirements.txt` e `tests/conftest.py` com as peças `llm_falso`, `ficha_exemplo` e `planilhas_basicas`.

### Sex 20 — `src/nucleo/catalogo.py` (só 2 funções) e `dados_exemplo/gerar_exemplos.py`

```python
@dataclass(frozen=True)
class DescricaoDeFuncao:
    nome: str; assinatura: str; uso: str; retorna: str; exemplo: str
    def linha_da_aula(self) -> str

def registrar(uso: str, retorna: str, exemplo: str)   # decorador
def funcoes() -> dict[str, Callable]
def descricoes() -> list[DescricaoDeFuncao]

def ler_planilha(rotulo, arquivo, aba, linha_cabecalho) -> Tabela
def finalizar(registro, copia, saida, relatorio) -> Resumo
```

As funções do catálogo são embrulhos finos sobre o `nucleo.py` existente (cole o `nucleo.py` na conversa).
`gerar_exemplos.py` cria `dados_exemplo/basico/origem.xlsx` e `destino.xlsx` com valores inventados.

### Sáb 21 — catálogo completo + `disfarce.py` + casos-problema

Acrescente ao catálogo, cada uma com `uso`, `retorna` e `exemplo`:

```python
def iniciar(ferramenta, arquivo_destino, aba_destino) -> tuple[Registro, CopiaSegura]
def casar_por_chave(origem, coluna_origem, destino, coluna_destino, casos_problema) -> Pares
def completar_coluna(pares, coluna_origem, coluna_destino, registro, copia) -> None
def trocar_coluna(pares, coluna_origem, coluna_destino, registro, copia) -> None
```

`disfarce.py` (adaptar o `disfarcar_planilha.py` existente):

```python
@dataclass
class ColunaRaioX:
    nome: str; tipo: str; pct_vazios: float; exemplo: str   # exemplo INVENTADO
@dataclass
class RaioX:
    arquivo: str; aba: str; total_linhas: int; colunas: list[ColunaRaioX]
    def para_texto(self) -> str
def raio_x(arquivo: str, aba: str, linha_cabecalho: int = 1) -> RaioX
def amostra_disfarcada(arquivo: str, aba: str, linha_cabecalho: int = 1,
                       n: int = 30, semente: int = 42) -> list[dict]
```

Teste obrigatório: nenhum valor da planilha original aparece em `para_texto()` nem na amostra.
`gerar_exemplos.py` ganha `dados_exemplo/casos_problema/`: vazios, chave repetida, acentos e maiúsculas, zeros à esquerda, fórmulas.

### Dom 22 — limpar o núcleo e criar o 1º script aprovado

- Retirar de `nucleo.py` e `alterar_coluna.py` qualquer nome do trabalho; apontar exemplos para `dados_exemplo/`.
- Criar `scripts_aprovados/alterar_coluna/` com `ficha.json`, `script.py`, `test_script.py`.
- Criar `scripts_aprovados/indice.json`: lista com `nome`, `acao`, `descricao`, `aprovado_em`, `voltas`.

### Seg 23 e Ter 24

README (instalação, como criar um script, como rodar, como testar), gabarito dos 8 pedidos do experimento (rodando o núcleo à mão), slides e `docs/` em `.md`.
