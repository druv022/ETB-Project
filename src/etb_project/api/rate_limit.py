"""Simple in-memory rate limiter (per client IP).

This is a small guardrail for local dev / demo deployments to prevent accidental
hammering (e.g. UI refresh loops or scripts). It is not meant to be a
cryptographically strong abuse prevention system.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class RateLimiter:
    """Sliding window: max ``n`` requests per 60 seconds per key."""

    def __init__(self, max_per_minute: int) -> None:
        self._max = max(1, max_per_minute)
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - 60.0
        with self._lock:
            dq = self._windows.setdefault(key, deque())
            while dq and dq[0] < cutoff:
                dq.popleft()
            if len(dq) >= self._max:
                return False
            dq.append(now)
            return True
