"""Load UI auth-related secrets from environment and optional Streamlit ``st.secrets``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def _from_streamlit_secrets(key: str) -> str | None:
    try:
        import streamlit as st

        sec: Any = getattr(st, "secrets", None)
        if sec is None:
            return None
        if key in sec:
            val = sec[key]
            return str(val).strip() if val is not None else None
    except Exception:
        return None
    return None


def secret_str(env_key: str, *, st_key: str | None = None) -> str | None:
    """Read secret: ``os.environ`` first, then ``st.secrets[st_key or env_key]``."""
    raw = os.environ.get(env_key)
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip()
    sk = st_key or env_key
    return _from_streamlit_secrets(sk)


def admin_username() -> str | None:
    return secret_str("ETB_ADMIN_USERNAME")


def admin_password() -> str | None:
    return secret_str("ETB_ADMIN_PASSWORD")


def admin_api_token() -> str | None:
    return secret_str("ETB_ADMIN_API_TOKEN")


def orchestrator_api_key() -> str | None:
    return secret_str("ETB_ORCHESTRATOR_API_KEY")


def retriever_api_key() -> str | None:
    raw = os.environ.get("RETRIEVER_API_KEY")
    if raw is not None and str(raw).strip() != "":
        return str(raw).strip()
    return _from_streamlit_secrets("RETRIEVER_API_KEY")


def retriever_base_url() -> str:
    return os.getenv("RETRIEVER_BASE_URL", "http://localhost:8000").rstrip("/")


def orchestrator_base_url() -> str:
    return os.getenv("ORCHESTRATOR_BASE_URL", "http://localhost:8001").rstrip("/")


def admin_configured() -> bool:
    u, p = admin_username(), admin_password()
    return bool(u and p)


def resolve_login(
    db_path: Path,
    username: str,
    password: str,
) -> tuple[str | None, str | None]:
    """Return (role, error). role is ``admin`` or ``user`` or None."""
    from etb_project.ui.user_store import verify_user_password

    u = username.strip()
    au, ap = admin_username(), admin_password()
    if admin_configured():
        if u == (au or "").strip() and password == (ap or ""):
            return "admin", None
        if u == (au or "").strip():
            return None, "Invalid username or password."

    if verify_user_password(db_path, username, password):
        return "user", None
    return None, "Invalid username or password."
