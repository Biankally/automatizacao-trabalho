# Pedido para a IA — Pessoa B (Construtor)

Cole na IA, nesta ordem: (1) o conteúdo de `AGENTS.md`, (2) este arquivo, (3) `src/contratos/ficha.py`, (4) o arquivo que você vai alterar, se já existir.
Peça UM arquivo por vez, na ordem dos dias.

---

Você vai me ajudar a construir o agente Construtor de um projeto Python. Siga o AGENTS.md acima à risca.
Para cada arquivo: escreva primeiro o teste, depois a implementação. Não mude nenhuma assinatura abaixo.
O LLM é acessado só pela interface `LLM` (método `conversar`). Nada de biblioteca `openai`: use `urllib`.
Nos testes, use sempre o `LLMFalso` com respostas gravadas.

## Meus arquivos, na ordem

### Qui 19 — `src/agentes/comum/llm.py` e `src/agentes/comum/execucao.py`

Os dois já existem na reconstrução do FlowMind (`flowmind/llm.py` e `flowmind/execucao.py`). Copie e ajuste para:

```python
Mensagem = dict[str, str]
class LLM(Protocol):
    def conversar(self, mensagens: list[Mensagem]) -> str: ...
class LLMFalso:
    def __init__(self, respostas: list[str]) -> None
    recebido: list[list[Mensagem]]
class LLMCompativelOpenAI:
    def __init__(self, modelo: str, url_base: str | None = None,
                 variavel_da_chave: str = "LLM_API_KEY", temperatura: float = 0.0) -> None
def criar_llm_do_ambiente() -> LLM
class LLMIndisponivel(Exception): ...

def extrair_codigo(resposta: str) -> str
def conferir_codigo(codigo: str, permitidas: set[str]) -> list[str]   # vazio = aceito
class CodigoRecusado(Exception): ...
```

Também: `.env.exemplo` com `LLM_URL_BASE=https://api.groq.com/openai/v1`, `LLM_MODELO=`, `LLM_API_KEY=`.

### Sex 20 — esqueleto: `prompts.py`, `montador.py`, modelo, `orquestrador.py`, `principal.py`

```python
# comum/prompts.py
def carregar(nome: str, **valores: str) -> str     # string.Template; KeyError se faltar variável

# construtor/montador.py  (NÃO usa LLM)
def montar(corpo: str, ficha: Ficha) -> str
def configurar(ficha: Ficha, pasta_aprovado: str) -> str   # troca só o bloco CONFIG
def config_da_ficha(ficha: Ficha) -> dict

# agentes/orquestrador.py
@dataclass
class ResultadoFase1:
    situacao: Literal["aprovado", "reprovado", "cancelado"]
    ficha: Ficha | None; script: Path | None; voltas: int; historico: list[str]
class Orquestrador:
    def __init__(self, llm: LLM, pasta_aprovados: Path, max_voltas: int = 3,
                 modo: Literal["dois_agentes", "um_agente"] = "dois_agentes") -> None
    def fase1(self, pedido: str, planilhas: dict[str, Path],
              confirmar: Callable[[Ficha], Ficha | None]) -> ResultadoFase1
```

`modelos/script_gerado.py.modelo`: cabeçalho fixo `from src.nucleo.catalogo import *`, lacuna `$config`, `def executar(config):` + lacuna `$corpo`, e `if __name__ == "__main__": print(executar(CONFIG))`.

`principal.py`: `python -m src.principal criar "pedido" --planilha origem=CAMINHO --planilha destino=CAMINHO` e `python -m src.principal listar`. O `input()` da confirmação fica AQUI (respostas: `s`, `n` ou texto de correção), nunca no orquestrador.

Na sexta, busca, ficha e gerador ainda são FALSOS (busca: sempre "criar novo"; ficha: fixa; gerador: corpo fixo). A ordem de chamadas do orquestrador está em `docs/estrutura.md`, seção 5.

### Sáb 21 — `construtor/ficha.py` + `prompts/construtor_ficha.md`

```python
def preencher(llm: LLM, pedido: str, raio_x: list[RaioX], amostras: list[list[dict]]) -> Ficha
def aplicar_correcao(llm: LLM, ficha: Ficha, correcao: str) -> Ficha
def mostrar(ficha: Ficha) -> str
```

Regra: JSON inválido → 1 nova tentativa com o aviso; na 2ª falha, `FichaInvalida`. O prompt pede as 6 respostas + `suposicoes`, e diz "se não souber, deixe vazio" (vira pergunta).

### Dom 22 — `construtor/busca.py`, `construtor/gerador.py` e os prompts de busca e aula

```python
@dataclass
class Decisao:
    reaproveitar: str | None
    motivo: str
def decidir(llm: LLM, pedido: str, raio_x: list[RaioX], indice: list[dict]) -> Decisao
def gerar_corpo(llm: LLM, ficha: Ficha, descricoes: list[DescricaoDeFuncao],
                aviso_anterior: str | None = None) -> str
```

Regras: nome que não está no índice vira "criar novo". O corpo gerado passa por `conferir_codigo` com os nomes do catálogo; se recusar, `CodigoRecusado`.
Formato de todo prompt: papel, informação disponível, regras, formato da resposta.

### Seg 23 — integração com o Groq (com a Pessoa C) e 3 pedidos de ponta a ponta. Ter 24 — gravar a demonstração.
