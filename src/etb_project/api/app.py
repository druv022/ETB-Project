"""FastAPI application for the standalone retriever service (v1)."""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from etb_project.api.exceptions import RetrieverAPIError
from etb_project.api.indexing import run_index_pdfs
from etb_project.api.jobs import JobRegistry
from etb_project.api.rate_limit import RateLimiter
from etb_project.api.schemas import (
    ChunkOut,
    ErrorBody,
    HealthResponse,
    IndexAcceptedResponse,
    JobAcceptedResponse,
    JobStatusResponse,
    ReadyResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from etb_project.api.settings import RetrieverAPISettings, load_api_settings
from etb_project.api.state import RetrieverServiceState, _serialize_metadata

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

_settings: RetrieverAPISettings | None = None
_state: RetrieverServiceState | None = None
_jobs: JobRegistry | None = None
_rate_limiter: RateLimiter | None = None
_index_exclusive = threading.Lock()
_shutting_down = threading.Event()


def get_settings() -> RetrieverAPISettings:
    if _settings is None:
        raise RuntimeError("Retriever API not initialized")
    return _settings


def get_state() -> RetrieverServiceState:
    if _state is None:
        raise RuntimeError("Retriever API not initialized")
    return _state


def get_jobs() -> JobRegistry:
    if _jobs is None:
        raise RuntimeError("Retriever API not initialized")
    return _jobs


def get_rate_limiter() -> RateLimiter:
    if _rate_limiter is None:
        raise RuntimeError("Retriever API not initialized")
    return _rate_limiter


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


class AssetTraversalGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        raw_path = request.scope.get("raw_path")
        if isinstance(raw_path, (bytes, bytearray)):
            raw = bytes(raw_path)
            raw_l = raw.lower()
            if raw_l.startswith(b"/v1/assets/") and (
                b"/../" in raw_l or raw_l.endswith(b"/..") or b"%2e%2e" in raw_l
            ):
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid asset path."}
                )
        return await call_next(request)


