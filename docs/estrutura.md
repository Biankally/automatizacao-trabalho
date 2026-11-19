# Estrutura do Projeto — Especificação para Desenvolvimento

Nov 19, 2026 · @Bianca · versão para a entrega de 25/11

## Sobre este documento

**Para que serve.** Este documento é a planta de construção do sistema. Ele diz, para cada pasta e arquivo do repositório, **o que é, o que contém, de quem depende, quem o escreve, em que dia fica pronto e como se prova que está certo**. Quem abre o repositório pela primeira vez deve conseguir construir a sua parte lendo só este documento.

**O que não está aqui.** A justificativa das decisões (está no Documento de Arquitetura), a gestão do projeto (está no Plano) e a pesquisa (está no documento de pesquisa).

**Escopo: versão de 25/11.** Por causa do prazo, esta é uma versão reduzida da arquitetura. A estrutura em camadas continua igual; o que muda é a quantidade de arquivos:

| Entra na versão 25/11 | Fica para depois |
| --- | --- |
| busca, ficha, Construtor com catálogo de 6 funções, Revisor, orquestrador, linha de comando | testes de escala |
| um contrato em código: `Ficha` | contratos separados para achado, catálogo e script aprovado (ficam onde já estão) |
| registro simples das chamadas ao LLM, suficiente para provar a privacidade | registro completo por execução |
| experimento com 8 pedidos, 1 rodada por modo | 20 pedidos com 3 rodadas |
| decisões documentadas no Documento de Arquitetura | um arquivo por decisão em `docs/decisoes/` |

**Mudanças de 19/11, depois da validação:** a especificação das seções 4 e 5 foi executada de ponta a ponta numa implementação de referência antes de ser passada ao grupo. Disso saíram: o formato exato do `CONFIG` (`Ficha.para_config`), o modelo de script que acha a raiz do projeto sozinho, o executor com `sys.executable`, a leitura de JSON "sujo" do LLM, a nova tentativa no limite do Groq, o script **parecido** usado como exemplo na aula e o Revisor com testes **básico** e **borda** (a sabotagem fica nos testes do núcleo).

**Extra (só se o esqueleto de sexta fechar no horário):** uma janela simples (`tkinter`, que já vem com o Python) no modelo de script, para o usuário escolher as planilhas e clicar em "Rodar" sem usar o terminal.

**Como ler.**

- **Antes de escrever código:** seções 1, 2 e 6.
- **Para construir a sua parte:** seção 4, nos arquivos com a sua letra, e seção 8, no seu dia.
- **Para entender como as partes conversam:** seção 5.

**Papéis.** Os arquivos têm dono por letra; preencha os nomes quando o grupo decidir:

- **A, Núcleo e documentação:** \_\_\_
- **B, Construtor:** \_\_\_
- **C, Revisor e experimento:** \_\_\_

## 1. Princípios de projeto

A estrutura não é uma lista de pastas escolhida por gosto. Cada pasta e cada arquivo existe por causa de um princípio de engenharia de software. Quando surgir uma dúvida do tipo "onde eu coloco isso?", a resposta sai destes oito princípios.

| # | Princípio | O que diz | Como aparece na estrutura |
| --- | --- | --- | --- |
| P1 | **Responsabilidade única** | cada módulo tem um só motivo para mudar | um arquivo por tarefa: `busca.py` só decide se reaproveita, `montador.py` só monta o script |
| P2 | **Dependência em camadas** | um módulo só importa camadas abaixo dele; nunca acima, nunca ao lado | `nucleo/` não importa nada de `agentes/`; `construtor/` e `revisor/` não se importam |
| P3 | **Inversão de dependência** | quem usa depende de uma interface, não de uma implementação | os agentes falam com a interface `LLM`; Groq, Ollama e o LLM falso são trocados sem mexer neles |
| P4 | **Contrato antes do código** | a forma dos dados trocados é definida antes de qualquer implementação | `contratos/ficha.py` é o primeiro arquivo escrito; todos programam contra ele |
| P5 | **Teste antes da implementação** | o teste descreve o comportamento e falha até o código ficar pronto | cada arquivo de `src/` tem seu par em `tests/`, escrito primeiro |
| P6 | **Falhar cedo, sem esconder** | erro de processo para tudo; erro de dado vira pendência visível | exceções nomeadas no núcleo e nos agentes; achados no relatório |
| P7 | **Seguro por padrão** | o caminho mais fácil tem de ser o seguro | `.gitignore` bloqueia planilhas e `.env`; o LLM só recebe o que `disfarce.py` produz |
| P8 | **Simplicidade** | não construir o que ainda não é necessário | a versão 25/11 tem um só contrato em código e uma única forma de rodar (linha de comando) |

