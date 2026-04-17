"""Validate ``ETB_ADMIN_API_TOKEN`` bearer headers with constant-time compare."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_bearer = HTTPBearer(auto_error=False)


def constant_time_equals(a: str, b: str) -> bool:
    """Compare two strings in constant time (UTF-8 bytes)."""
    try:
        return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))
    except Exception:
        return False


def constant_time_token_match(presented: str | None, expected: str) -> bool:
    """Compare bearer tokens via fixed-size digests to reduce timing signal leakage."""
    try:
        presented_digest = hashlib.sha256((presented or "").encode("utf-8")).digest()
        expected_digest = hashlib.sha256(expected.encode("utf-8")).digest()
        return hmac.compare_digest(presented_digest, expected_digest)
    except Exception:
        return False


def require_admin_bearer_token(
    expected_token: str | None,
) -> Callable[..., Coroutine[Any, Any, None]]:
    """Return a FastAPI dependency that enforces Bearer token when ``expected_token`` is set."""

    async def _dep(
        creds: HTTPAuthorizationCredentials | None = Depends(security_bearer),
    ) -> None:
        if not expected_token:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": "Admin API is not enabled."},
            )
        presented = creds.credentials if creds else None
        if not constant_time_token_match(presented, expected_token):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing admin bearer token.",
                },
            )

    return _dep
