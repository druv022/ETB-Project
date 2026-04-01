"""Ensemble retrieval: dense FAISS heads, optional BM25, RRF, optional cosine rerank."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Literal

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.api.schemas import RetrieveRequest
from etb_project.api.settings import RetrieverAPISettings
from etb_project.retrieval.hyde import generate_hypothetical_passage, resolve_hyde_mode
from etb_project.retrieval.sparse_retriever import Bm25DualSparseRetriever

logger = logging.getLogger(__name__)

RetrieveStrategy = Literal["dense", "hybrid"]
RerankerMode = Literal["off", "cosine", "cross_encoder", "llm"]

# Head order for RRF tie-break (first appearance in this concatenation wins).
HEAD_ORDER = (
    "dense_text_q",
    "dense_caption_q",
    "dense_text_h",
    "dense_caption_h",
    "bm25_text",
    "bm25_caption",
)


def rrf_doc_key(doc: Document) -> tuple:
    meta = doc.metadata or {}
    cid = meta.get("child_id")
    if cid is not None:
        return ("child", str(cid))
    return (
        "flat",
        doc.page_content,
        meta.get("source"),
        meta.get("page"),
        meta.get("path"),
    )


def ensemble_rrf(
    heads: list[tuple[str, list[Document]]],
    k_rrf: int,
    cap: int,
) -> list[Document]:
    """Reciprocal rank fusion; empty input heads are skipped."""
    active = [(hid, lst) for hid, lst in heads if lst]
    if not active:
        return []

    best_rank: dict[tuple, dict[str, int]] = defaultdict(dict)
    for hid, lst in active:
        for rank, doc in enumerate(lst, start=1):
            key = rrf_doc_key(doc)
            prev = best_rank[key].get(hid, 10**9)
            if rank < prev:
                best_rank[key][hid] = rank

    scores: dict[tuple, float] = {}
    for key, per_head in best_rank.items():
        scores[key] = sum(1.0 / (k_rrf + r) for r in per_head.values())

    first_pos: dict[tuple, int] = {}
    pos = 0
    for hid in HEAD_ORDER:
        lst = next((L for h, L in active if h == hid), [])
        if not lst:
            continue
        for doc in lst:
            key = rrf_doc_key(doc)
            if key not in first_pos:
                first_pos[key] = pos
            pos += 1

    sorted_keys = sorted(
        scores.keys(),
        key=lambda k: (-scores[k], first_pos.get(k, 10**9)),
    )

    key_doc: dict[tuple, Document] = {}
    for _, lst in active:
        for doc in lst:
            key = rrf_doc_key(doc)
            if key not in key_doc:
                key_doc[key] = doc

    out: list[Document] = []
    for key in sorted_keys[:cap]:
        out.append(key_doc[key])
    return out


def _cosine_rerank(
    query: str,
    docs: list[Document],
    embeddings: Embeddings,
) -> list[Document]:
    if not docs:
        return []
    qv = np.asarray(embeddings.embed_query(query), dtype=np.float64)
    qn = float(np.linalg.norm(qv))
    if qn > 0:
        qv = qv / qn
    texts = [d.page_content for d in docs]
    mat = embeddings.embed_documents(texts)
    scored: list[tuple[float, int]] = []
    for i, row in enumerate(mat):
        v = np.asarray(row, dtype=np.float64)
        vn = float(np.linalg.norm(v))
        if vn > 0:
            v = v / vn
        scored.append((float(np.dot(qv, v)), i))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [docs[i] for _, i in scored]


def effective_k_fetch(k: int, settings: RetrieverAPISettings) -> int:
    if settings.retrieval_k_fetch is not None:
        base = settings.retrieval_k_fetch
    else:
        base = max(k * 5, 30)
    return min(base, settings.k_fetch_hard_cap, settings.max_retrieve_k)


def _reranker_mode(
    request: RetrieveRequest,
    settings: RetrieverAPISettings,
) -> RerankerMode:
    raw = (
        request.reranker if request.reranker is not None else settings.default_reranker
    )
    if raw in ("off", "cosine", "cross_encoder", "llm"):
        return raw  # type: ignore[return-value]
    return "off"


def _tag_head(docs: list[Document], head_id: str) -> list[Document]:
    """Attach ``ensemble_head`` for tracing (stripped before HTTP response)."""
    out: list[Document] = []
    for d in docs:
        meta = dict(d.metadata or {})
        meta["ensemble_head"] = head_id
        out.append(Document(page_content=d.page_content, metadata=meta))
    return out


def run_retrieval(
    *,
    request: RetrieveRequest,
    k: int,
    strategy: RetrieveStrategy,
    text_vs: FAISS,
    caption_vs: FAISS,
    bm25: Bm25DualSparseRetriever | None,
    embeddings: Embeddings,
    settings: RetrieverAPISettings,
    request_id: str | None = None,
) -> list[Document]:
    """Run dense (+ optional BM25) heads, RRF, rerank, return top ``k`` documents."""
    k_fetch = effective_k_fetch(k, settings)
    q = request.query

    hyde_mode = resolve_hyde_mode(request, settings)
    H: str | None = None
    hyde_usable = False
    if hyde_mode in ("replace", "fuse"):
        H = generate_hypothetical_passage(q, settings, request_id=request_id)
        hyde_usable = bool(H and H.strip())
        if not hyde_usable:
            logger.warning(
                "HyDE: skipping dense HyDE heads (no passage); using query dense only%s",
                f" request_id={request_id}" if request_id else "",
            )

    include_query_dense = (hyde_mode != "replace") or (not hyde_usable)
    include_hyde_dense = hyde_usable and hyde_mode in ("replace", "fuse")

    heads: list[tuple[str, list[Document]]] = []

    text_r_kw = {"k": k_fetch}
    if include_query_dense:
        text_retriever_q = text_vs.as_retriever(search_kwargs=text_r_kw)
        caption_retriever_q = caption_vs.as_retriever(search_kwargs=text_r_kw)
        heads.append(
            (
                "dense_text_q",
                _tag_head(list(text_retriever_q.invoke(q)), "dense_text_q"),
            )
        )
        heads.append(
            (
                "dense_caption_q",
                _tag_head(list(caption_retriever_q.invoke(q)), "dense_caption_q"),
            )
        )

    if include_hyde_dense and H is not None:
        text_retriever_h = text_vs.as_retriever(search_kwargs=text_r_kw)
        caption_retriever_h = caption_vs.as_retriever(search_kwargs=text_r_kw)
        heads.append(
            (
                "dense_text_h",
                _tag_head(list(text_retriever_h.invoke(H)), "dense_text_h"),
            )
        )
        heads.append(
            (
                "dense_caption_h",
                _tag_head(list(caption_retriever_h.invoke(H)), "dense_caption_h"),
            )
        )

    if strategy == "hybrid" and bm25 is not None:
        heads.append(("bm25_text", bm25.search_text(q, k_fetch)))
        if bm25.has_caption_index:
            heads.append(("bm25_caption", bm25.search_captions(q, k_fetch)))

    k_rrf = settings.rrf_k
    cap = settings.ensemble_cap
    merged = ensemble_rrf(heads, k_rrf=k_rrf, cap=cap)

    if not merged:
        return []

    mode = _reranker_mode(request, settings)
    try:
        if mode == "cosine":
            merged = _cosine_rerank(q, merged, embeddings)
        elif mode == "off":
            pass
        else:
            logger.warning(
                "Reranker mode %s not implemented; using ensemble order", mode
            )
    except Exception as exc:
        logger.warning("Rerank failed, using ensemble order: %s", exc)

    return merged[:k]
