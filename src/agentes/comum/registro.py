"""Registro das chamadas ao LLM: tudo o que saiu da máquina, para provar a privacidade.

Camada 4. Especificação: docs/estrutura.md, seção 4.4.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agentes.comum.llm import LLM, Mensagem

RESPOSTA_DE_FALHA = "(sem resposta: a chamada falhou)"


class RegistroDeChamadas:
    """Lista, em ordem, de cada chamada ao LLM: agente, mensagens enviadas e resposta."""

    def __init__(self) -> None:
        """Começa um registro vazio."""
        self._chamadas: list[dict] = []

    def anotar(self, agente: str, mensagens: list[Mensagem], resposta: str) -> None:
        """Anota uma chamada.

        Recebe:
            agente: quem chamou ("busca", "ficha", "revisor", "construtor").
            mensagens: o que foi enviado ao LLM.
            resposta: o que o LLM devolveu.
        Garante:
            guarda uma cópia; mudar as mensagens depois não altera o registro.
        """
        self._chamadas.append({
            "agente": agente,
            "mensagens": [dict(m) for m in mensagens],
            "resposta": resposta,
        })

    def texto_enviado(self) -> str:
        """Devolve todo o texto que saiu da máquina (só as mensagens enviadas).

        Devolve:
            o conteúdo de todas as mensagens, uma por linha; "" se não houve chamadas.
        Garante:
            não inclui as respostas do LLM, que não saíram da máquina.
        """
        return "\n".join(
            mensagem.get("content", "")
            for chamada in self._chamadas
            for mensagem in chamada["mensagens"]
        )

    def salvar(self, arquivo: str) -> None:
        """Grava o registro como JSON em utf-8.

        Recebe:
            arquivo: caminho do .json; as pastas que faltarem são criadas.
        """
        caminho = Path(arquivo)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(self._chamadas, ensure_ascii=False, indent=2),
                           encoding="utf-8")


class LLMRegistrado:
    """Embrulha um LLM: mesma interface, mas anota cada chamada no registro."""

    def __init__(self, llm: LLM, registro: RegistroDeChamadas, agente: str) -> None:
        """Recebe o LLM de verdade (ou falso), o registro e o nome do agente que vai usá-lo."""
        self._llm = llm
        self._registro = registro
        self._agente = agente

    def conversar(self, mensagens: list[Mensagem]) -> str:
        """Repassa ao LLM e anota a chamada.

        Recebe:
            mensagens: o histórico a enviar.
        Devolve:
            a resposta do LLM, sem mudança.
        Garante:
            se o LLM falhar, a chamada é anotada mesmo assim e o erro sobe sem ser escondido.
        """
        try:
            resposta = self._llm.conversar(mensagens)
        except Exception:
            self._registro.anotar(self._agente, mensagens, RESPOSTA_DE_FALHA)
            raise
        self._registro.anotar(self._agente, mensagens, resposta)
        return resposta
