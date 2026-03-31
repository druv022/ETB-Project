from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any, cast

import numpy as np
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI


def _normalize_embed_documents_for_faiss(out: Any, num_texts: int) -> list[list[float]]:
    """Coerce ``embed_documents`` output so FAISS gets a 2D stack.

    LangChain FAISS does ``np.array(embeddings)`` then ``index.add``. If a backend
    returns a single document as a flat ``[float, ...]`` instead of
    ``[[float, ...]]``, the array is 1D and faiss raises
    ``ValueError: not enough values to unpack (expected 2, got 1)``.
    """
    if num_texts == 0:
        return []
    if isinstance(out, np.ndarray):
        if out.ndim == 2 and out.shape[0] == num_texts:
            return cast(list[list[float]], out.astype(np.float64).tolist())
        if out.ndim == 1 and num_texts == 1:
            return cast(list[list[float]], [out.astype(np.float64).tolist()])
        raise ValueError(
            f"Cannot normalize embedding array with shape {out.shape} for {num_texts} text(s)"
        )
    if isinstance(out, tuple):
        out = list(out)
    if not isinstance(out, list):
        raise TypeError(
            f"embed_documents must return list or ndarray, got {type(out).__name__}"
        )
    if not out:
        return []
    if num_texts == 1 and isinstance(out[0], (int, float, np.floating)):
        return [list(map(float, out))]
    result: list[list[float]] = []
    for row in out:
        if isinstance(row, np.ndarray):
            result.append(row.astype(np.float64).tolist())
        elif isinstance(row, list):
            result.append(list(map(float, row)))
        else:
            result.append([float(row)])
    return result


class FaissCompatibleEmbeddings(Embeddings):
    """Wraps an :class:`Embeddings` so document batches are always stacked for FAISS."""

    def __init__(self, inner: Embeddings) -> None:
        self._inner = inner

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raw = self._inner.embed_documents(texts)
        return _normalize_embed_documents_for_faiss(raw, len(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._inner.embed_query(text)


def get_openai_llm(model: str = "gpt-4o-mini", temperature: float = 0) -> ChatOpenAI:
    llm = ChatOpenAI(model=model, temperature=temperature)
    return llm


class ChatModelProvider(ABC):
    """Base class for chat model providers.

    This keeps LLM construction in one place and allows the orchestrator (and
    other runtime code under `src/`) to select a provider via environment
    variables without importing provider-specific factories everywhere.
    """

    name: str

    @abstractmethod
    def build_chat_model(self) -> BaseChatModel: ...


class OpenAICompatibleProvider(ChatModelProvider):
    """OpenAI-compatible chat provider (also supports OpenRouter via base URL)."""

    name = "openai_compat"

    def build_chat_model(self) -> BaseChatModel:
        model = os.environ.get("OPENAI_MODEL", "stepfun/step-3.5-flash").strip()
        temperature = float(os.environ.get("OPENAI_TEMPERATURE", "0"))

        kwargs: dict[str, Any] = {"model": model, "temperature": temperature}

        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key and api_key.strip():
            kwargs["api_key"] = api_key.strip()

        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url and base_url.strip():
            kwargs["base_url"] = base_url.strip()

        return ChatOpenAI(**kwargs)


class OllamaChatProvider(ChatModelProvider):
    """Ollama-backed chat provider."""

    name = "ollama"

    def build_chat_model(self) -> BaseChatModel:
        model = os.environ.get("OLLAMA_CHAT_MODEL", "qwen3.5:9b").strip()
        temperature = float(os.environ.get("OLLAMA_TEMPERATURE", "0"))
        return get_ollama_llm(model=model, temperature=temperature)


PROVIDERS: dict[str, ChatModelProvider] = {
    OpenAICompatibleProvider.name: OpenAICompatibleProvider(),
    OllamaChatProvider.name: OllamaChatProvider(),
}


def get_chat_llm() -> BaseChatModel:
    """Select and build the chat LLM for runtime orchestration.

    Uses:
    - ETB_LLM_PROVIDER: 'openai_compat' (default) or 'ollama'
    - Provider-specific env vars (OPENAI_* or OLLAMA_*)
    """

    provider = os.environ.get("ETB_LLM_PROVIDER", "openai_compat").strip().lower()
    p = PROVIDERS.get(provider)
    if p is None:
        raise ValueError(
            f"Unsupported ETB_LLM_PROVIDER={provider!r}. "
            f"Supported: {', '.join(sorted(PROVIDERS.keys()))}"
        )
    return p.build_chat_model()


def _ollama_base_url() -> str | None:
    """Host URL for Ollama HTTP API (ollama-python uses ``OLLAMA_HOST``; we also honor ``OLLAMA_BASE_URL``)."""
    raw = os.environ.get("OLLAMA_HOST") or os.environ.get("OLLAMA_BASE_URL")
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip()


def get_ollama_llm(model: str = "qwen3.5:9b", temperature: float = 0) -> ChatOllama:
    bu = _ollama_base_url()
    if bu:
        return ChatOllama(model=model, temperature=temperature, base_url=bu)
    return ChatOllama(model=model, temperature=temperature)


def get_ollama_embedding_model(model: str = "qwen3-embedding:0.6b") -> Embeddings:
    bu = _ollama_base_url()
    inner = (
        OllamaEmbeddings(model=model, base_url=bu)
        if bu
        else OllamaEmbeddings(model=model)
    )
    return FaissCompatibleEmbeddings(inner)


if __name__ == "__main__":
    print(get_ollama_llm().invoke("Hello, how are you?"))
