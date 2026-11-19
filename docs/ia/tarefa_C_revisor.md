# Pedido para a IA — Pessoa C (Revisor e experimento)

**Como usar:** cole na IA, nesta ordem: (1) o conteúdo de `AGENTS.md`, (2) este arquivo inteiro, (3) o código atual do arquivo que você vai mexer, se já existir. Peça **um arquivo por vez**, na ordem dos dias.

As seções abaixo foram copiadas de `docs/estrutura.md` e já foram **executadas numa implementação de referência**: as interfaces se encaixam e rodam. Não mude nomes, parâmetros nem retornos.

---

Você vai me ajudar a construir a minha parte de um projeto Python em grupo. Siga o AGENTS.md à risca.
Para cada arquivo: escreva primeiro o teste (em `tests/`), confirme que ele falha, depois implemente.
Use exatamente as assinaturas abaixo. Nada de biblioteca além de pandas, openpyxl, pytest e a biblioteca padrão.
Todo arquivo de texto com `encoding="utf-8"`; subprocessos com `sys.executable`; caminhos com `pathlib.Path`.
Quando terminar um arquivo, rode `python -m pytest -q` e me mostre o resultado.

## Meus arquivos, por dia

| Dia | Arquivo |
| --- | --- |
| Qui 19 | assinaturas e testes (falhando) de `kit_testes.py` e `executor.py` |
| Sex 20 | `src/agentes/revisor/executor.py` real; `designer_testes.py` FALSO (1 teste fixo) |
| Sáb 21 | `revisor/kit_testes.py` real + `prompts/revisor_testes.md` |
| Dom 22 | `revisor/designer_testes.py` real; `comum/registro.py`; `tests/test_privacidade.py` |
| Seg 23 | integração (com B); `avaliacao/pedidos.json` e `rodar_experimento.py` |
| Ter 24 | rodar o experimento; `avaliacao/resultados.md` |

**Regra central:** nada em `src/agentes/revisor/` importa algo de `src/agentes/construtor/` (o `tests/test_camadas.py` acusa).

## Especificação exata

### 4.4 `src/agentes/comum/`

**`llm.py` ★**

- **Ficha técnica:** camada 4 · dono B · entrega 19/11 (vem da reconstrução do FlowMind).

```python
Mensagem = dict[str, str]           # {"role": "user" | "assistant", "content": "..."}
class LLM(Protocol):
    def conversar(self, mensagens: list[Mensagem]) -> str: ...
class LLMFalso:                     # devolve respostas prontas, em ordem; acabou = RuntimeError
    def __init__(self, respostas: list[str]) -> None
    recebido: list[list[Mensagem]]  # tudo o que "viu"
class LLMCompativelOpenAI:          # Groq, Ollama ou qualquer servidor no formato da OpenAI
    def __init__(self, modelo: str, url_base: str | None = None,
                 variavel_da_chave: str = "LLM_API_KEY", temperatura: float = 0.0) -> None
def criar_llm_do_ambiente() -> LLM  # lê LLM_URL_BASE, LLM_MODELO, LLM_API_KEY
class LLMIndisponivel(Exception): ...
```

- **Regras:** só `urllib` (nada da biblioteca `openai`). HTTP 429 (limite do plano grátis): espera 5 s e 10 s e tenta de novo, no máximo 3 vezes; depois, ou em qualquer outro erro de HTTP ou rede, `LLMIndisponivel`.
- **Pronto quando:** testes com o `LLMFalso` passam sem internet; uma chamada manual ao Groq responde.

**`execucao.py` ★**

- **Ficha técnica:** camada 4 · dono B · entrega 19/11.

````python
def extrair_codigo(resposta: str) -> str           # exige um único bloco ```python
def conferir_codigo(codigo: str, permitidas: set[str],
                    exigir_funcoes: tuple[str, ...] = ()) -> list[str]   # vazio = aceito
def extrair_json(resposta: str) -> dict            # acha o JSON mesmo cercado de texto ou crases; ValueError se não houver
class CodigoRecusado(Exception): ...
````

- **Mudanças em relação à reconstrução:** a exigência de `print()` sai; entra `exigir_funcoes` (por exemplo, `("executar",)`); entra `extrair_json`.
- **Pronto quando:** recusa `import`, `open`, `eval`, `__class__`, `.format` e `gi_frame`; `extrair_json` aceita resposta "suja" (texto + crases).

**`prompts.py`**

- **Ficha técnica:** camada 4 · dono B · entrega 20/11.

```python
def carregar(nome: str, **valores: str) -> str    # lê prompts/<nome>.md (utf-8) e preenche com string.Template; KeyError se faltar variável
```

**`registro.py`**

- **Ficha técnica:** camada 4 · dono C · entrega 22/11.

```python
class RegistroDeChamadas:
    def anotar(self, agente: str, mensagens: list[Mensagem], resposta: str) -> None
    def texto_enviado(self) -> str           # tudo o que saiu da máquina
    def salvar(self, arquivo: str) -> None   # JSON, utf-8
class LLMRegistrado:                         # mesma interface LLM; anota cada chamada
    def __init__(self, llm: LLM, registro: RegistroDeChamadas, agente: str) -> None
    def conversar(self, mensagens: list[Mensagem]) -> str
```