P1 a P3 vêm dos princípios SOLID (responsabilidade única e inversão de dependência) e da arquitetura em camadas. P5 é uma forma leve de desenvolvimento guiado por testes (TDD). P8 corresponde aos princípios conhecidos como KISS e YAGNI.

## 2. Visão geral

O código-fonte (`src/`) é dividido em 6 camadas, desenhadas em 7 linhas: Construtor e Revisor são a mesma camada (a 3), em linhas separadas só para caber. Cada caixa é um arquivo, com a cor do seu dono.

```
Mapa dos arquivos de código (6 camadas, 18 arquivos; dono entre colchetes)

Camada 1  Interface      principal.py [B]
Camada 2  Orquestração   orquestrador.py [B]
Camada 3  Construtor     busca.py [B]  ficha.py [B]  gerador.py [B]  montador.py [B]
Camada 3  Revisor        designer_testes.py [C]  kit_testes.py [C]  executor.py [C]
Camada 4  Comum          llm.py [B]  execucao.py [B]  prompts.py [B]  registro.py [C]
Camada 5  Núcleo         nucleo.py [A]  disfarce.py [A]  catalogo.py [A]  alterar_coluna.py [A]
Camada 6  Contratos      ficha.py [A]

Regra: cada arquivo só importa camadas de número MAIOR (abaixo). Construtor e Revisor não se importam.
```

Como ler o diagrama:

- **A seta à esquerda é a regra de importação (P2).** Um arquivo pode importar qualquer arquivo de uma linha abaixo dele, nunca de uma linha acima. Construtor e Revisor são vizinhos na mesma camada: um não pode importar o outro. Só o orquestrador conhece os dois.
- **As cores mostram o encaixe entre as pessoas.** A constrói a base (núcleo e contrato), B constrói quase toda a parte de cima e C constrói o Revisor e o registro. Os pontos de encontro são três: o contrato `Ficha` (A entrega a B e C), o catálogo (A entrega a B) e o orquestrador (B junta o trabalho de C).
- **Existem dois arquivos `ficha.py`, com papéis diferentes.** `contratos/ficha.py` define **o que é** uma ficha. `construtor/ficha.py` **preenche** uma ficha usando o LLM. O primeiro não sabe que o segundo existe.

Além do código-fonte, o repositório tem arquivos de apoio, que não são importados por ninguém, mas são lidos pelo programa: os textos do LLM (`prompts/`), o modelo de script (`modelos/`), a biblioteca de scripts aprovados (`scripts_aprovados/`) e as planilhas inventadas (`dados_exemplo/`).

## 3. Árvore de diretórios (versão 25/11)

A árvore abaixo é a estrutura completa do repositório na entrega. Ao lado de cada arquivo: **dono**, **dia** em que precisa estar pronto e **o que é**. Arquivos marcados com ★ já existem e só precisam ser adaptados.

