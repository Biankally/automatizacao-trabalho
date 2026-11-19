# AGENTS.md — instruções para assistentes de IA

Você está ajudando num projeto de faculdade com 3 pessoas e prazo curto.
Siga estas regras à risca. Se uma tarefa exigir quebrar alguma delas, PARE e avise quem pediu.

## O projeto em 3 linhas

Um agente recebe um pedido em português sobre planilhas e entrega um script Python testado.
Fase 1 (com LLM): busca um script existente ou cria um novo combinando funções prontas; um segundo agente (Revisor) testa sem ver o código.
Fase 2 (sem LLM, offline): a pessoa roda o script; o núcleo faz o trabalho e confere o próprio resultado.

Especificação completa de cada arquivo: `docs/estrutura.md`, seção 4. Use EXATAMENTE as assinaturas de lá.

## Regra de camadas (quem pode importar quem)

Cada arquivo só importa camadas ABAIXO dele. Nunca acima, nunca ao lado.

| Camada | Pasta | Pode importar |
|---|---|---|
| 1 | `src/principal.py` | tudo abaixo |
| 2 | `src/agentes/orquestrador.py` | 3, 4, 5, 6 |
| 3 | `src/agentes/construtor/` e `src/agentes/revisor/` | 4, 5, 6 — construtor e revisor NUNCA importam um ao outro |
| 4 | `src/agentes/comum/` | 5, 6 |
| 5 | `src/nucleo/` | 6 — o núcleo NUNCA importa nada de `agentes/` |
| 6 | `src/contratos/` | só a biblioteca padrão |

## Proibido

- Usar dado real. Planilhas de exemplo só são criadas por `dados_exemplo/gerar_exemplos.py`, com valores inventados.
- Colocar chave de API no código. Ela fica só no `.env` (que não vai para o git).
- Adicionar biblioteca nova. Só existem: biblioteca padrão, `pandas`, `openpyxl`, `pytest`. Nada de `openai`, `langchain`, `requests`.
- Mudar nome, parâmetros ou retorno de uma função pública da seção 4 de `docs/estrutura.md`. Isso quebra a parte de outra pessoa.
- Usar `print` fora de `src/principal.py` e dos scripts gerados. Os outros arquivos devolvem valores.
- Usar `except:` vazio ou esconder erro. Use as exceções com nome (`FichaInvalida`, `CodigoRecusado`, `LLMIndisponivel`).
- Casar chaves de forma aproximada (semelhança de texto). A comparação é sempre exata, depois de `padronizar()`.
- Mandar ao LLM valores de planilha ou a mensagem completa de um erro. Só tipo do erro e linha.

## Obrigatório

- Escrever o teste ANTES da função, em `tests/test_<arquivo>.py`. O teste deve falhar primeiro.
- Testes nunca usam internet nem o LLM real: use a peça `llm_falso` do `tests/conftest.py`.
- Testes gravam arquivos só em `tmp_path`.
- Toda conferência tem um teste de sabotagem (estraga o resultado de propósito e exige que a conferência acuse).
- Nomes em português, sem acento: funções `minusculas_com_sublinhado`, classes `MaiusculasJuntas`, constantes `MAIUSCULAS`.
- Anotação de tipos em toda função pública e docstring com: o que faz, Recebe, Devolve, Garante.
- Caminhos com `pathlib.Path`.

## Comandos

```
python -m venv .venv
.venv\Scripts\Activate.ps1           # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
python dados_exemplo/gerar_exemplos.py
python -m pytest -q
```

## Contrato central: `src/contratos/ficha.py`

A `Ficha` responde 6 perguntas: `planilhas`, `chave`, `acao` ("completar" ou "trocar"), `colunas`, `casos_problema`, `saida`.
Tem também `pedido`, `suposicoes` e `confirmada`. Métodos: `problemas()`, `perguntas()`, `para_json()`, `de_json()`.
Não altere este arquivo sem combinar com o grupo.

## Git

- Um branch por tarefa: `a/...`, `b/...`, `c/...`.
- Commits: `tipo(lugar): o que mudou` — tipos `feat`, `fix`, `test`, `docs`, `refactor`.
- Antes do commit: `python -m pytest -q` passando e `git status` sem `.xlsx`, `.csv` ou `.env`.

## Pronto quando

1. Implementa a interface da seção 4 sem mudar assinaturas.
2. Atinge o "Pronto quando" da ficha técnica do arquivo.
3. Testes passam sem internet.
4. Respeita a regra de camadas.
5. Tem docstrings.
6. Nenhum dado real, chave ou nome do trabalho.
