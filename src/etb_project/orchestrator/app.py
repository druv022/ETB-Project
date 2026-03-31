"""FastAPI Orchestrator service for chat-style RAG.

This service:
- Receives chat messages from the UI
- Retrieves context via the standalone Retriever API (remote mode)
- Generates an answer using an OpenAI-compatible chat backend
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from etb_project.graph_rag import build_rag_graph
from etb_project.models import get_chat_llm
from etb_project.orchestrator.exceptions import OrchestratorAPIError
from etb_project.orchestrator.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorBody,
    HealthResponse,
    ReadyResponse,
    SourceOut,
)
from etb_project.orchestrator.sessions import InMemorySessionStore
from etb_project.orchestrator.settings import (
    OrchestratorSettings,
    load_orchestrator_settings,
)
from etb_project.retrieval import RemoteRetriever

logger = logging.getLogger(__name__)

_settings: OrchestratorSettings | None = None
_sessions: InMemorySessionStore | None = None


def get_settings() -> OrchestratorSettings:
    if _settings is None:
        raise RuntimeError("Orchestrator API not initialized")
    return _settings


def get_sessions() -> InMemorySessionStore:
    if _sessions is None:
        raise RuntimeError("Orchestrator API not initialized")
    return _sessions


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = rid
        start = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception(
                "request_failed request_id=%s path=%s duration_ms=%.2f",
                rid,
                request.url.path,
                duration_ms,
            )
            raise
        duration_ms = (time.monotonic() - start) * 1000
        response.headers["X-Request-ID"] = rid
        logger.info(
            "request request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
            rid,
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            duration_ms,
        )
        return response


def _error_response(
    status_code: int,
    code: str,
    message: str,
    detail: str | None = None,
) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _build_retriever(settings: OrchestratorSettings, k: int) -> RemoteRetriever:
    if not settings.retriever_base_url:
        raise OrchestratorAPIError(
            500,
            "CONFIG_ERROR",
            "RETRIEVER_BASE_URL is not configured for the orchestrator.",
        )
    return RemoteRetriever(settings.retriever_base_url, k=k, timeout_s=60.0)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        global _settings, _sessions
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        _settings = load_orchestrator_settings()
        _sessions = InMemorySessionStore(ttl_seconds=_settings.session_ttl_seconds)
        logger.info(
            "Orchestrator API started; retriever_base_url=%s",
            _settings.retriever_base_url or "(unset)",
        )
        yield

    app = FastAPI(
        title="ETB Orchestrator API",
        version="1.0.0",
        description="Chat orchestration service (LangGraph RAG + remote retriever).",
        lifespan=lifespan,
    )
    app.add_middleware(RequestLoggingMiddleware)

    # CORS is optional; for docker-compose local dev it can stay unset.
    settings = load_orchestrator_settings()
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.exception_handler(OrchestratorAPIError)
    async def _api_error_handler(
        request: Request, exc: OrchestratorAPIError
    ) -> JSONResponse:
        return _error_response(exc.status_code, exc.code, exc.message, exc.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            422,
            "VALIDATION_ERROR",
            "Request validation failed.",
            str(exc.errors())[:2000],
        )

    @app.get("/v1/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/v1/ready", response_model=ReadyResponse, tags=["health"])
    async def ready(
        settings: OrchestratorSettings = Depends(get_settings),
    ) -> ReadyResponse:
        try:
            get_chat_llm()
            llm_ok = True
        except Exception:
            llm_ok = False
        ready_flag = bool(settings.retriever_base_url and llm_ok)
        return ReadyResponse(
            ready=ready_flag,
            retriever_base_url=settings.retriever_base_url or None,
            llm_configured=llm_ok,
        )

    @app.get("/v1/assets/{asset_path:path}", tags=["assets"])
    async def asset_proxy(
        request: Request,
        asset_path: str,
        settings: OrchestratorSettings = Depends(get_settings),
    ) -> Response:
        """Proxy asset bytes from the Retriever API.

        The Retriever owns the document_output_dir artifacts; the orchestrator
        exposes them to the UI so Streamlit only needs one base URL.
        """
        if not settings.retriever_base_url:
            raise OrchestratorAPIError(
                500,
                "CONFIG_ERROR",
                "RETRIEVER_BASE_URL is not configured for the orchestrator.",
            )
        base = settings.retriever_base_url.rstrip("/")
        url = f"{base}/v1/assets/{asset_path}"
        headers: dict[str, str] = {}
        auth = request.headers.get("authorization")
        if auth:
            headers["authorization"] = auth

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=headers)
        except httpx.RequestError as exc:
            raise OrchestratorAPIError(
                502,
                "RETRIEVER_UNREACHABLE",
                "Retriever service unreachable while fetching asset.",
                str(exc)[:1000],
            ) from exc

        if resp.status_code == 401:
            raise OrchestratorAPIError(
                401, "UNAUTHORIZED", "Invalid or missing bearer token."
            )
        if resp.status_code == 404:
            raise OrchestratorAPIError(404, "ASSET_NOT_FOUND", "Asset not found.")
        if resp.status_code == 400:
            raise OrchestratorAPIError(400, "BAD_REQUEST", "Invalid asset path.")
        if resp.status_code >= 400:
            raise OrchestratorAPIError(
                502,
                "ASSET_PROXY_FAILED",
                "Failed to fetch asset from retriever.",
                f"status={resp.status_code} body={resp.text[:500]}",
            )

        media_type = resp.headers.get("content-type") or "application/octet-stream"
        return Response(content=resp.content, media_type=media_type)

    @app.post("/v1/chat", response_model=ChatResponse, tags=["chat"])
    async def chat(
        request: Request,
        body: ChatRequest,
        settings: OrchestratorSettings = Depends(get_settings),
        sessions: InMemorySessionStore = Depends(get_sessions),
    ) -> ChatResponse:
        rid = getattr(request.state, "request_id", None)
        k = body.k or settings.default_k

        retriever = _build_retriever(settings, k=k)
        llm = get_chat_llm()
        graph = build_rag_graph(llm=llm, retriever=retriever)

        # Phase 1: minimal per-turn invocation; keep messages for future multi-turn upgrades.
        prior = sessions.get_messages(body.session_id)
        result: dict[str, Any] = graph.invoke(
            {"query": body.message, "messages": prior}
        )
        answer = (result.get("answer") or "").strip()
        if not answer:
            raise OrchestratorAPIError(
                502,
                "EMPTY_ANSWER",
                "LLM returned an empty answer.",
            )

        # Persist messages back if present.
        messages = result.get("messages")
        if isinstance(messages, list):
            sessions.set_messages(body.session_id, messages)

        sources: list[SourceOut] = []
        if body.return_sources:
            docs = result.get("context_docs") or []
            for d in docs:
                try:
                    sources.append(
                        SourceOut(
                            content=str(getattr(d, "page_content", "")),
                            metadata=dict(getattr(d, "metadata", {}) or {}),
                        )
                    )
                except Exception:
                    continue

        return ChatResponse(answer=answer, sources=sources, request_id=rid)

    return app
