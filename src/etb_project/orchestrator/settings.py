"""Environment-driven settings for the Orchestrator HTTP API.

The orchestrator is the "brains" layer:
- Owns the chat endpoint and session memory.
- Calls the Retriever API for context (and proxies assets for the UI).
- Calls the chat LLM to produce the final answer.

Configuration is env-driven so Docker compose can wire services together without
requiring code changes.
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
    # Seconds for httpx read timeout on ``POST /v1/retrieve`` (same env as CLI remote mode).
    retriever_timeout_s: float
    # When ``dense`` or ``hybrid``, forwarded as JSON ``strategy`` on ``POST /v1/retrieve``.
    retriever_strategy: str | None

    cors_allow_origins: list[str]
    session_ttl_seconds: int


def _split_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def load_orchestrator_settings() -> OrchestratorSettings:
    host = os.environ.get("ETB_ORCH_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("ETB_ORCH_PORT", os.environ.get("PORT", "8001")))

    retriever_base_url = os.environ.get("RETRIEVER_BASE_URL", "").strip().rstrip("/")
    default_k = int(os.environ.get("ORCH_RETRIEVER_K", "10"))
    retriever_timeout_s = float(os.environ.get("RETRIEVER_TIMEOUT_S", "60"))

    strat_raw = os.environ.get("ORCH_RETRIEVER_STRATEGY", "").strip().lower()
    retriever_strategy = strat_raw if strat_raw in ("dense", "hybrid") else None

    cors_allow_origins = _split_csv_env("ORCH_CORS_ALLOW_ORIGINS")
    session_ttl_seconds = int(os.environ.get("ORCH_SESSION_TTL_SECONDS", "7200"))

    return OrchestratorSettings(
        host=host,
        port=port,
        retriever_base_url=retriever_base_url,
        default_k=default_k,
        retriever_timeout_s=retriever_timeout_s,
        retriever_strategy=retriever_strategy,
        cors_allow_origins=cors_allow_origins,
        session_ttl_seconds=session_ttl_seconds,
    )
