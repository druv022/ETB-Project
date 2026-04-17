"""Thread-safe in-memory tracing flags (env boot defaults + HTTP PUT overrides)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _boot_langchain_tracing_v2() -> bool:
    """Value read at process start; not overridden by PUT (may require restart)."""
    return _env_bool("LANGCHAIN_TRACING_V2", True)


@dataclass
class TracingStore:
    """Mutable tracing toggles; `ETB_TRACE_*` env defaults are **on** when unset."""

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    enabled: bool = field(default_factory=lambda: _env_bool("ETB_TRACE_ENABLED", True))
    log_queries: bool = field(
        default_factory=lambda: _env_bool("ETB_TRACE_LOG_QUERIES", True)
    )

    def snapshot(self) -> dict[str, bool]:
        """Effective flags plus boot LangChain tracing (informational)."""
        with self._lock:
            return {
                "enabled": self.enabled,
                "log_queries": self.log_queries,
                "langchain_tracing_v2_boot": _boot_langchain_tracing_v2(),
            }

    def apply_partial(
        self, *, enabled: bool | None = None, log_queries: bool | None = None
    ) -> None:
        with self._lock:
            if enabled is not None:
                self.enabled = enabled
            if log_queries is not None:
                self.log_queries = log_queries


_store = TracingStore()


def get_tracing_store() -> TracingStore:
    """Process-wide tracing store (orchestrator + retriever + CLI share module state per process)."""
    return _store
