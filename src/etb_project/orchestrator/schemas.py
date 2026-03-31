from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class SourceOut(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """One user turn for the agentic orchestrator (history is server-side per ``session_id``)."""

    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    return_sources: bool = True


class ChatResponse(BaseModel):
    """Agent reply; ``phase`` distinguishes clarify-only vs grounded answer paths."""

    answer: str
    sources: list[SourceOut] = Field(default_factory=list)
    request_id: str | None = None
    phase: Literal["clarify", "answer"] | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    ready: bool
    retriever_base_url: str | None = None
    llm_configured: bool
