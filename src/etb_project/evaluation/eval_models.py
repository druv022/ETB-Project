"""OpenAI clients and RAGAS factories used for metric scoring (RAGAS 0.4.x)."""

from __future__ import annotations

import os
from typing import Any


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    if v is None:
        return default
    v = v.strip()
    return v or default


def build_openai_client() -> Any:
    """Sync OpenAI client for ``llm_factory`` / ``embedding_factory``."""
    from openai import OpenAI

    api_key = _env("ETB_EVAL_OPENAI_API_KEY") or _env("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "RAGAS metrics require an API key. Set ETB_EVAL_OPENAI_API_KEY or OPENAI_API_KEY."
        )
    base_url = _env("ETB_EVAL_OPENAI_BASE_URL") or _env("OPENAI_BASE_URL")
    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def build_ragas_scoring_llm_and_embeddings() -> tuple[Any, Any]:
    """Build RAGAS LLM + embedding models for Faithfulness, AnswerRelevancy, etc."""
    try:
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            'ragas is not installed. Install with: pip install -e ".[eval]"'
        ) from exc

    client = build_openai_client()
    model = _env("ETB_EVAL_METRICS_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
    emb_model = _env("ETB_EVAL_EMBEDDING_MODEL", "text-embedding-3-small") or (
        "text-embedding-3-small"
    )
    llm = llm_factory(model, provider="openai", client=client)
    embeddings = embedding_factory("openai", model=emb_model, client=client)
    return llm, embeddings
