"""In-memory ring buffer of recent HTTP request summaries for admin audit logs."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

_MAX_DEFAULT = 500
_SENSITIVE_QUERY_KEYS = re.compile(
    r"(^|&)(token|key|password|secret|authorization)=([^&]*)",
    re.IGNORECASE,
)


def redact_query_string(qs: str | None) -> str:
    if not qs:
        return ""
    return _SENSITIVE_QUERY_KEYS.sub(r"\1\2=[REDACTED]", qs)


@dataclass(frozen=True)
class AuditLogEntry:
    ts: str
    service: str
    method: str
    path: str
    status: int
    duration_ms: float


class HttpAuditRingBuffer:
    def __init__(self, maxlen: int = _MAX_DEFAULT) -> None:
        self._buf: deque[AuditLogEntry] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def append(
        self,
        *,
        service: str,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
    ) -> None:
        ts = datetime.now(timezone.utc).isoformat()
        entry = AuditLogEntry(
            ts=ts,
            service=service,
            method=method,
            path=path,
            status=status,
            duration_ms=duration_ms,
        )
        with self._lock:
            self._buf.append(entry)

    def recent(self, limit: int) -> list[AuditLogEntry]:
        cap = max(1, min(limit, _MAX_DEFAULT))
        with self._lock:
            items = list(self._buf)
        return items[-cap:]

    def as_dicts(self, limit: int) -> list[dict[str, Any]]:
        return [
            {
                "ts": e.ts,
                "service": e.service,
                "method": e.method,
                "path": e.path,
                "status": e.status,
                "duration_ms": round(e.duration_ms, 2),
            }
            for e in self.recent(limit)
        ]


def monotonic_ms() -> float:
    return time.monotonic() * 1000.0
