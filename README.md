# Agente de conformidade de planilhas

Trabalho final de Inteligência Artificial (IDP). Um sistema de agentes que recebe um pedido
em português ("completa o e-mail da planilha A usando a B, pela matrícula"), executa com
ferramentas que se conferem sozinhas e entrega a planilha com um relatório explicado.

Princípio: **o LLM decide O QUE fazer; o código faz e confere.**

## Estrutura
- `docs/`: o projeto (problema, arquitetura, componentes, verificação, fundamentação)
- `src/nucleo/`: as ferramentas (código, sem LLM)
- `src/agentes/`: Analista, Executor e Auditor
- `dados_exemplo/`: planilhas INVENTADAS
- `tests/`: testes
- `apresentacao/`: slides

## Regras do repositório
1. Nenhum dado real. Só planilhas inventadas, em `dados_exemplo/`.
2. Nenhuma chave de API no código (use `.env`).