```
automatizacao-trabalho/
│
├── README.md                          A  24/11  o que é, como instalar, como rodar
├── pyproject.toml                     A  19/11  metadados do pacote e configuração do pytest
├── requirements.txt                   A  19/11  pandas, openpyxl, pytest
├── .env.exemplo                       B  19/11  modelo da configuração do LLM, sem chave
├── .gitignore                       ★ A  19/11  bloqueia .env, planilhas reais e saida/
│
├── src/
│   ├── __init__.py
│   ├── principal.py                   B  20/11  linha de comando (camada 1)
│   │
│   ├── contratos/                     camada 6
│   │   ├── __init__.py
│   │   └── ficha.py                   A  19/11  dataclass Ficha + validação + JSON
│   │
│   ├── nucleo/                        camada 5 (nunca chama o LLM)
│   │   ├── __init__.py
│   │   ├── nucleo.py                ★ A  22/11  pipeline, conferências, relatório, Achado
│   │   ├── disfarce.py              ★ A  21/11  raio-x e amostra disfarçada
│   │   ├── catalogo.py                A  21/11  as 6 funções que o LLM pode usar
│   │   └── ferramentas/
│   │       ├── __init__.py
│   │       └── alterar_coluna.py    ★ A  22/11  ferramenta semente (completar | trocar)
│   │
│   └── agentes/
│       ├── __init__.py
│       ├── orquestrador.py            B  20/11  ciclo da Fase 1 (camada 2)
│       ├── comum/                     camada 4
│       │   ├── __init__.py
│       │   ├── llm.py               ★ B  19/11  interface LLM, LLMFalso, LLMCompativelOpenAI
│       │   ├── execucao.py          ★ B  19/11  extrair código e conferir por AST
│       │   ├── prompts.py                 B  20/11  lê e preenche prompts/*.md
│       │   └── registro.py                C  22/11  grava o que o LLM recebeu e respondeu
│       ├── construtor/                camada 3
│       │   ├── __init__.py
│       │   ├── busca.py                   B  22/11  reaproveitar ou criar
│       │   ├── ficha.py                   B  21/11  preenche a ficha + suposições
│       │   ├── gerador.py                 B  22/11  aula + corpo do script
│       │   └── montador.py                B  20/11  encaixa o corpo no modelo
│       └── revisor/                   camada 3 (vizinho do construtor)
│           ├── __init__.py
│           ├── designer_testes.py         C  22/11  escreve testes a partir da ficha
│           ├── kit_testes.py              C  21/11  peças prontas para os testes gerados
│           └── executor.py                C  20/11  roda o pytest e resume sem dados
│
├── prompts/
│   ├── construtor_busca.md            B  22/11
│   ├── construtor_ficha.md            B  21/11
│   ├── construtor_aula.md             B  22/11
│   └── revisor_testes.md              C  21/11
│
├── modelos/
│   └── script_gerado.py.modelo        B  20/11  cabeçalho fixo + CONFIG + corpo + chamada
│
├── scripts_aprovados/
│   ├── indice.json                    A  22/11  catálogo dos scripts aprovados
│   └── alterar_coluna/                A  22/11  1º script aprovado (semente)
│       ├── ficha.json
│       ├── script.py
│       └── test_script.py
│
├── dados_exemplo/
│   ├── gerar_exemplos.py              A  20/11  cria todas as planilhas inventadas
│   ├── basico/                        (gerado) origem.xlsx, destino.xlsx
│   └── casos_problema/                (gerado) vazios, chave_repetida, acentos, zeros, formulas
│
├── tests/                             um arquivo de teste por arquivo de src/
│   ├── conftest.py                    A  19/11  LLM falso, pastas temporárias, planilhas de exemplo
│   ├── test_contrato_ficha.py         A  19/11
│   ├── test_nucleo.py               ★ A
│   ├── test_disfarce.py             ★ A
│   ├── test_catalogo.py               A
│   ├── test_alterar_coluna.py       ★ A
│   ├── test_llm.py                  ★ B
│   ├── test_execucao.py             ★ B
│   ├── test_busca.py                  B
│   ├── test_ficha_construtor.py       B
│   ├── test_gerador.py                B
│   ├── test_montador.py               B
│   ├── test_orquestrador.py           B
│   ├── test_kit_testes.py             C
│   ├── test_designer_testes.py        C
│   ├── test_executor.py               C
│   ├── test_privacidade.py            C  22/11  nenhum valor real chega ao LLM
│   └── test_ponta_a_ponta.py          B+C 20/11 esqueleto; 23/11 completo
│
├── avaliacao/
│   ├── pedidos.json                   C  23/11  8 pedidos + gabarito
│   ├── rodar_experimento.py           C  23/11  1 agente × 2 agentes
│   └── resultados.md                  C  24/11
│
├── docs/                              A  24/11  Plano, Arquitetura, Estrutura e Pesquisa em .md
├── apresentacao/                      todos 24/11
└── saida/                             ignorada pelo git; resultados locais
```

Os testes ficam numa pasta só, sem subpastas. Para dois arquivos de teste não terem o mesmo nome, o que o pytest não aceita, os nomes dizem de qual camada são: `test_contrato_ficha.py` e `test_ficha_construtor.py`.

**Tipos de arquivo**

| Extensão | Uso | Por que esse formato |
| --- | --- | --- |
| `.py` | código e testes | linguagem única do projeto |
| `.md` | prompts e documentação | texto que pessoas revisam e o git compara linha a linha |
| `.json` | fichas, índice, pedidos do experimento | estruturado para o programa, legível para pessoas |
| `.py.modelo` | modelo de script com lacunas | a extensão diferente impede o Python e o pytest de executá-lo por engano |
| `.xlsx` | planilhas inventadas e saídas | o formato das planilhas reais |
| `.toml`, `.txt`, `.env` | configuração | padrão do ecossistema Python |

## 4. Especificação arquivo por arquivo

Cada arquivo de código segue a mesma ficha técnica:

- **Ficha técnica:** camada, dono e dia de entrega.
- **Propósito:** a única responsabilidade do arquivo (P1).
- **Interface:** o que os outros arquivos podem usar. É o compromisso entre as pessoas; mudar uma assinatura segue o controle de mudanças.
- **Importa:** de quais arquivos depende. Deve respeitar P2.
- **Pronto quando:** o critério objetivo para dar o arquivo como concluído.

