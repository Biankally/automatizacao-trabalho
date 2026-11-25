"""Conexão com o LLM.

Define a interface LLM e suas implementações:
- LLMFalso: devolve respostas prontas em ordem, sem rede.
- LLMCompativelOpenAI: chama servidores compatíveis com a API da OpenAI (Groq, Ollama etc.).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Protocol
import urllib.error
import urllib.request

Mensagem = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}

ESPERAS_LIMITE_TAXA: tuple[int, ...] = (5, 10)
MAX_TENTATIVAS: int = 3
URL_BASE_PADRAO: str = "https://api.openai.com/v1"


class LLMIndisponivel(Exception):
    """Lançada quando o servidor de LLM falha, está sem configuração ou esgota tentativas."""


class LLM(Protocol):
    """Contrato mínimo de qualquer cliente de modelo de linguagem."""

    def conversar(self, mensagens: list[Mensagem]) -> str:
        """Envia o histórico de mensagens e devolve o texto de resposta."""
        ...


class LLMFalso:
    """Implementação determinística de LLM para testes e execução sem internet."""

    def __init__(self, respostas: list[str]) -> None:
        """Inicializa o LLM falso com uma fila de respostas.

        Recebe:
            respostas: lista de strings que serão devolvidas a cada chamada.
        """
        self._respostas = list(respostas)
        self.recebido: list[list[Mensagem]] = []

    def conversar(self, mensagens: list[Mensagem]) -> str:
        """Registra as mensagens recebidas e devolve a próxima resposta configurada.

        Recebe:
            mensagens: lista de dicionários com role e content.
        Devolve:
            A próxima string da lista de respostas.
        Lança:
            RuntimeError: se não houver mais respostas disponíveis.
        """
        self.recebido.append([dict(m) for m in mensagens])
        if not self._respostas:
            raise RuntimeError("LLMFalso ficou sem respostas.")
        return self._respostas.pop(0)


class LLMCompativelOpenAI:
    """Cliente HTTP para APIs compatíveis com o formato chat/completions da OpenAI."""

    def __init__(
        self,
        modelo: str,
        url_base: str | None = None,
        variavel_da_chave: str = "LLM_API_KEY",
        temperatura: float = 0.0,
        tempo_limite: int = 120,
    ) -> None:
        """Configura o cliente compatível com OpenAI.

        Recebe:
            modelo: identificador do modelo no provedor.
            url_base: URL base da API (usa LLM_URL_BASE do ambiente se None).
            variavel_da_chave: nome da variável de ambiente com a chave de API.
            temperatura: grau de aleatoriedade da geração.
            tempo_limite: tempo máximo de espera por resposta, em segundos.
        """
        self.modelo = modelo
        url_resolvida = url_base or os.environ.get("LLM_URL_BASE", URL_BASE_PADRAO)
        self.url_base = url_resolvida.rstrip("/")
        self.chave = os.environ.get(variavel_da_chave, "")
        self.temperatura = temperatura
        self.tempo_limite = tempo_limite

    def conversar(self, mensagens: list[Mensagem]) -> str:
        """Envia mensagens ao endpoint /chat/completions e retorna o conteúdo gerado.

        Recebe:
            mensagens: histórico da conversa no formato role/content.
        Devolve:
            Texto da primeira escolha retornada pelo modelo.
        Lança:
            LLMIndisponivel: em falhas de rede, erros HTTP ou resposta malformada.
        """
        corpo = json.dumps(
            {
                "model": self.modelo,
                "messages": mensagens,
                "temperature": self.temperatura,
            }
        ).encode("utf-8")
        
        cabecalhos = {
            "Content-Type": "application/json",
            "User-Agent": "automatizacao-trabalho/1.0",
        }

        if self.chave:
            cabecalhos["Authorization"] = f"Bearer {self.chave}"

        pedido = urllib.request.Request(
            f"{self.url_base}/chat/completions",
            data=corpo,
            headers=cabecalhos,
            method="POST",
        )

        for tentativa in range(MAX_TENTATIVAS):
            try:
                with urllib.request.urlopen(pedido, timeout=self.tempo_limite) as resposta:
                    bruto = resposta.read().decode("utf-8")
                return _extrair_conteudo(bruto)
            except urllib.error.HTTPError as erro:
                if erro.code == 429 and tentativa < MAX_TENTATIVAS - 1:
                    time.sleep(ESPERAS_LIMITE_TAXA[tentativa])
                    continue
                raise LLMIndisponivel(f"Erro HTTP {erro.code} ao consultar o LLM.") from erro
            except (urllib.error.URLError, TimeoutError, OSError) as erro:
                raise LLMIndisponivel(f"Falha de rede ao consultar o LLM: {erro}") from erro

        raise LLMIndisponivel("Limite de tentativas excedido ao consultar o LLM.")


def _extrair_conteudo(bruto: str) -> str:
    """Extrai o texto de resposta do JSON retornado pela API compatível com OpenAI."""
    try:
        dados = json.loads(bruto)
        conteudo = dados["choices"][0]["message"]["content"]
    except (json.JSONDecodeError, KeyError, IndexError, TypeError) as erro:
        raise LLMIndisponivel("Resposta inválida recebida do servidor de LLM.") from erro

    if not isinstance(conteudo, str):
        raise LLMIndisponivel("Conteúdo da resposta do LLM não é texto.")
    return conteudo


def _carregar_env_local(caminho: Path = Path(".env")) -> None:
    """Carrega variáveis de um arquivo .env local se ainda não estiverem no ambiente."""
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        trecho = linha.strip()
        if not trecho or trecho.startswith("#") or "=" not in trecho:
            continue
        chave, valor = trecho.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip("'\"")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


def criar_llm_do_ambiente() -> LLM:
    """Cria uma instância de LLM a partir das variáveis de ambiente ou arquivo .env.

    Recebe:
        Nada (lê LLM_URL_BASE, LLM_MODELO e LLM_API_KEY).
    Devolve:
        Uma instância configurada de LLMCompativelOpenAI.
    Lança:
        LLMIndisponivel: se LLM_MODELO não estiver definido.
    """
    _carregar_env_local()
    modelo = os.environ.get("LLM_MODELO", "").strip()
    if not modelo:
        raise LLMIndisponivel("Variável LLM_MODELO não configurada no ambiente ou .env.")
    url_base = os.environ.get("LLM_URL_BASE", "").strip() or None
    return LLMCompativelOpenAI(modelo=modelo, url_base=url_base, variavel_da_chave="LLM_API_KEY")