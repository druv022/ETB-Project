"""HTTP-style errors for the orchestrator (mapped to JSON by FastAPI handlers)."""

from __future__ import annotations


class OrchestratorAPIError(Exception):
    """Predictable API failure with status code and stable machine ``code``."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.detail = detail