O que não aparece na interface é detalhe interno: pode mudar sem avisar ninguém, desde que os testes continuem passando.

### 4.1 Raiz do repositório

| Arquivo | Dono | Conteúdo obrigatório |
| --- | --- | --- |
| `README.md` | A | o que o sistema faz (3 linhas); requisitos; instalação (seção 7); como criar um script; como rodar um script aprovado; como rodar os testes; links para os documentos |
| `pyproject.toml` | A | `[project]` com nome `automatizacao-trabalho`, versão e `requires-python = ">=3.10"`; `[tool.pytest.ini_options]` com `testpaths = ["tests"]` e `pythonpath = ["."]` |
| `requirements.txt` | A | `pandas`, `openpyxl`, `pytest`, cada um com a versão mínima |
| `.env.exemplo` | B | `LLM_URL_BASE=https://api.groq.com/openai/v1`, `LLM_MODELO=`, `LLM_API_KEY=` (vazio) e um comentário explicando que o arquivo real se chama `.env` e nunca vai para o git |
| `.gitignore` | A | `.env`; `*.xlsx`, `*.xls`, `*.xlsm`, `*.csv` com exceção de `dados_exemplo/`; `saida/`; `__pycache__/`; `.pytest_cache/`; `.venv/` |

### 4.2 `src/contratos/ficha.py`

- **Ficha técnica:** camada 6 · dono A · entrega 19/11 (primeiro arquivo do projeto).
- **Propósito:** definir o que é uma ficha, se ela está completa e como ela vira a configuração do script.
- **Importa:** só a biblioteca padrão (`dataclasses`, `json`, `pathlib`, `typing`).

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
    zeros_na_chave: bool = False              # True: "0048213" e "48213" são a mesma chave

@dataclass
class Ficha:
    pedido: str                               # texto original da pessoa
    planilhas: list[PlanilhaDaFicha]          # 1. exatamente uma "origem" e um "destino"
    chave: dict[str, str]                     # 2. {"origem": coluna, "destino": coluna}
    acao: str                                 # 3. "completar" ou "trocar"
    colunas: dict[str, str]                   # 4. coluna da origem -> coluna do destino
    casos_problema: CasosProblema             # 5.
    saida: str                                # 6. arquivo de saída
    suposicoes: list[str] = field(default_factory=list)
    confirmada: bool = False

    def problemas(self) -> list[str]          # lista vazia = ficha válida
    def perguntas(self) -> list[str]          # o que perguntar à pessoa
    def para_config(self, arquivos: dict[str, str] | None = None,
                    saida: str | None = None) -> dict   # o CONFIG do script (formato abaixo)
    def para_json(self) -> str
    @classmethod
    def de_json(cls, texto: str) -> "Ficha"   # lança FichaInvalida; campos ausentes: pedido="", suposicoes=[], confirmada=False

class FichaInvalida(Exception): ...
```

**Formato do CONFIG** (devolvido por `para_config`, usado pelo script e pelos testes do Revisor). `arquivos` troca o caminho de uma planilha pelo rótulo e `saida` troca o arquivo de saída; o relatório é sempre o nome da saída + `_RELATORIO.xlsx`.

```python
{
  "planilhas": {
    "origem":  {"arquivo": "rh.xlsx",       "aba": "Plan1", "linha_cabecalho": 1},
    "destino": {"arquivo": "cadastro.xlsx", "aba": "Plan1", "linha_cabecalho": 1},
  },
  "chave": {"origem": "Matricula", "destino": "Matricula"},
  "acao": "completar",
  "colunas": {"Email": "Email"},
  "casos_problema": {"chave_repetida": "nao_alterar", "ignorar_acento_e_caixa": False, "zeros_na_chave": True},
  "saida": "saida/cadastro_completado.xlsx",
  "relatorio": "saida/cadastro_completado_RELATORIO.xlsx",
}
```

- **`problemas()` acusa:** rótulos diferentes de exatamente `origem` e `destino`; planilha sem arquivo ou aba; chave sem as duas colunas; ação fora de `completar`/`trocar`; nenhuma coluna; coluna-chave do destino entre as colunas alteradas; `chave_repetida` inválida; saída vazia.
- **Pronto quando:** `test_contrato_ficha.py` cobre ficha válida, cada item acima, JSON quebrado, ida e volta (`de_json(para_json(f)) == f`) e o formato exato do `para_config()`.

### 4.3 `src/nucleo/`

**`nucleo.py` ★**

- **Ficha técnica:** camada 5 · dono A · entrega 22/11.
- **Propósito:** executar os passos (ler, padronizar, casar, julgar, agir, relatar) e conferir o resultado.
- **Interface:** a que já existe: `ler_aba`, `padronizar`, `chave_de`, `indexar`, `Opcoes`, `Tabela`, `Registro`, `CopiaSegura`, `Achado`, `conferir_completude`, `conferir_exatidao`, `conferir_rastro`, `gravar_relatorio`, `finalizar`.
- **Mudanças:** retirar nomes do trabalho; tirar os `print` de `finalizar()` (o texto passa a ser mostrado pelo `Resumo` do catálogo); todo `open()` com `encoding="utf-8"`. A classe `Achado` continua aqui nesta versão.
- **Pronto quando:** os testes atuais e as sabotagens passam, e uma busca por nomes do trabalho não acha nada.

**`disfarce.py` ★**

- **Ficha técnica:** camada 5 · dono A · entrega 21/11.
- **Propósito:** descrever uma planilha sem revelar valores.

```python
@dataclass
class ColunaRaioX:
    nome: str; tipo: str; pct_vazios: float; exemplo: str   # exemplo INVENTADO (mesmo formato, outro conteúdo)
