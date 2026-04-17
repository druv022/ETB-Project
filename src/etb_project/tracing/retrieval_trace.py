"""LangSmith ``@traceable`` for the retriever ensemble pipeline."""

from __future__ import annotations

from typing import Any, Literal

from langsmith import traceable

from etb_project.api.schemas import RetrieveRequest
from etb_project.api.settings import RetrieverAPISettings
from etb_project.tracing.settings import get_tracing_store


@traceable(name="etb_run_retrieval", run_type="chain")
def trace_run_retrieval_summary(
    *,
    resolved_strategy: Literal["dense", "hybrid"],
    request_strategy_raw: str | None,
    default_retrieve_strategy: str,
    hyde_mode: str,
    reranker_mode: str,
    expand_resolved: bool,
    k: int,
    request_id: str | None,
    vector_store_root: str,
    head_counts: list[dict[str, Any]],
    bm25_loaded: bool,
    hierarchy_active: bool,
    final_doc_count: int,
) -> dict[str, Any]:
    """Structured LangSmith run for retrieval policy (inputs + fusion heads)."""
    return {
        "resolved_strategy": resolved_strategy,
        "request_strategy_raw": request_strategy_raw,
        "default_retrieve_strategy": default_retrieve_strategy,
        "hyde_mode": hyde_mode,
        "reranker_mode": reranker_mode,
        "expand_resolved": expand_resolved,
        "k": k,
        "request_id": request_id,
        "vector_store_root": vector_store_root,
        "head_counts": head_counts,
        "bm25_loaded": bm25_loaded,
        "hierarchy_active": hierarchy_active,
        "final_doc_count": final_doc_count,
    }


def maybe_trace_run_retrieval(
    *,
    request: RetrieveRequest,
    k: int,
    strategy: Literal["dense", "hybrid"],
    settings: RetrieverAPISettings,
    head_counts: list[dict[str, Any]],
    bm25_loaded: bool,
    hierarchy_active: bool,
    hyde_mode: str,
    reranker_mode: str,
    expand_resolved: bool,
    final_doc_count: int,
    request_id: str | None,
    vector_store_root: str,
) -> None:
    if not get_tracing_store().enabled:
        return
    raw_strat = request.strategy
    trace_run_retrieval_summary(
        resolved_strategy=strategy,
        request_strategy_raw=raw_strat,
        default_retrieve_strategy=str(
            getattr(settings, "default_retrieve_strategy", "") or ""
        ),
        hyde_mode=hyde_mode,
        reranker_mode=reranker_mode,
        expand_resolved=expand_resolved,
        k=k,
        request_id=request_id,
        vector_store_root=vector_store_root,
        head_counts=head_counts,
        bm25_loaded=bm25_loaded,
        hierarchy_active=hierarchy_active,
        final_doc_count=final_doc_count,
    )
