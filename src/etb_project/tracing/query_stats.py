"""Query redaction for LangSmith traces."""

from __future__ import annotations

import hashlib
from typing import Any

from etb_project.tracing.settings import get_tracing_store


def query_stats_for_trace(query: str) -> dict[str, Any]:
    """Return a JSON-safe dict for trace inputs (preview or hash only)."""
    store = get_tracing_store()
    if not store.log_queries:
        digest = hashlib.sha256(query.encode("utf-8")).hexdigest()
        return {
            "length": len(query),
            "sha256_prefix": digest[:16],
        }
    preview = query if len(query) <= 200 else query[:200] + "..."
    return {"length": len(query), "preview": preview}
