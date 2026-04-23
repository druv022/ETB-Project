"""Tests for etb_project.models provider selection (no network)."""

from __future__ import annotations

import pytest


def test_get_chat_llm_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from etb_project import models

    monkeypatch.setenv("ETB_LLM_PROVIDER", "does-not-exist")
    with pytest.raises(ValueError, match="Unsupported ETB_LLM_PROVIDER"):
        models.get_chat_llm()


def test_get_chat_llm_openai_compat_builds_chatopenai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from etb_project import models

    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_MODEL", "stepfun/step-3.5-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    llm = models.get_chat_llm()
    assert llm.__class__.__name__ == "ChatOpenAI"


def test_get_chat_llm_openai_compat_falls_back_to_openrouter_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docker `.env` often sets OPENROUTER_API_KEY only; nested Compose substitution may skip OPENAI_API_KEY."""
    from etb_project import models

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-from-env")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    llm = models.get_chat_llm()
    assert llm.__class__.__name__ == "ChatOpenAI"
    key = getattr(llm, "openai_api_key", None)
    assert key is not None
    revealed = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key)
    assert revealed == "sk-or-v1-from-env"


def test_get_chat_llm_ollama_builds_chatollama(monkeypatch: pytest.MonkeyPatch) -> None:
    from etb_project import models

    monkeypatch.setenv("ETB_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_CHAT_MODEL", "qwen3.5:9b")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    llm = models.get_chat_llm()
    assert llm.__class__.__name__ == "ChatOllama"