def _error_response(
    status_code: int,
    code: str,
    message: str,
    detail: str | None = None,
) -> JSONResponse:
    body = ErrorBody(code=code, message=message, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return str(forwarded).split(",")[0].strip()
    if request.client:
        return str(request.client.host)
    return "unknown"


async def require_api_key_if_configured(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    settings: RetrieverAPISettings = Depends(get_settings),
) -> None:
    if settings.api_key is None:
        return
    token = creds.credentials if creds else None
    if token != settings.api_key:
        raise RetrieverAPIError(
            status_code=401,
            code="UNAUTHORIZED",
            message="Invalid or missing bearer token.",
        )


def _run_index_sync(
    pdf_paths: list[str],
    reset: bool,
    job_id: str | None,
) -> None:
    st = get_state()
    cfg = get_settings()
    job_reg = get_jobs()
    chunk_size = int(os.environ.get("ETB_CHUNK_SIZE", "1000"))
    chunk_overlap = int(os.environ.get("ETB_CHUNK_OVERLAP", "200"))
    try:
        if job_id:
            job_reg.update(job_id, status="running", message="Indexing…")
        paths = [Path(p) for p in pdf_paths]
        run_index_pdfs(
            paths,
            reset=reset,
            settings=cfg,
            state=st,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        if job_id:
            job_reg.update(
                job_id,
                status="completed",
                message="Index updated successfully.",
            )
    except ValueError as exc:
        msg = str(exc).lower()
        if "chunk" in msg or "embedding" in msg:
            if job_id:
                job_reg.update(job_id, status="failed", error=str(exc))
            raise RetrieverAPIError(
                409,
                "INDEX_CONFLICT",
                str(exc),
            ) from exc
        if job_id:
            job_reg.update(job_id, status="failed", error=str(exc))
        raise RetrieverAPIError(
            400,
            "INDEX_VALIDATION_ERROR",
            str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("index_failed")
        if job_id:
            job_reg.update(job_id, status="failed", error=str(exc))
        raise RetrieverAPIError(
            500,
            "INDEX_FAILED",
            "Indexing failed.",
            str(exc)[:1000],
        ) from exc


def _index_job_wrapper(job_id: str, paths: list[str], reset: bool) -> None:
    if not _index_exclusive.acquire(blocking=False):
        get_jobs().update(
            job_id,
            status="failed",
            error="INDEX_BUSY: another indexing operation is in progress.",
        )
        return
    try:
        _run_index_sync(paths, reset, job_id)
    finally:
        _index_exclusive.release()


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        global _settings, _state, _jobs, _rate_limiter
        # Each TestClient instance creates a new app, but globals persist across tests.
        # Reset shutdown flag so subsequent app instances behave correctly.
        _shutting_down.clear()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        _settings = load_api_settings()
        logging.getLogger().setLevel(
            getattr(logging, _settings.log_level, logging.INFO)
        )
        _state = RetrieverServiceState(_settings.vector_store_path)
        _jobs = JobRegistry()
        _rate_limiter = RateLimiter(_settings.rate_limit_per_minute)
        _state.vector_store_root.mkdir(parents=True, exist_ok=True)
        _settings.document_output_dir.mkdir(parents=True, exist_ok=True)
        _settings.upload_dir.mkdir(parents=True, exist_ok=True)
        if _state.index_ready():
            _state.reload_after_index()
        logger.info(
            "Retriever API started; vector_store_path=%s", _settings.vector_store_path
        )
        yield
        _shutting_down.set()
        logger.info("Retriever API shutdown requested")

    app = FastAPI(
        title="ETB Retriever API",
        version="1.0.0",
        description="Dual FAISS retrieval and PDF indexing (no RAG graph).",
        lifespan=lifespan,
    )
    app.add_middleware(AssetTraversalGuardMiddleware)
    app.add_middleware(RequestLoggingMiddleware)

    @app.exception_handler(RetrieverAPIError)
    async def _retriever_api_error_handler(
        request: Request, exc: RetrieverAPIError
    ) -> JSONResponse:
        return _error_response(
            exc.status_code,
            exc.code,
            exc.message,
            exc.detail,
        )

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
        state: RetrieverServiceState = Depends(get_state),
        settings: RetrieverAPISettings = Depends(get_settings),
    ) -> ReadyResponse:
        idx = state.index_ready()
        emb_ok = state.embeddings_ping()
        ready_flag = bool(idx and emb_ok)
        return ReadyResponse(
            ready=ready_flag,
            index_ready=idx,
            embeddings_ok=emb_ok,
            vector_store_path=str(settings.vector_store_path),
        )

    @app.get(
        "/v1/assets/{asset_path:path}",
        tags=["assets"],
        dependencies=[Depends(require_api_key_if_configured)],
    )
    async def asset(
        asset_path: str,
        settings: RetrieverAPISettings = Depends(get_settings),
    ) -> FileResponse:
        """Serve extracted artifacts (images) from document_output_dir.

        The path is resolved under document_output_dir and guarded against
        path traversal.
        """
        root = settings.document_output_dir.resolve()
        candidate = (root / asset_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid asset path.") from exc
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Asset not found.")
        return FileResponse(path=str(candidate))

    @app.post(
        "/v1/retrieve",
        response_model=RetrieveResponse,
        tags=["retrieve"],
        dependencies=[Depends(require_api_key_if_configured)],
    )
    async def retrieve(
        request: Request,
        body: RetrieveRequest,
        state: RetrieverServiceState = Depends(get_state),
        settings: RetrieverAPISettings = Depends(get_settings),
    ) -> RetrieveResponse:
        if _shutting_down.is_set():
            raise RetrieverAPIError(
                503,
                "SERVICE_UNAVAILABLE",
                "Service is shutting down.",
            )
        rl = get_rate_limiter()
        if not rl.allow(_client_ip(request) + ":retrieve"):
            raise RetrieverAPIError(
                429,
                "RATE_LIMITED",
                "Too many requests.",
            )
        cl = request.headers.get("content-length")
        if cl is not None:
            try:
                if int(cl) > settings.retrieve_body_max_bytes:
                    raise RetrieverAPIError(
                        413,
                        "PAYLOAD_TOO_LARGE",
                        "Request body exceeds limit.",
                    )
            except ValueError:
                pass

        if len(body.query) > settings.max_query_chars:
            raise RetrieverAPIError(
                400,
                "QUERY_TOO_LONG",
                f"Query exceeds {settings.max_query_chars} characters.",
            )

        k = body.k if body.k is not None else settings.default_retriever_k
        k = min(k, settings.max_retrieve_k)

        try:
            docs = state.retrieve(body.query, k)
        except FileNotFoundError:
            raise RetrieverAPIError(
                503,
                "INDEX_NOT_READY",
                "Vector index is not available. Build or upload documents first.",
                str(state.vector_store_root),
            ) from None
        except Exception as exc:
            logger.exception("retrieve_failed: %s", exc)
            raise RetrieverAPIError(
                503,
                "OLLAMA_UNAVAILABLE",
                "Embedding or retrieval failed (Ollama unavailable or misconfigured).",
                str(exc)[:500],
            ) from exc

        chunks = [
            ChunkOut(
                content=d.page_content,
                metadata=_serialize_metadata(d.metadata),
            )
            for d in docs
        ]
        return RetrieveResponse(chunks=chunks)

    @app.post(
        "/v1/index/documents",
        tags=["index"],
        dependencies=[Depends(require_api_key_if_configured)],
    )
    async def index_documents(
        request: Request,
        background_tasks: BackgroundTasks,
        reset: bool = False,
        async_mode: bool | None = None,
        files: list[UploadFile] = File(
            ...,
            description="One or more PDF files to index.",
        ),
        settings: RetrieverAPISettings = Depends(get_settings),
    ) -> IndexAcceptedResponse | JobAcceptedResponse:
        if _shutting_down.is_set():
            raise RetrieverAPIError(
                503,
                "SERVICE_UNAVAILABLE",
                "Service is shutting down.",
            )
        rl = get_rate_limiter()
        if not rl.allow(_client_ip(request) + ":index"):
            raise RetrieverAPIError(
                429,
                "RATE_LIMITED",
                "Too many requests.",
            )

        use_async = (
            bool(async_mode) if async_mode is not None else settings.job_poll_enabled
        )

        if not files:
            raise RetrieverAPIError(
                400,
                "NO_FILES",
                "Provide at least one PDF file.",
            )
        if len(files) > settings.max_upload_files:
            raise RetrieverAPIError(
                400,
                "TOO_MANY_FILES",
                f"At most {settings.max_upload_files} files per request.",
            )

        saved: list[str] = []
        for uf in files:
            if not uf.filename or not uf.filename.lower().endswith(".pdf"):
                raise RetrieverAPIError(
                    415,
                    "UNSUPPORTED_MEDIA_TYPE",
                    "Only PDF files are accepted.",
                )
            raw = await uf.read()
            if len(raw) > settings.max_upload_bytes_per_file:
                raise RetrieverAPIError(
                    413,
                    "FILE_TOO_LARGE",
                    f"File exceeds {settings.max_upload_bytes_per_file} bytes.",
                )
            dest_name = f"{uuid.uuid4().hex}_{uf.filename}"
            dest = settings.upload_dir / dest_name
            dest.write_bytes(raw)
            saved.append(str(dest))

        if use_async:
            job_reg = get_jobs()
            job = job_reg.create()
            background_tasks.add_task(
                _index_job_wrapper,
                job.job_id,
                saved,
                reset,
            )
            base = str(request.base_url).rstrip("/")
            return JobAcceptedResponse(
                job_id=job.job_id,
                status="pending",
                poll_url=f"{base}/v1/jobs/{job.job_id}",
            )

        if not _index_exclusive.acquire(blocking=False):
            raise RetrieverAPIError(
                423,
                "INDEX_BUSY",
                "Another indexing operation is in progress.",
            )
        try:
            _run_index_sync(saved, reset, job_id=None)
        finally:
            _index_exclusive.release()

        return IndexAcceptedResponse()

    @app.get(
        "/v1/jobs/{job_id}",
        response_model=JobStatusResponse,
        tags=["index"],
        dependencies=[Depends(require_api_key_if_configured)],
    )
    async def job_status(job_id: str) -> JobStatusResponse:
        reg = get_jobs()
        job = reg.get(job_id)
        if job is None:
            raise RetrieverAPIError(
                404,
                "JOB_NOT_FOUND",
                "Unknown job id.",
            )
        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            message=job.message,
            error=job.error,
        )

    return app