### 4.6 `src/agentes/revisor/`

**`kit_testes.py`**

- **Ficha técnica:** camada 3 · dono C · entrega 21/11.

```python
@dataclass
class Execucao:
    ok: bool; saida: Path; relatorio: Path; bloqueada: bool    # bloqueada = saída virou NAO_USE_
def script_sob_teste() -> Path                       # lê a variável de ambiente SCRIPT_SOB_TESTE
def criar_planilha(pasta, nome, cabecalho, linhas, aba="Plan1") -> Path
def config_teste(ficha: dict, arquivos: dict, pasta) -> dict    # CONFIG da ficha com as planilhas do teste; saída em pasta/saida.xlsx
def rodar_script(script: Path, config: dict) -> Execucao        # importa o script e chama executar(config)
def valor(saida, coluna_chave, chave, coluna)                   # valor de uma célula da saída
def achados(relatorio, situacao: str | None = None) -> list[dict]   # linhas da aba "Achados"
DESCRICAO_KIT: str                                    # o texto que vai no prompt do Revisor
```

- **Regras:** `config_teste` usa a primeira aba de cada planilha criada e `linha_cabecalho=1`, para o teste não depender da aba da ficha.

**`designer_testes.py`**

- **Ficha técnica:** camada 3 · dono C · entrega 22/11 (versão falsa em 20/11: 1 teste fixo).

```python
def escrever_testes(llm: LLM, ficha: Ficha, descricao_kit: str) -> str   # arquivo pytest completo
def categorias(testes: str) -> dict[str, int]        # {"basico": n, "borda": n}
```

- **Regras:** o LLM escreve **só as funções de teste** (`test_basico_*` e `test_borda_*`, com `tmp_path`), sem import. O designer coloca na frente um cabeçalho fixo com `import json`, `import pytest`, `from src.agentes.revisor.kit_testes import *`, `FICHA = json.loads(...)` e `SCRIPT = script_sob_teste()`. As funções passam por `conferir_codigo` liberando só o kit, `pytest`, `FICHA` e `SCRIPT`; falta de categoria → `CodigoRecusado`. **Não importa nada do construtor.**

**`executor.py`**

- **Ficha técnica:** camada 3 · dono C · entrega 20/11. Não usa LLM.

```python
@dataclass
class Falha:
    teste: str; tipo_erro: str; linha: int | None
@dataclass
class ResultadoTestes:
    passou: bool; total: int; falhas: list[Falha]
    def aviso(self) -> str       # "Falharam 1 de 2 testes:\n- test_borda_x: AssertionError na linha 12"
def executar(script: Path, testes: Path, tempo_limite: int = 60) -> ResultadoTestes
```

- **Como roda (exatamente):** `subprocess.run([sys.executable, "-m", "pytest", <testes>, "-q", "-p", "no:cacheprovider", "-c", <raiz>/pyproject.toml, "--rootdir", <raiz>, "--junitxml=<tmp>/resultado.xml"], cwd=<raiz>, env={..., "SCRIPT_SOB_TESTE": <script>}, timeout=tempo_limite)`.
- **Como lê:** do XML, só o nome de cada teste; o tipo e a linha saem da última linha do traceback (`arquivo.py:12: AssertionError`). A mensagem do erro, que contém valores, nunca é usada. Tempo esgotado → falha `TempoEsgotado`; nenhum teste coletado → falha `NenhumTeste`.

### 4.8 Arquivos de apoio

**Modelo** (`modelos/script_gerado.py.modelo`, dono B; **já validado, entra pronto no repositório**). As lacunas são `$raiz`, `$config` e `$funcao`, preenchidas com `string.Template`:

```python
# ===== Gerado pelo agente. Nao edite o cabecalho nem o final. =====
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve()
_RAIZ = next((p for p in _AQUI.parents if (p / "src" / "nucleo").is_dir()), Path(r"$raiz"))
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from src.nucleo.catalogo import *  # noqa: E402,F401,F403

# --- CONFIG (inicio) ---
CONFIG = $config
# --- CONFIG (fim) ---


$funcao


if __name__ == "__main__":
    print(executar(CONFIG))
```

O cabeçalho procura a raiz do projeto subindo as pastas; se o script estiver fora dela, usa o caminho gravado na hora da montagem. Assim ele roda com dois cliques, de qualquer pasta, sem `ModuleNotFoundError`.

**Prompts** (`prompts/`). Todo prompt tem: papel, informação disponível, regras e formato da resposta.