@dataclass
class RaioX:
    arquivo: str; aba: str; total_linhas: int; colunas: list[ColunaRaioX]
    def para_texto(self) -> str        # o texto que vai no prompt
def raio_x(arquivo: str, aba: str, linha_cabecalho: int = 1) -> RaioX
def amostra_disfarcada(arquivo: str, aba: str, linha_cabecalho: int = 1,
                       n: int = 30, semente: int = 42) -> list[dict]
```

- **Pronto quando:** nenhum valor da planilha original aparece em `para_texto()` nem na amostra (teste com valores conhecidos).

**`catalogo.py`**

- **Ficha técnica:** camada 5 · dono A · entrega 21/11 (`ler_planilha` e `finalizar` em 20/11, para o esqueleto).
- **Propósito:** as funções que o LLM pode combinar, cada uma com descrição e exemplo.

```python
@dataclass(frozen=True)
class DescricaoDeFuncao:
    nome: str; assinatura: str; uso: str; retorna: str; exemplo: str
    def linha_da_aula(self) -> str
def registrar(uso: str, retorna: str, exemplo: str)        # decorador
def funcoes() -> dict[str, Callable]
def descricoes() -> list[DescricaoDeFuncao]               # na ordem de uso

@dataclass
class Resumo:
    ok: bool; saida: str; relatorio: str; alteradas: int; pendencias: int
    def __str__(self) -> str                               # o que o script mostra na tela

