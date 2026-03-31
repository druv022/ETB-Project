"""Environment-driven settings for the FastAPI orchestrator and agent guardrails.

CLI interactive mode reuses ``load_orchestrator_settings()`` for the same caps as HTTP
(``ETB_AGENT_*``), even though host/port/CORS apply only to the orchestrator process.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class OrchestratorSettings:
    host: str
    port: int
    retriever_base_url: str
    default_k: int

    cors_allow_origins: list[str]
    session_ttl_seconds: int

    # Passed into ``build_agent_orchestrator_graph`` (retrieve budget, tool-loop cap, context window).
    agent_max_retrieve: int
    agent_max_steps: int
    agent_max_context_chars: int


def _split_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def load_orchestrator_settings() -> OrchestratorSettings:
    """Read orchestrator bind address, retriever URL, CORS, session TTL, and agent limits from env."""
    host = os.environ.get("ETB_ORCH_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("ETB_ORCH_PORT", os.environ.get("PORT", "8001")))

    retriever_base_url = os.environ.get("RETRIEVER_BASE_URL", "").strip().rstrip("/")
    default_k = int(os.environ.get("ORCH_RETRIEVER_K", "10"))

    cors_allow_origins = _split_csv_env("ORCH_CORS_ALLOW_ORIGINS")
    session_ttl_seconds = int(os.environ.get("ORCH_SESSION_TTL_SECONDS", "7200"))

    agent_max_retrieve = int(os.environ.get("ETB_AGENT_MAX_RETRIEVE", "4"))
    agent_max_steps = int(os.environ.get("ETB_AGENT_MAX_STEPS", "10"))
    agent_max_context_chars = int(
        os.environ.get("ETB_AGENT_MAX_CONTEXT_CHARS", "48000")
    )

    return OrchestratorSettings(
        host=host,
        port=port,
        retriever_base_url=retriever_base_url,
        default_k=default_k,
        cors_allow_origins=cors_allow_origins,
        session_ttl_seconds=session_ttl_seconds,
        agent_max_retrieve=agent_max_retrieve,
        agent_max_steps=agent_max_steps,
        agent_max_context_chars=agent_max_context_chars,
    )
