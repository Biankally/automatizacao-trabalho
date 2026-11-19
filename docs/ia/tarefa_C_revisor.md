# Pedido para a IA — Pessoa C (Revisor e experimento)

Cole na IA, nesta ordem: (1) o conteúdo de `AGENTS.md`, (2) este arquivo, (3) `src/contratos/ficha.py`, (4) o arquivo que você vai alterar, se já existir.
Peça UM arquivo por vez, na ordem dos dias.

---

Você vai me ajudar a construir o agente Revisor de um projeto Python. Siga o AGENTS.md acima à risca.
Para cada arquivo: escreva primeiro o teste, depois a implementação. Não mude nenhuma assinatura abaixo.
REGRA CENTRAL: o Revisor nunca vê o script. Nenhum arquivo de `src/agentes/revisor/` pode importar nada de `src/agentes/construtor/`.

## Meus arquivos, na ordem

### Qui 19 — assinaturas e testes de `kit_testes.py` e `executor.py` (sem implementar)

### Sex 20 — `src/agentes/revisor/executor.py` (real) e `designer_testes.py` (falso: 1 teste fixo)

```python
@dataclass
class Falha:
    teste: str; tipo_erro: str; linha: int | None
@dataclass
class ResultadoTestes:
    passou: bool; total: int; falhas: list[Falha]
    def aviso(self) -> str      # texto que volta ao Construtor, SEM mensagens de erro
def executar(script: Path, testes: Path, tempo_limite: int = 60) -> ResultadoTestes
```

Como funciona: `subprocess` roda `python -m pytest <testes> --junitxml=<arquivo>`; do XML lê só nome do teste, tipo do erro e linha.
Teste obrigatório: `aviso()` não contém o texto da mensagem de erro.

### Sáb 21 — `revisor/kit_testes.py` (real) + `prompts/revisor_testes.md`

```python
def criar_planilha(pasta: Path, nome: str, cabecalho: list[str], linhas: list[list]) -> Path
def rodar_script(script: Path, config: dict, pasta: Path) -> Execucao   # Execucao(saida, relatorio, bloqueada)
def valor(saida: Path, coluna_chave: str, chave, coluna: str)
def achados(relatorio: Path, situacao: str | None = None) -> list[dict]
def sabotar(saida: Path, coluna_chave: str, chave, coluna: str, novo_valor) -> None
def conferir_de_novo(execucao: Execucao) -> bool
```

O prompt do Revisor: papel de testador; recebe a ficha e a descrição do kit; deve escrever testes com nomes `test_basico_*`, `test_borda_*` e `test_sabotagem_*`, criando planilhas pequenas dentro do próprio teste com `criar_planilha`.

### Dom 22 — `designer_testes.py` (real), `comum/registro.py`, `tests/test_privacidade.py`

```python
def escrever_testes(llm: LLM, ficha: Ficha, descricao_kit: str) -> str
def categorias(testes: str) -> dict[str, int]

class RegistroDeChamadas:
    def anotar(self, agente: str, mensagens: list[Mensagem], resposta: str) -> None
    def texto_enviado(self) -> str
    def salvar(self, arquivo: str) -> None
class LLMRegistrado:            # mesma interface LLM; anota cada chamada
    def __init__(self, llm: LLM, registro: RegistroDeChamadas, agente: str) -> None
    def conversar(self, mensagens: list[Mensagem]) -> str
```

Regras: os testes gerados passam por `conferir_codigo` liberando só o kit, `assert` e `pytest`; precisa de pelo menos 1 teste de cada categoria (senão, nova tentativa com aviso).
`test_privacidade.py`: roda um pedido inteiro com LLM falso e confere que nenhum valor das planilhas aparece em `texto_enviado()`.

### Seg 23 — integração (com a Pessoa B), `avaliacao/pedidos.json` e `avaliacao/rodar_experimento.py`

8 pedidos: 4 que devem reaproveitar um script, 3 novos dentro do catálogo, 1 fora do catálogo. Cada um com planilhas e gabarito (a Pessoa A gera o gabarito).
O experimento roda os 8 com `modo="um_agente"` e `modo="dois_agentes"` e mede: aprovou?, saída igual ao gabarito?, voltas, chamadas ao LLM.

### Ter 24 — rodar o experimento e escrever `avaliacao/resultados.md` (tabela + limitações).