# As 6 funções da versão 25/11, na ordem em que um script as chama:
def ler_planilha(rotulo, arquivo, aba, linha_cabecalho) -> Tabela
def iniciar(ferramenta, origem, destino) -> Registro                     # registra as linhas das duas tabelas
def casar_por_chave(registro, origem, coluna_origem, destino, coluna_destino, casos_problema) -> Pares
def completar_coluna(registro, pares, coluna_origem, coluna_destino) -> None   # só células vazias
def trocar_coluna(registro, pares, coluna_origem, coluna_destino) -> None      # troca o que difere
def finalizar(registro, pares, saida, relatorio) -> Resumo               # aplica, confere, grava, relata
```

- **Regras:** `casar_por_chave` dá o desfecho de toda linha da origem e das linhas do destino sem chave ou sem par; `finalizar` dá o desfecho das linhas casadas (alterada, com pendência ou sem mudança), assim a conferência de completude sempre fecha. `zeros_na_chave=True` vira `Opcoes(zeros_chave=20)` (as duas chaves completadas com zeros até 20 dígitos). Valor diferente na origem para a mesma chave, com `chave_repetida="nao_alterar"`, vira pendência.
- **Pronto quando:** o exemplo de cada função roda numa planilha inventada; um script com as 6 funções gera saída e relatório.

**`ferramentas/alterar_coluna.py` ★**

- **Ficha técnica:** camada 5 · dono A · entrega 22/11.
- **Propósito:** a ferramenta semente; também vira o primeiro script aprovado (4.8).
- **Mudanças:** configuração padrão com nomes genéricos, apontando para `dados_exemplo/`.
- **Pronto quando:** os 14 testes atuais passam, incluindo as 5 sabotagens.

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

## 6. Regras de desenvolvimento

Regras combinadas uma vez e seguidas por todos. Elas existem para que o código de três pessoas pareça escrito por uma só e se encaixe sem surpresa.

### 6.1 Código

| Regra | Como é | Exemplo |
| --- | --- | --- |
| Estilo | PEP 8 (guia oficial de estilo do Python) | 4 espaços, linhas de até 100 caracteres |
| Nomes | português, sem acento; funções e variáveis em `minusculas_com_sublinhado`; classes em `MaiusculasJuntas`; constantes em `MAIUSCULAS` | `casar_por_chave`, `ResultadoTestes`, `MAX_VOLTAS` |
| Tipos | toda função pública tem anotação de tipos nos parâmetros e no retorno | `def decidir(llm: LLM, pedido: str) -> Decisao:` |
| Documentação | toda função pública tem docstring (PEP 257) dizendo o que faz, o que recebe, o que devolve e o que lança | ver abaixo |
| Tamanho | uma função faz uma coisa; passou de \~40 linhas, provavelmente faz duas | dividir em funções internas `_assim` |
| Caminhos | sempre `pathlib.Path`, nunca texto com `\` | `Path("saida") / "relatorio.xlsx"` |
| Números soltos | nada de números mágicos; vira constante com nome | `MAX_VOLTAS = 3`, `TAMANHO_AMOSTRA = 30` |
| Saída na tela | só `principal.py` e os scripts gerados usam `print`; os outros arquivos devolvem valores | o orquestrador devolve `ResultadoFase1`, não imprime |
| Erros | exceções com nome (`FichaInvalida`, `CodigoRecusado`, `LLMIndisponivel`); nunca `except:` vazio | `raise FichaInvalida("falta a coluna-chave")` |
| Importações | só camadas de baixo (P2); importações no topo do arquivo, uma por linha | `from src.contratos.ficha import Ficha` |

Duas regras a mais, porque quebram no Windows sem aviso:

- **Arquivos de texto sempre com `encoding="utf-8"`** (`open()`, `read_text()`, `write_text()`). Pastas com acento ou `°` quebram sem isso.
- **Subprocessos sempre com `sys.executable`**, nunca com o comando `python` solto, que pode ser outro Python, sem as bibliotecas do projeto.

Modelo de docstring:

```python
def decidir(llm: LLM, pedido: str, raio_x: list[RaioX], indice: list[dict]) -> Decisao:
    """Decide se um script aprovado atende o pedido.

    Recebe:
        llm: o LLM em uso (real ou falso).
        pedido: o texto original da pessoa.
        raio_x: o raio-x de cada planilha.
        indice: as entradas de scripts_aprovados/indice.json.
    Devolve:
        Decisao com o nome do script a reaproveitar, ou None para criar um novo.
    Garante:
        nunca devolve um nome que não esteja no índice (RN-08).
    """
