"""Rastro no Phoenix (opcional): manda cada passo e cada chamada ao LLM da demo para o Arize Phoenix.

So e usado por demo.py --phoenix. Precisa de: pip install -r requirements-phoenix.txt
e do servidor rodando em outro terminal: phoenix serve  (abre em http://localhost:6006).
Se o Phoenix nao estiver instalado, nada muda: a demo roda igual.
"""

from __future__ import annotations

import contextlib
import json

PROJETO = "agente-planilhas"
_tracer = None


def ligar(endpoint: str = "http://localhost:6006/v1/traces") -> bool:
    """Liga o envio de rastros. Devolve False se o Phoenix nao estiver instalado."""
    global _tracer
    try:
        from opentelemetry import trace
        from phoenix.otel import register
    except ImportError:
        return False
    register(project_name=PROJETO, endpoint=endpoint, batch=False, verbose=False)
    _tracer = trace.get_tracer("agente-planilhas")
    return True


@contextlib.contextmanager
def etapa(nome: str, tipo: str = "CHAIN", entrada: str | None = None):
    """Abre um trecho (span) no rastro. tipo: AGENT, CHAIN, TOOL ou LLM."""
    if _tracer is None:
        yield None
        return
    with _tracer.start_as_current_span(nome) as span:
        span.set_attribute("openinference.span.kind", tipo)
        if entrada is not None:
            span.set_attribute("input.value", entrada)
        yield span


def saida(span, valor) -> None:
    """Grava o resultado de um trecho."""
    if span is not None:
        span.set_attribute("output.value", valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False,
                                                                                           default=str))


class LLMRastreado:
    """Embrulha um LLM: cada conversar() vira um trecho LLM com o que foi enviado e recebido."""

    def __init__(self, llm, modelo: str) -> None:
        self._llm, self._modelo = llm, modelo

    def conversar(self, mensagens):
        with etapa(f"LLM · {self._modelo}", "LLM", json.dumps(mensagens, ensure_ascii=False)) as span:
            if span is not None:
                span.set_attribute("llm.model_name", self._modelo)
                for i, m in enumerate(mensagens):
                    span.set_attribute(f"llm.input_messages.{i}.message.role", m.get("role", ""))
                    span.set_attribute(f"llm.input_messages.{i}.message.content", m.get("content", ""))
            resposta = self._llm.conversar(mensagens)
            if span is not None:
                span.set_attribute("output.value", resposta)
                span.set_attribute("llm.output_messages.0.message.role", "assistant")
                span.set_attribute("llm.output_messages.0.message.content", resposta)
            return resposta
