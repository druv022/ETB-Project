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
from typing import Any, Literal

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from etb_project import transaction_queries
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
    SqlMeta,
    TransactionQueryRequest,
    TransactionQueryResponse,
)
from etb_project.orchestrator.session_messages import (
    deserialize_messages,
    serialize_messages,
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
    return RemoteRetriever(
        settings.retriever_base_url,
        k=k,
        timeout_s=60.0,
        strategy=settings.retriever_strategy,
    )


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
        """Session-aware chat: routes documents vs transactions vs hybrid, then answers."""
        rid = getattr(request.state, "request_id", None)
        k = body.k or settings.default_k

        retriever = _build_retriever(settings, k=k)
        llm = get_chat_llm()
        graph = build_rag_graph(llm=llm, retriever=retriever, enable_data_router=True)

        prior = deserialize_messages(sessions.get_messages(body.session_id))
        result: dict[str, Any] = graph.invoke(
            {
                "query": body.message,
                "messages": prior,
                "request_id": rid,
            }
        )
        answer = (result.get("answer") or "").strip()
        if not answer:
            raise OrchestratorAPIError(
                502,
                "EMPTY_ANSWER",
                "LLM returned an empty answer.",
            )

        messages = result.get("messages")
        if isinstance(messages, list):
            sessions.set_messages(body.session_id, serialize_messages(messages))

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

        rt = result.get("route")
        phase: Literal["clarify", "answer"] = "clarify" if rt == "clarify" else "answer"
        clarify_gate = (
            result.get("clarify_gate")
            if phase == "clarify"
            and result.get("clarify_gate") in ("documents", "transactions")
            else None
        )
        sql_meta_raw = result.get("sql_meta_out")
        sql_meta: SqlMeta | None = None
        if isinstance(sql_meta_raw, dict) and phase == "answer":
            try:
                sql_meta = SqlMeta(
                    row_count=int(sql_meta_raw.get("row_count", 0)),
                    truncated=bool(sql_meta_raw.get("truncated", False)),
                    detail=sql_meta_raw.get("detail"),
                )
            except (TypeError, ValueError):
                sql_meta = None

        return ChatResponse(
            answer=answer,
            sources=sources,
            request_id=rid,
            phase=phase,
            clarify_gate=clarify_gate,
            sql_meta=sql_meta,
        )

    @app.post(
        "/v1/transactions/query",
        response_model=TransactionQueryResponse,
        tags=["transactions"],
    )
    def transactions_query(body: TransactionQueryRequest) -> TransactionQueryResponse:
        """Return JSON-safe transaction rows from the local SQLite database."""
        try:
            result = transaction_queries.load_transactions(
                start_date=body.start_date,
                end_date=body.end_date,
                filters=body.filters,
                limit=body.limit,
                include_catalog=body.include_catalog,
            )
        except ValueError as exc:
            raise OrchestratorAPIError(
                422,
                "VALIDATION_ERROR",
                "Invalid transaction query.",
                str(exc),
            ) from exc

        df = result.dataframe
        rows = transaction_queries.dataframe_to_json_rows(df)
        detail_parts: list[str] = []
        if result.detail:
            detail_parts.append(result.detail)
        if result.truncated:
            detail_parts.append(f"Results truncated to {body.limit} rows.")
        detail_out = " ".join(detail_parts) if detail_parts else None

        return TransactionQueryResponse(
            rows=rows,
            row_count=len(rows),
            truncated=result.truncated,
            detail=detail_out,
        )

    return app
