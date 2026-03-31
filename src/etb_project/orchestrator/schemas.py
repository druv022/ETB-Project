from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    detail: str | None = None


class SourceOut(BaseModel):
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    k: int | None = Field(default=None, ge=1)
    return_sources: bool = True


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut] = Field(default_factory=list)
    request_id: str | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    ready: bool
    retriever_base_url: str | None = None
    llm_configured: bool