| Arquivo | Dono | Variáveis | Resposta esperada |
| --- | --- | --- | --- |
| `construtor_busca.md` | B | `$pedido`, `$raio_x`, `$indice` | JSON `{"reaproveitar", "parecido", "motivo"}` |
| `construtor_ficha.md` | B | `$pedido`, `$raio_x`, `$amostra` | JSON da `Ficha`, com `suposicoes` |
| `construtor_aula.md` | B | `$descricoes`, `$ficha`, `$exemplo` | um bloco \`\`\`python com `def executar(config):` |
| `revisor_testes.md` | C | `$ficha`, `$kit` | um bloco \`\`\`python só com funções `test_basico_*` e `test_borda_*` |

**Scripts aprovados** (`scripts_aprovados/`, dono A). Cada aprovado é uma pasta com `script.py`, `test_script.py` e `ficha.json`. O `indice.json` é uma lista com `nome`, `acao`, `descricao`, `aprovado_em` e `voltas`. A primeira entrada é o `alterar_coluna`, montado com o modelo acima.

**Planilhas inventadas** (`dados_exemplo/gerar_exemplos.py`, dono A). Gera `basico/` e `casos_problema/` (vazios, chave repetida, acentos e maiúsculas, zeros à esquerda, fórmulas).

**Testes de destaque** (`tests/`)

| Arquivo | Dono | O que prova |
| --- | --- | --- |
| `test_camadas.py` | (pronto) | nenhum import proibido entre camadas |
| `test_ponta_a_ponta.py` | (pronto) | **o termômetro:** o caminho inteiro com o LLM falso, incluindo rodar o script aprovado num processo separado e conferir a planilha de saída; enquanto faltar alguma peça, aparece como "skipped" |
| `test_privacidade.py` | C | nenhum valor das planilhas aparece em `registro.texto_enviado()` |

**Avaliação** (`avaliacao/`, dono C). `pedidos.json` traz os 8 pedidos (4 que devem reaproveitar, 3 novos dentro do catálogo, 1 fora), cada um com planilhas e gabarito; `rodar_experimento.py` roda os 8 nos dois modos e grava `resultados.md`.

## 5. Fluxo entre arquivos

Esta tabela é o roteiro de execução, na ordem exata em que o `test_ponta_a_ponta.py` percorre.

**Fase 1: `python -m src.principal criar ...`**

| # | Quem chama | Chama | Em | Recebe | Devolve |
| --- | --- | --- | --- | --- | --- |
| 1 | `principal.py` | `criar_llm_do_ambiente()` | `comum/llm.py` | `.env` | `LLM` |
| 2 | `principal.py` | `Orquestrador(...).fase1(...)` | `orquestrador.py` | pedido, planilhas, `confirmar` | `ResultadoFase1` |
| 3 | `orquestrador.py` | `raio_x()`, `amostra_disfarcada()` | `nucleo/disfarce.py` | planilhas (primeira aba) | `RaioX`, amostras |
| 4 | `orquestrador.py` | `decidir()` 🤖 | `construtor/busca.py` | pedido, raio-x, `indice.json` | `Decisao` |
| 5 | `orquestrador.py` | `preencher()` 🤖 | `construtor/ficha.py` | pedido, raio-x, amostras | `Ficha` |
| 6 | `orquestrador.py` | `confirmar(ficha)` | função de `principal.py` | `Ficha` | `Ficha` ou `None` (→ cancelado) |
| 7 | `orquestrador.py` | `escrever_testes()` 🤖 | `revisor/designer_testes.py` | **só a ficha** + `DESCRICAO_KIT` | arquivo de testes |
| 8 | `orquestrador.py` | `funcao_de()` (se houver parecido) | `construtor/montador.py` | script parecido | exemplo |
| 9a | `orquestrador.py` | `gerar_corpo()` 🤖 + `montar()` | `construtor/` | ficha, `descricoes()`, exemplo, aviso | script |
| 9b | (se reaproveitar) | `configurar()` | `construtor/montador.py` | ficha, pasta do aprovado | script |
| 10 | `orquestrador.py` | `executar()` | `revisor/executor.py` | script, testes | `ResultadoTestes` |
| 11 | se falhou | volta ao 9a com `aviso()` | — | — | máximo 3 voltas → reprovado |
| 12 | se passou | grava pasta e índice | `scripts_aprovados/` | script, testes, ficha | aprovado |

🤖 = chamada ao LLM, sempre pelo `LLMRegistrado`.

**Fase 2: `python scripts_aprovados/<nome>/script.py`** (ou dois cliques)

| # | Chama | Em | Devolve |
| --- | --- | --- | --- |
| 13 | `ler_planilha()` 2× | `nucleo/catalogo.py` | `Tabela` |
| 14 | `iniciar()` | `nucleo/catalogo.py` | `Registro` |
| 15 | `casar_por_chave()` | `nucleo/catalogo.py` | `Pares` |
| 16 | `completar_coluna()` ou `trocar_coluna()` por coluna | `nucleo/catalogo.py` | anota no `Registro` |
| 17 | `finalizar()` | `nucleo/catalogo.py` → `nucleo.py` | saída (ou `NAO_USE_`) + relatório + `Resumo` |

Na Fase 2, nenhum arquivo de `agentes/` é carregado.
