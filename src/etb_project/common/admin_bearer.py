"""Validate ``ETB_ADMIN_API_TOKEN`` bearer headers with constant-time compare."""

from __future__ import annotations

import hmac
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_bearer = HTTPBearer(auto_error=False)


def constant_time_token_match(presented: str | None, expected: str) -> bool:
    """Compare bearer tokens in fixed-size constant-time byte space."""
    try:
        presented_bytes = (presented or "").encode("utf-8")
        expected_bytes = expected.encode("utf-8")
        max_len = max(128, len(expected_bytes), len(presented_bytes))
        presented_fixed = presented_bytes[:max_len].ljust(max_len, b"\x00")
        expected_fixed = expected_bytes[:max_len].ljust(max_len, b"\x00")
        payload_match = hmac.compare_digest(presented_fixed, expected_fixed)
        length_match = hmac.compare_digest(
            len(presented_bytes).to_bytes(8, "big"),
            len(expected_bytes).to_bytes(8, "big"),
        )
        return payload_match and length_match
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
