"""FastAPI routes for GET/PUT ``/v1/tracing`` (curl-friendly runtime toggles)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from etb_project.tracing.settings import get_tracing_store


class TracingPutBody(BaseModel):
    """Partial update: only set fields are applied."""

    enabled: bool | None = Field(
        default=None,
        description="Enable ETB traceable spans and RunnableConfig metadata.",
    )
    log_queries: bool | None = Field(
        default=None,
        description="When true, include truncated query previews in traces; when false, hash prefix only.",
    )


class TracingResponse(BaseModel):
    service: str
    enabled: bool
    log_queries: bool
    langchain_tracing_v2_boot: bool


def build_tracing_router(
    service_name: str,
    *,
    put_dependencies: Sequence[Any] = (),
) -> APIRouter:
    router = APIRouter(prefix="/v1", tags=["tracing"])

    @router.get("/tracing", response_model=TracingResponse)
    async def get_tracing() -> TracingResponse:
        snap = get_tracing_store().snapshot()
        return TracingResponse(service=service_name, **snap)

    @router.put(
        "/tracing", response_model=TracingResponse, dependencies=list(put_dependencies)
    )
    async def put_tracing(body: TracingPutBody) -> TracingResponse:
        get_tracing_store().apply_partial(
            enabled=body.enabled, log_queries=body.log_queries
        )
        snap = get_tracing_store().snapshot()
        return TracingResponse(service=service_name, **snap)

    return router
