# Pedido para a IA — Pessoa A (Núcleo e documentação)

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
| Qui 19 | `src/contratos/ficha.py` + `tests/test_contrato_ficha.py` (inclui `para_config`) |
| Sex 20 | `src/nucleo/catalogo.py` com `ler_planilha`, `iniciar` e `finalizar`; `dados_exemplo/gerar_exemplos.py` (planilhas básicas) |
| Sáb 21 | catálogo completo (as 6 funções, cada uma com exemplo); `src/nucleo/disfarce.py`; planilhas de casos-problema |
| Dom 22 | `nucleo.py` e `alterar_coluna.py` sem nomes do trabalho e sem `print` em `finalizar`; `scripts_aprovados/alterar_coluna/` + `indice.json` |
| Seg 23 / Ter 24 | README; gabarito dos 8 pedidos do experimento; slides; `docs/` |

Para o catálogo e o núcleo, cole também o `nucleo.py` atual na conversa.

## Especificação exata

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
