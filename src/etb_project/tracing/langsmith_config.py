"""Build LangGraph ``RunnableConfig`` metadata/tags for LangSmith."""

from __future__ import annotations

import os
from typing import Any

from langchain_core.runnables import RunnableConfig

from etb_project.tracing.settings import get_tracing_store


def _payload_strategy_label(strategy: str | None) -> str:
    if strategy in ("dense", "hybrid"):
        return strategy
    return "omitted_uses_retriever_default"


def build_runnable_config_for_orchestrator(
    *,
    retriever_base_url: str | None,
    orch_retriever_strategy: str | None,
    payload_strategy: str | None,
    retriever_k: int,
    session_id: str | None,
    request_id: str | None,
) -> RunnableConfig | None:
    """Return a RunnableConfig for ``graph.invoke`` when tracing is enabled."""
    store = get_tracing_store()
    if not store.enabled:
        return None
    meta: dict[str, Any] = {
        "service": "etb-orchestrator",
        "retriever_base_url": retriever_base_url or None,
        "orch_retriever_strategy": orch_retriever_strategy,
        "payload_strategy": _payload_strategy_label(payload_strategy),
        "retriever_k": retriever_k,
        "session_id": session_id,
        "request_id": request_id,
    }
    return {
        "tags": ["etb", "orchestrator", "rag"],
        "metadata": meta,
    }


def build_runnable_config_for_cli(
    *,
    etb_retriever_mode: str,
    retriever_base_url: str | None,
    orch_retriever_strategy: str | None,
    payload_strategy: str | None,
    retriever_k: int,
) -> RunnableConfig | None:
    store = get_tracing_store()
    if not store.enabled:
        return None
    meta: dict[str, Any] = {
        "service": "etb-cli",
        "etb_retriever_mode": etb_retriever_mode.strip().lower(),
        "retriever_base_url": retriever_base_url or None,
        "orch_retriever_strategy": orch_retriever_strategy,
        "payload_strategy": _payload_strategy_label(payload_strategy),
        "retriever_k": retriever_k,
    }
    return {
        "tags": ["etb", "cli", "rag"],
        "metadata": meta,
    }


def remote_payload_strategy_for_cli() -> str | None:
    """When CLI uses RemoteRetriever without ORCH_RETRIEVER_STRATEGY, strategy is omitted."""
    raw = os.environ.get("ORCH_RETRIEVER_STRATEGY", "").strip().lower()
    return raw if raw in ("dense", "hybrid") else None
