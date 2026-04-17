"""Environment-driven settings for the retriever HTTP API.

The retriever is designed to run in Docker (compose) and in local dev, so most
configuration is environment-variable driven. A YAML config (``ETB_CONFIG``) is
still supported for shared defaults (e.g. vector store location, log level).

Principles:
- **Safe defaults** for local development.
- **Hard caps** for request sizes to avoid accidental OOM / slow requests.
- **Tolerant parsing**: unknown enum-like env values fall back to defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from etb_project.config import DATA_DIR, load_config, resolve_artifact_path


def _env_int(name: str, default: int) -> int:
    """Parse integer env vars with a default.

    We intentionally let ``ValueError`` propagate here: misconfigured numeric
    limits are operational bugs that should fail fast on startup.
    """
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_bool(name: str, default: bool) -> bool:
    """Parse boolean env vars with a default (common truthy strings only)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_strategy(default: str = "dense") -> str:
    raw = os.environ.get("ETB_RETRIEVE_STRATEGY", default).strip().lower()
    if raw in ("dense", "hybrid"):
        return raw
    return default


def _env_reranker(default: str = "cosine") -> str:
    raw = os.environ.get("ETB_RERANKER", default).strip().lower()
    if raw in ("off", "cosine", "cross_encoder", "llm"):
        return raw
    return default


def _env_hyde_mode(default: str = "off") -> str:
    raw = os.environ.get("ETB_HYDE_MODE", default).strip().lower()
    if raw in ("off", "replace", "fuse"):
        return raw
    return default


def _env_hier_expand_default() -> bool:
    raw = os.environ.get("ETB_HIER_EXPAND_DEFAULT")
    if raw is None or raw.strip() == "":
        return True
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
    rate_limit_per_minute: int
    log_level: str
    index_shutdown_timeout_s: float
    job_poll_enabled: bool
    default_retrieve_strategy: str
    retrieval_k_fetch: int | None
    k_fetch_hard_cap: int
    rrf_k: int
    ensemble_cap: int
    default_reranker: str
    default_hyde_mode: str
    hyde_max_tokens: int
    hier_expand_default: bool
    parent_context_chars: int
    max_hierarchy_parents: int
    retrieval_debug: bool
    llm_rerank_batch_size: int
    cross_encoder_model: str


def load_api_settings() -> RetrieverAPISettings:
    """Load settings from env and optional ``ETB_CONFIG`` YAML."""
    cfg = load_config()
    vs = cfg.vector_store_path
    if not vs:
        raise ValueError(
            "vector_store_path must be set in settings.yaml or ETB_CONFIG for the API."
        )
    vector_root = Path(vs)
    # These paths are resolved under the project ``data/`` directory by default
    # so Docker volumes can mount a single shared location for all artifacts.
    out_raw = os.environ.get("ETB_DOCUMENT_OUTPUT_DIR", "data/document_output")
    upload_raw = os.environ.get("ETB_UPLOAD_DIR", "data/uploads")
    doc_out = resolve_artifact_path(out_raw) or (DATA_DIR / "document_output")
    upload_dir = resolve_artifact_path(upload_raw) or (DATA_DIR / "uploads")
    assert doc_out is not None
    assert upload_dir is not None

    default_k = cfg.retriever_k
    max_k = min(100, _env_int("ETB_MAX_RETRIEVE_K", 100))

    # ``k_fetch`` is an internal "over-fetch then fuse/rerank" control. It is
    # allowed to be unset so the pipeline can compute a reasonable default.
    kfetch_env = os.environ.get("ETB_RETRIEVAL_K_FETCH", "").strip()
    retrieval_k_fetch = int(kfetch_env) if kfetch_env else None

    api_key = os.environ.get("RETRIEVER_API_KEY")
    if api_key is not None and api_key.strip() == "":
        api_key = None

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
        rate_limit_per_minute=_env_int("ETB_RATE_LIMIT_PER_MINUTE", 120),
        log_level=cfg.log_level,
        index_shutdown_timeout_s=float(
            os.environ.get("ETB_INDEX_SHUTDOWN_TIMEOUT_S", "120")
        ),
        job_poll_enabled=_env_bool("ETB_INDEX_ASYNC", True),
        default_retrieve_strategy=_env_strategy("dense"),
        retrieval_k_fetch=retrieval_k_fetch,
        k_fetch_hard_cap=_env_int("ETB_K_FETCH_CAP", 100),
        rrf_k=_env_int("ETB_RRF_K", 60),
        ensemble_cap=_env_int("ETB_ENSEMBLE_CAP", 80),
        default_reranker=_env_reranker("cosine"),
        default_hyde_mode=_env_hyde_mode("off"),
        hyde_max_tokens=_env_int("ETB_HYDE_MAX_TOKENS", 384),
        hier_expand_default=_env_hier_expand_default(),
        parent_context_chars=_env_int("ETB_PARENT_CONTEXT_CHARS", 12_000),
        max_hierarchy_parents=_env_int("ETB_MAX_PARENTS", 20),
        retrieval_debug=_env_bool("ETB_RETRIEVAL_DEBUG", False),
        llm_rerank_batch_size=max(1, _env_int("ETB_LLM_RERANK_BATCH", 8)),
        cross_encoder_model=os.environ.get(
            "ETB_CROSS_ENCODER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"
        ).strip()
        or "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
