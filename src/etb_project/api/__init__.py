"""HTTP API for dual FAISS retrieval and PDF indexing (no RAG graph)."""

from __future__ import annotations

from typing import Any

__all__ = ["create_app"]


def __getattr__(name: str) -> Any:
    """Lazy import so ``etb_project.api.schemas`` does not pull in the full FastAPI app."""
    if name == "create_app":
        from etb_project.api.app import create_app

        return create_app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
