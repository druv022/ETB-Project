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
    orchestrator_chat_api_key: str | None
    admin_api_token: str | None


def _split_csv_env(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [p.strip() for p in raw.split(",") if p.strip()]


def _optional_nonempty_env(name: str) -> str | None:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return None
    return str(raw).strip()


def load_orchestrator_settings() -> OrchestratorSettings:
    host = os.environ.get("ETB_ORCH_HOST", "0.0.0.0")  # nosec B104
    port = int(os.environ.get("ETB_ORCH_PORT", os.environ.get("PORT", "8001")))

    retriever_base_url = os.environ.get("RETRIEVER_BASE_URL", "").strip().rstrip("/")
    default_k = int(os.environ.get("ORCH_RETRIEVER_K", "10"))

    cors_allow_origins = _split_csv_env("ORCH_CORS_ALLOW_ORIGINS")
    session_ttl_seconds = int(os.environ.get("ORCH_SESSION_TTL_SECONDS", "7200"))

    return OrchestratorSettings(
        host=host,
        port=port,
        retriever_base_url=retriever_base_url,
        default_k=default_k,
        cors_allow_origins=cors_allow_origins,
        session_ttl_seconds=session_ttl_seconds,
        orchestrator_chat_api_key=_optional_nonempty_env("ETB_ORCHESTRATOR_API_KEY"),
        admin_api_token=_optional_nonempty_env("ETB_ADMIN_API_TOKEN"),
    )
