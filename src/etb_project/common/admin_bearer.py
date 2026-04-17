"""Validate ``ETB_ADMIN_API_TOKEN`` bearer headers with constant-time compare."""

from __future__ import annotations

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
        presented = creds.credentials if creds else ""
        if not presented or not constant_time_equals(presented, expected_token):
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or missing admin bearer token.",
                },
            )

    return _dep
