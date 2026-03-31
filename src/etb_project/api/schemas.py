"""Pydantic models for the retriever API (v1)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RetrieveRequest(BaseModel):
    """Body for ``POST /v1/retrieve``."""

    query: str = Field(..., min_length=1)
    k: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Top-k per sub-retriever; merged total may be up to 2*k before dedup.",
    )


class ChunkOut(BaseModel):
    """One retrieved chunk."""

    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrieveResponse(BaseModel):
    """Response for ``POST /v1/retrieve``."""

    chunks: list[ChunkOut]


class ErrorBody(BaseModel):
    """Stable error envelope."""

    code: str
    message: str
    detail: str | None = None


class HealthResponse(BaseModel):
    """``GET /v1/health`` — liveness."""

    status: str = "ok"
    service: str = "etb-retriever"


class ReadyResponse(BaseModel):
    """``GET /v1/ready`` — readiness for traffic."""

    ready: bool
    index_ready: bool
    embeddings_ok: bool
    vector_store_path: str


class IndexAcceptedResponse(BaseModel):
    """Synchronous index completion."""

    status: str = "completed"
    message: str = "Index updated successfully."


class JobAcceptedResponse(BaseModel):
    """Async index accepted."""

    job_id: str
    status: str = "pending"
    poll_url: str


class JobStatusResponse(BaseModel):
    """``GET /v1/jobs/{job_id}``."""

    job_id: str
    status: str
    message: str | None = None
    error: str | None = None
