"""HTTP-friendly API errors with stable ``code`` strings."""

from __future__ import annotations


class RetrieverAPIError(Exception):
    """Raised for predictable client errors (mapped to JSON + status)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)
