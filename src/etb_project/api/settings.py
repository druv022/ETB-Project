"""Environment-driven settings for the retriever HTTP API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from etb_project.config import DATA_DIR, load_config, resolve_artifact_path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class RetrieverAPISettings:
    """Configuration for ``uvicorn`` and route limits."""

    vector_store_path: Path
    document_output_dir: Path
    upload_dir: Path
    default_retriever_k: int
    max_retrieve_k: int
    max_query_chars: int
    max_upload_bytes_per_file: int
    max_upload_files: int
    retrieve_body_max_bytes: int
    api_key: str | None
    admin_api_token: str | None
    rate_limit_per_minute: int
    log_level: str
    index_shutdown_timeout_s: float
    job_poll_enabled: bool


def load_api_settings() -> RetrieverAPISettings:
    """Load settings from env and optional ``ETB_CONFIG`` YAML."""
    cfg = load_config()
    vs = cfg.vector_store_path
    if not vs:
        raise ValueError(
            "vector_store_path must be set in settings.yaml or ETB_CONFIG for the API."
        )
    vector_root = Path(vs)
    out_raw = os.environ.get("ETB_DOCUMENT_OUTPUT_DIR", "data/document_output")
    upload_raw = os.environ.get("ETB_UPLOAD_DIR", "data/uploads")
    doc_out = resolve_artifact_path(out_raw) or (DATA_DIR / "document_output")
    upload_dir = resolve_artifact_path(upload_raw) or (DATA_DIR / "uploads")
    assert doc_out is not None
    assert upload_dir is not None

    default_k = cfg.retriever_k
    max_k = min(100, _env_int("ETB_MAX_RETRIEVE_K", 100))

    api_key = os.environ.get("RETRIEVER_API_KEY")
    if api_key is not None and api_key.strip() == "":
        api_key = None

    admin_raw = os.environ.get("ETB_ADMIN_API_TOKEN")
    admin_tok = (
        str(admin_raw).strip()
        if admin_raw is not None and str(admin_raw).strip() != ""
        else None
    )

    return RetrieverAPISettings(
        vector_store_path=vector_root,
        document_output_dir=Path(doc_out),
        upload_dir=Path(upload_dir),
        default_retriever_k=default_k,
        max_retrieve_k=max_k,
        max_query_chars=_env_int("ETB_MAX_QUERY_CHARS", 10_000),
        max_upload_bytes_per_file=_env_int("ETB_MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
        max_upload_files=_env_int("ETB_MAX_UPLOAD_FILES", 20),
        retrieve_body_max_bytes=_env_int("ETB_MAX_RETRIEVE_BODY_BYTES", 65_536),
        api_key=api_key,
        admin_api_token=admin_tok,
        rate_limit_per_minute=_env_int("ETB_RATE_LIMIT_PER_MINUTE", 120),
        log_level=cfg.log_level,
        index_shutdown_timeout_s=float(
            os.environ.get("ETB_INDEX_SHUTDOWN_TIMEOUT_S", "120")
        ),
        job_poll_enabled=_env_bool("ETB_INDEX_ASYNC", True),
    )
