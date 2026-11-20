# Pedido para a IA — Pessoa B (Construtor)

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
| Qui 19 | `src/agentes/comum/llm.py` e `execucao.py` (partindo do `flowmind_reconstrucao.zip`, com as mudanças da 4.4); `.env.exemplo`; conta no Groq |
| Sex 20 | `comum/prompts.py`, `construtor/montador.py` (o modelo já está pronto em `modelos/`), `agentes/orquestrador.py` e `principal.py`, com busca, ficha e gerador FALSOS |
| Sáb 21 | `construtor/ficha.py` real + `prompts/construtor_ficha.md` |
| Dom 22 | `construtor/busca.py`, `construtor/gerador.py`, `prompts/construtor_busca.md` e `construtor_aula.md` |
| Seg 23 | integração com o Groq (com C): 3 pedidos de ponta a ponta; `tests/test_ponta_a_ponta.py` passando |
| Ter 24 | gravar a demonstração |

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

### 4.5 `src/agentes/construtor/`

**`busca.py`**

- **Ficha técnica:** camada 3 · dono B · entrega 22/11 (versão falsa em 20/11: sempre "criar novo").

```python
@dataclass
class Decisao:
    reaproveitar: str | None    # script aprovado que serve IGUAL (só troca o CONFIG)
    parecido: str | None        # script aprovado PARECIDO (vira exemplo na aula)
    motivo: str
def decidir(llm: LLM, pedido: str, raio_x: list[RaioX], indice: list[dict]) -> Decisao
```

- **Regras:** o LLM responde `{"reaproveitar": nome|null, "parecido": nome|null, "motivo": "..."}` (lido com `extrair_json`). Nome que não está no índice vira `None`: o LLM nunca inventa um script.

**`ficha.py`**

- **Ficha técnica:** camada 3 · dono B · entrega 21/11 (versão falsa em 20/11: ficha fixa).

```python
def preencher(llm: LLM, pedido: str, raio_x: list[RaioX], amostras: list[list[dict]]) -> Ficha
def mostrar(ficha: Ficha) -> str         # texto da tela de confirmação
```

- **Regras:** lê a resposta com `extrair_json`, coloca `pedido` e `confirmada=False` e valida com `Ficha.de_json`. Resposta inválida: 1 nova tentativa com o aviso do erro; na 2ª, `FichaInvalida`.

**`gerador.py`**

- **Ficha técnica:** camada 3 · dono B · entrega 22/11 (versão falsa em 20/11: função fixa).

```python
def gerar_corpo(llm: LLM, ficha: Ficha, descricoes: list[DescricaoDeFuncao],
                exemplo: str | None = None, aviso_anterior: str | None = None) -> str
```

- **Regras:** o LLM escreve **a função inteira `def executar(config):`**, sem import, usando só funções do catálogo e o `config` no formato de 4.2. `exemplo` é a função `executar` de um script parecido (vem de `montador.funcao_de`). A resposta passa por `conferir_codigo(codigo, nomes_do_catalogo, exigir_funcoes=("executar",))`; recusada → `CodigoRecusado` (o orquestrador conta uma volta).

**`montador.py`**

- **Ficha técnica:** camada 3 · dono B · entrega 20/11. Não usa LLM.

```python
def montar(funcao: str, ficha: Ficha) -> str              # modelo + CONFIG + função; o texto final compila
def configurar(ficha: Ficha, pasta_aprovado: Path) -> str  # script aprovado com SÓ o bloco CONFIG trocado
def config_da_ficha(ficha: Ficha) -> dict                  # = ficha.para_config()
def funcao_de(script: str) -> str                          # extrai a função executar de um script
def nome_do_script(ficha: Ficha) -> str                    # ex.: "completar_email_por_matricula" (sem acento)
```

- **Pronto quando:** o script montado compila; `configurar` não muda nada fora dos marcadores de CONFIG; `nome_do_script` só tem `a-z`, `0-9` e `_`.

### 4.7 Orquestração e interface

**`src/agentes/orquestrador.py`**

- **Ficha técnica:** camada 2 · dono B (com C na integração) · entrega 20/11 com peças falsas; 23/11 completo.

```python
@dataclass
class ResultadoFase1:
    situacao: Literal["aprovado", "reprovado", "cancelado"]
    ficha: Ficha | None; script: Path | None; voltas: int; historico: list[str]
class Orquestrador:
    def __init__(self, llm: LLM, pasta_aprovados: Path, max_voltas: int = 3,
                 modo: Literal["dois_agentes", "um_agente"] = "dois_agentes",
                 pasta_trabalho: Path = Path("saida/candidatos")) -> None
    def fase1(self, pedido: str, planilhas: dict[str, Path],
              confirmar: Callable[[Ficha], Ficha | None]) -> ResultadoFase1
    registro: RegistroDeChamadas
```

- **Regras:** a ordem exata está na seção 5. As chamadas ao LLM acontecem nesta ordem: busca → ficha → testes (Revisor, uma vez) → função (Construtor, uma por volta). `confirmar` devolve a ficha (talvez corrigida) ou `None`; nunca há `input()` aqui. Raio-x e amostra usam a primeira aba de cada planilha. Cada tentativa é gravada em `pasta_trabalho/<data-hora>/` (`script.py` e `test_script.py`); só o aprovado vai para `pasta_aprovados/<nome>/` com `ficha.json`, e o `indice.json` é atualizado.
- **Pronto quando:** `tests/test_ponta_a_ponta.py` passa (aprovado na 1ª volta, aprovado na 2ª, reprovado após 3, cancelado e reaproveitado).

**`src/principal.py`**

- **Ficha técnica:** camada 1 · dono B · entrega 20/11.

```
python -m src.principal criar "pedido" --planilha origem=CAMINHO --planilha destino=CAMINHO
python -m src.principal listar
```

- **Regras:** aqui fica o `input()` da confirmação (`s`, `n` ou texto de correção). Erros viram mensagens claras, sem traceback.

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
