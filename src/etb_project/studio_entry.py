"""LangGraph Studio entry: same agent graph as production, HTTP retriever + Ollama LLM."""

from __future__ import annotations

import os

from etb_project.config import load_config
from etb_project.models import get_ollama_llm as get_llm
from etb_project.orchestrator.agent_graph import build_agent_orchestrator_graph
from etb_project.orchestrator.settings import load_orchestrator_settings
from etb_project.retrieval import RemoteRetriever


def rag_app() -> object:
    """
    LangGraph entrypoint for Studio / langgraph dev.

    Requires ``RETRIEVER_BASE_URL`` pointing at the standalone retriever service
    (same HTTP contract as the orchestrator). Inputs may include ``{"query": "..."}``.
    """
    base = os.environ.get("RETRIEVER_BASE_URL", "").strip().rstrip("/")
    if not base:
        raise ValueError(
            "Set RETRIEVER_BASE_URL to the retriever HTTP API (e.g. http://localhost:8000)."
        )
    config = load_config()
    orch = load_orchestrator_settings()
    timeout_s = float(os.environ.get("RETRIEVER_TIMEOUT_S", "60"))
    # Studio does not use the FastAPI session store; pass history via graph state in the UI if needed.
    retriever = RemoteRetriever(
        base,
        k=config.retriever_k,
        timeout_s=timeout_s,
    )
    llm = get_llm()
    return build_agent_orchestrator_graph(
        llm=llm,
        retriever=retriever,
        max_retrieve=orch.agent_max_retrieve,
        max_steps=orch.agent_max_steps,
        max_context_chars=orch.agent_max_context_chars,
        grounded_finalize_mode=orch.grounded_finalize_mode,
        writer_max_steps=orch.writer_max_steps,
        writer_max_retrieve=orch.writer_max_retrieve,
        writer_max_context_chars=orch.writer_max_context_chars,
        writer_max_messages=orch.writer_max_messages,
        writer_session_messages=orch.writer_session_messages,
    )