```

### 6.2 Testes

| Regra | Como é |
| --- | --- |
| Ferramenta | pytest; rodar com `python -m pytest -q` na raiz |
| Um par por arquivo | cada arquivo de `src/` tem um `test_<nome>.py` em `tests/` |
| Nome do teste | `test_<o_que>_<situacao>`, por exemplo `test_decidir_nome_inventado_vira_criar` |
| Regra de negócio | teste que prova uma RN leva o número no nome: `test_rn15_original_intocado` |
| Estrutura | 3 blocos, nesta ordem: **prepara** (monta os dados), **age** (chama a função), **confere** (`assert`) |
| Sem internet | testes nunca chamam o LLM real; usam a peça `llm_falso` do `conftest.py` |
| Sem arquivos soltos | testes gravam só na pasta temporária do pytest (`tmp_path`) |
| Sabotagem | toda conferência tem um teste que estraga o resultado e exige que ela acuse |
| Primeiro o teste | escreva o teste antes da função e veja-o falhar; só então implemente |

### 6.3 Git e GitHub

O fluxo é o **GitHub Flow**: a `main` está sempre funcionando e todo trabalho acontece num branch separado.

1. **Branch por tarefa**, com a letra do dono: `a/catalogo`, `b/ficha-construtor`, `c/executor`.
2. **Commits pequenos**, no padrão *Conventional Commits*: `tipo(lugar): o que mudou`.
   - `feat(catalogo): adiciona casar_por_chave`
   - `test(executor): cobre tempo esgotado`
   - `fix(ficha): aceita linha_cabecalho ausente`
   - `docs(readme): instruções de instalação`
   - `refactor(nucleo): remove nomes do trabalho`
3. **Pull request** para a `main` no mesmo dia, com: o que muda, como testar e quais arquivos da seção 4 afeta.
4. **Revisão por outra pessoa** antes do merge. Quem revisa confere a definição de pronto (6.6).
5. **Merge só com testes passando.** Se a `main` quebrar, consertar vira a prioridade de quem quebrou.

### 6.4 Versões

Cada marco vira uma versão marcada no git (`git tag`), seguindo o versionamento semântico (SemVer):

| Versão | Quando | O que significa |
| --- | --- | --- |
| `v0.1.0` | sex 20/11 | esqueleto ponta a ponta com peças falsas (M2) |
| `v0.2.0` | dom 22/11 | peças reais, ainda com LLM falso (M3) |
| `v0.3.0` | seg 23/11 | integrado com o Groq (M4) |
| `v1.0.0` | ter 24/11 | versão de entrega |

Se algo quebrar perto da entrega, dá para voltar à última versão que funcionava com `git checkout v0.3.0`.

### 6.5 Segurança (antes de todo push)

- [ ] `git status` não mostra nenhum `.xlsx`, `.csv` ou `.env` fora de `dados_exemplo/`.
- [ ] Nenhuma chave de API no código (procurar por `key` e `gsk_` nos arquivos alterados).
- [ ] Nenhum nome do trabalho (órgão, tabela, coluna real) no código, nos testes ou nos prompts.
- [ ] Planilhas de exemplo geradas por `gerar_exemplos.py`, nunca copiadas de um arquivo real.

### 6.6 Definição de pronto

Um arquivo está pronto quando:

- [ ] implementa a interface da seção 4, sem mudar nenhuma assinatura;
- [ ] atinge o "pronto quando" da sua ficha técnica;
- [ ] tem testes, que passam sem internet;
- [ ] respeita a regra de importação (P2);
- [ ] tem docstrings nas funções públicas;
- [ ] passou na checagem de segurança (6.5);
- [ ] foi revisado por outra pessoa e está na `main`.

## 7. Preparação do ambiente

Cada pessoa faz isto uma vez, no próprio computador. Os comandos são para o terminal do Windows (PowerShell); no Linux ou Mac, as diferenças estão indicadas.

**1. Configurar o git com o e-mail protegido do GitHub** (evita a recusa do push por privacidade de e-mail):

```
git config --global user.name "Seu Nome"
git config --global user.email "SEU_ID+usuario@users.noreply.github.com"
```

O endereço exato aparece em github.com → Settings → Emails, com a opção "Keep my email addresses private" marcada.

**2. Baixar o repositório e entrar na pasta**

```
git clone https://github.com/Biankally/automatizacao-trabalho.git
cd automatizacao-trabalho
```

**3. Criar o ambiente virtual e instalar as dependências**

```
python -m venv .venv
.venv\Scripts\Activate.ps1          # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

O ambiente virtual (`.venv`) mantém as bibliotecas do projeto separadas das do computador. Ele precisa ser ativado toda vez que um terminal novo for aberto.

**4. Configurar o LLM**

```
copy .env.exemplo .env              # Linux/Mac: cp .env.exemplo .env
```

Abra o `.env` e cole a chave do Groq em `LLM_API_KEY=`. Esse arquivo nunca vai para o git.

**5. Gerar as planilhas inventadas e rodar os testes**

```
python dados_exemplo/gerar_exemplos.py
python -m pytest -q
```

Se todos os testes passarem, o ambiente está pronto.

**6. Antes de começar uma tarefa**

```
git checkout main
git pull
git checkout -b a/nome-da-tarefa    # troque a letra pela sua
```

**7. Ao terminar uma tarefa**

```
python -m pytest -q                 # tudo passando?
git status                          # nada de .xlsx, .csv ou .env
git add <arquivos>
git commit -m "feat(lugar): o que mudou"
git push -u origin a/nome-da-tarefa
```

Depois, abra o pull request no GitHub e peça a revisão de outra pessoa.

## 8. Ordem de criação

A ordem segue as camadas de baixo para cima (cada camada precisa da de baixo para ser testada) com uma exceção planejada: o **esqueleto de sexta**, em que todas as camadas existem ao mesmo tempo, algumas com peças falsas. As setas ➜ marcam o que uma pessoa entrega para outra.

