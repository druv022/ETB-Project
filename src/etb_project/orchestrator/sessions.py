"""In-memory chat sessions for the orchestrator (message history per ``session_id``)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class SessionRecord:
    session_id: str
    messages: list[dict[str, Any]]
    updated_at: float


class InMemorySessionStore:
    """Simple session store suitable for single-process dev.

    For multi-user Docker deployments with multiple orchestrator replicas,
    replace this with Redis or another shared store.
    """

    def __init__(self, *, ttl_seconds: int) -> None:
        self._ttl = ttl_seconds
        self._data: dict[str, SessionRecord] = {}

    def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        self._gc()
        rec = self._data.get(session_id)
        if rec is None:
            return []
        return list(rec.messages)

    def set_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        now = time.time()
        self._data[session_id] = SessionRecord(
            session_id=session_id, messages=list(messages), updated_at=now
        )

    def _gc(self) -> None:
        if not self._data:
            return
        now = time.time()
        expired = [
            sid for sid, rec in self._data.items() if (now - rec.updated_at) > self._ttl
        ]
        for sid in expired:
            self._data.pop(sid, None)