| Dia | A: Núcleo e docs | B: Construtor | C: Revisor |
| --- | --- | --- | --- |
| **Qui 19** | estrutura de pastas, `pyproject.toml`, `requirements.txt`, `.gitignore`; `contratos/ficha.py` + `test_contrato_ficha.py` ➜ B e C; `conftest.py` | `comum/llm.py` e `comum/execucao.py` (da reconstrução do FlowMind) + testes; `.env.exemplo`; conta no Groq | assinaturas e docstrings de `kit_testes.py` e `executor.py` (sem implementar); testes que falham |
| **Sex 20** | `catalogo.py` com `ler_planilha` e `finalizar` ➜ B; `gerar_exemplos.py` com as planilhas básicas | `prompts.py`, `montador.py`, modelo de script, `orquestrador.py` e `principal.py` com busca, ficha e gerador **falsos** | `executor.py` real; `designer_testes.py` **falso** (1 teste fixo) ➜ B |
|  | **noite: os 3 juntos rodam `test_ponta_a_ponta.py` e marcam `v0.1.0`** |  |  |
| **Sáb 21** | catálogo completo (6 funções com exemplo) ➜ B; `disfarce.py` adaptado; planilhas de casos-problema | `construtor/ficha.py` real + `prompts/construtor_ficha.md` | `kit_testes.py` real + `prompts/revisor_testes.md` |
| **Dom 22** | `nucleo.py` e `alterar_coluna.py` sem nomes do trabalho; `scripts_aprovados/alterar_coluna/` e `indice.json` ➜ B | `busca.py`, `gerador.py` e os prompts de busca e aula | `designer_testes.py` real; `registro.py`; `test_privacidade.py` |
|  | **noite: tudo na `main` com LLM falso; marcar `v0.2.0`** |  |  |
| **Seg 23** | README; gabarito dos 8 pedidos com o núcleo ➜ C; começar os slides | integração com o Groq (com C): 3 pedidos de ponta a ponta | integração (com B); `pedidos.json`; `rodar_experimento.py`; marcar `v0.3.0` |
| **Ter 24** | slides; `docs/` com os 4 documentos em `.md` | gravar a demonstração (reserva); correções | rodar o experimento; `resultados.md` |
|  | **noite: ensaio da apresentação; marcar `v1.0.0`** |  |  |
| **Qua 25** | entrega | entrega | entrega |

**Se atrasar**, a ordem de corte é:

1. o experimento vira 4 pedidos;
2. o `designer_testes.py` fica com testes básicos, sem borda;
3. a busca vira sempre "criar novo".

O esqueleto, a ficha, o Construtor e o executor nunca são cortados: sem eles, não há o que demonstrar.

**Como saber quanto falta:** o `tests/test_ponta_a_ponta.py` já está no repositório. Enquanto faltar alguma peça, ele aparece como `skipped`. No dia em que ele passar, o sistema executa de ponta a ponta, do pedido ao script aprovado rodando numa planilha.

## 9. Checklist de entrega

Conferido pelos três juntos na noite de 24/11, antes de marcar `v1.0.0`.

**Funciona**

- [ ] Um clone novo do repositório instala e roda seguindo só o README.
- [ ] `python -m pytest -q` passa sem internet.
- [ ] `python -m src.principal criar ...` gera um script aprovado com o Groq, nos 3 pedidos de demonstração.
- [ ] Um pedido parecido com `alterar_coluna` reaproveita o script, sem gerar código novo.
- [ ] Um script aprovado roda com a internet desligada e gera saída e relatório.
- [ ] Uma sabotagem na saída gera `NAO_USE_`.

**Está seguro**

- [ ] `test_privacidade.py` passa.
- [ ] Nenhum `.xlsx`, `.csv` ou `.env` fora de `dados_exemplo/` no histórico do git.
- [ ] Nenhum nome do trabalho no repositório.

**Está explicado**

- [ ] `avaliacao/resultados.md` com a tabela 1 agente × 2 agentes e as limitações.
- [ ] `docs/` com Plano, Arquitetura, Estrutura e Pesquisa.
- [ ] Slides prontos e ensaiados; demonstração gravada como reserva.

## 10. Referências

**Padrões de código e de trabalho**

- PYTHON SOFTWARE FOUNDATION. [PEP 8: Style Guide for Python Code](https://peps.python.org/pep-0008/).
- PYTHON SOFTWARE FOUNDATION. [PEP 257: Docstring Conventions](https://peps.python.org/pep-0257/).
- [Conventional Commits 1.0.0](https://www.conventionalcommits.org/pt-br/v1.0.0/) (em português).
- PRESTON-WERNER, T. [Versionamento Semântico 2.0.0](https://semver.org/lang/pt-BR/).
- GITHUB. [GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow).
- PYTEST. [Documentação do pytest](https://docs.pytest.org/).

**Princípios de projeto**

- MARTIN, R. C. **Arquitetura Limpa: o guia do artesão para estrutura e design de software**. Alta Books, 2019. (Responsabilidade única, inversão de dependência, regra de dependência entre camadas.)
- BECK, K. **TDD: Desenvolvimento Guiado por Testes**. Bookman, 2010.

**Documentos do projeto**

- Plano do Projeto: escopo, regras de negócio (RN), requisitos (RF/RNF), riscos.
- Documento de Arquitetura de Software: contexto, decisões (ADRs), cenários de qualidade e a versão completa da arquitetura.
- Agentes que criam automações: pesquisa e engenharia reversa do FlowMind.
