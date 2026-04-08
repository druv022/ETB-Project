"""Ensemble retrieval: dense FAISS heads, optional BM25, RRF, optional rerankers.

This is the core retrieval "policy" module: given a query and available indices,
it decides which retrieval heads to run, how to fuse results, and how to rerank.

Why the implementation uses explicit "heads":
- It keeps retrieval experimentation modular (add/remove heads without rewriting
  the full pipeline).
- It allows parallel execution of independent heads to reduce latency.
- It provides a single place to enforce caps (k_fetch, ensemble_cap) so new heads
  don't accidentally explode retrieval cost.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Literal

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from etb_project.api.schemas import RetrieveRequest
from etb_project.api.settings import RetrieverAPISettings
from etb_project.retrieval.hyde import (
    generate_hypothetical_passage,
    get_retriever_chat_llm,
    resolve_hyde_mode,
)
from etb_project.retrieval.sparse_retriever import Bm25DualSparseRetriever
from etb_project.vectorstore.hierarchy_store import expand_child_hits_to_parents

logger = logging.getLogger(__name__)

RetrieveStrategy = Literal["dense", "hybrid"]
RerankerMode = Literal["off", "cosine", "cross_encoder", "llm"]

# Head order for RRF tie-break (first appearance in this concatenation wins).
# This matters when multiple documents have identical RRF scores: we prefer
# earlier heads to keep output stable and aligned with our default priorities.
HEAD_ORDER = (
    "dense_text_q",
    "dense_caption_q",
    "dense_text_h",
    "dense_caption_h",
    "bm25_text",
    "bm25_caption",
    "hier_child",
)

_MAX_HEAD_WORKERS = 4

_RERANK_LLM_SYSTEM = (
    "You score how relevant each passage is to answering the user query. "
    'Reply with ONLY a JSON object: {"scores": [<integer 0-10>, ...]} with exactly '
    "one score per passage, in the same order as given."
)

_cross_encoder_model_loaded: str | None = None
_cross_encoder_instance: Any = None


def rrf_doc_key(doc: Document) -> tuple:
    """Return a stable identity used for cross-head de-duplication.

    When hierarchical retrieval is enabled, child chunks have stable ``child_id``.
    Otherwise we fall back to a best-effort composite key (content + provenance).
    """
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

    # Track best rank per (doc_key, head_id). A document can appear in multiple
    # heads, potentially at different ranks; we keep the best (lowest) rank per
    # head for RRF scoring.
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

    # RRF alone can produce ties. We use the first position a doc appears in the
    # concatenated head order as a deterministic tie-breaker.
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
    """Lightweight reranker based on embedding cosine similarity.

    This is intentionally "cheap": it avoids extra model calls while usually
    improving ordering after fusion.
    """
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


def _get_cross_encoder(model_name: str) -> Any:
    global _cross_encoder_model_loaded, _cross_encoder_instance
    try:
        from sentence_transformers import CrossEncoder
    except ImportError as exc:
        raise ImportError(
            "cross_encoder reranker requires sentence-transformers "
            "(pip install sentence-transformers)"
        ) from exc
    # Cross-encoder models are heavy to load. Cache a singleton and replace only
    # when the model name changes.
    if _cross_encoder_instance is None or _cross_encoder_model_loaded != model_name:
        _cross_encoder_instance = CrossEncoder(model_name)
        _cross_encoder_model_loaded = model_name
    return _cross_encoder_instance


def _cross_encoder_rerank(
    query: str,
    docs: list[Document],
    model_name: str,
) -> list[Document]:
    if not docs:
        return []
    ce = _get_cross_encoder(model_name)
    pairs = [[query, d.page_content or ""] for d in docs]
    raw = ce.predict(pairs)
    arr = np.asarray(raw, dtype=np.float64).reshape(-1)
    order = np.argsort(-arr)
    return [docs[int(i)] for i in order]


def _extract_text_ai(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content).strip()


def _parse_llm_scores_json(text: str, expected: int) -> list[float] | None:
    text = text.strip()
    # Some providers prepend/explain before the JSON. We try to salvage the
    # trailing JSON object to keep reranking robust.
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        text = m.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    scores = data.get("scores")
    if not isinstance(scores, list) or len(scores) != expected:
        return None
    out: list[float] = []
    for s in scores:
        if isinstance(s, bool) or not isinstance(s, (int, float)):
            return None
        out.append(float(max(0, min(10, int(s)))))
    return out


def _llm_rerank(
    query: str,
    docs: list[Document],
    settings: RetrieverAPISettings,
    *,
    request_id: str | None = None,
) -> list[Document]:
    llm = get_retriever_chat_llm()
    if llm is None:
        raise RuntimeError("LLM reranker: chat LLM unavailable")
    if not docs:
        return []
    batch_size = settings.llm_rerank_batch_size
    all_scores: list[float] = []
    offset = 0
    rid = f" request_id={request_id}" if request_id else ""

    # Score in batches to keep prompt size and token usage bounded.
    while offset < len(docs):
        batch = docs[offset : offset + batch_size]
        lines = [f"[{j}] {d.page_content[:4000]}" for j, d in enumerate(batch)]
        user_content = (
            f"Query:\n{query.strip()}\n\n"
            f"Passages (score each 0-10 for relevance to the query):\n"
            + "\n\n".join(lines)
        )
        messages = [
            SystemMessage(content=_RERANK_LLM_SYSTEM),
            HumanMessage(content=user_content),
        ]
        # As with HyDE generation, not all chat backends support bind(max_tokens).
        try:
            try:
                bound = llm.bind(max_tokens=512)
                response = bound.invoke(messages)
            except (TypeError, ValueError, AttributeError):
                response = llm.invoke(messages)
        except Exception as exc:
            logger.warning("LLM rerank batch failed%s: %s", rid, exc)
            raise

        text = (
            _extract_text_ai(response)
            if isinstance(response, AIMessage)
            else str(response).strip()
        )
        parsed = _parse_llm_scores_json(text, len(batch))
        if parsed is None:
            logger.warning("LLM rerank: could not parse scores%s", rid)
            raise ValueError("invalid LLM rerank JSON")
        all_scores.extend(parsed)
        offset += batch_size

    order = sorted(range(len(docs)), key=lambda i: -all_scores[i])
    return [docs[i] for i in order]


def effective_k_fetch(k: int, settings: RetrieverAPISettings) -> int:
    """Compute how many docs each head should fetch before fusion/rerank.

    Fetching more than ``k`` is important because fusion/reranking needs a pool
    to reorder. We cap aggressively to avoid runaway latency/cost.
    """
    if settings.retrieval_k_fetch is not None:
        base = settings.retrieval_k_fetch
    else:
        base = max(k * 5, 30)
    return min(base, settings.k_fetch_hard_cap, settings.max_retrieve_k)


def _resolve_expand(
    request: RetrieveRequest,
    settings: RetrieverAPISettings,
    hierarchy_active: bool,
) -> bool:
    if request.expand is not None:
        return bool(request.expand)
    if not hierarchy_active:
        return False
    return bool(settings.hier_expand_default)


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


def _execute_heads_parallel(
    tasks: list[tuple[str, Callable[[], list[Document]]]],
) -> list[tuple[str, list[Document]]]:
    """Run independent head callables; preserve ``HEAD_ORDER`` in output."""
    if not tasks:
        return []
    by_id: dict[str, list[Document]] = {}
    # Avoid threadpool overhead for the common single-head path.
    if len(tasks) == 1:
        hid, fn = tasks[0]
        by_id[hid] = _tag_head(fn(), hid)
    else:
        workers = min(_MAX_HEAD_WORKERS, len(tasks))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            future_to_hid = {ex.submit(fn): hid for hid, fn in tasks}
            for fut in as_completed(future_to_hid):
                hid = future_to_hid[fut]
                by_id[hid] = _tag_head(fut.result(), hid)
    return [(hid, by_id[hid]) for hid in HEAD_ORDER if hid in by_id]


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
    hierarchy_sqlite_path: Path | None = None,
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

    # HyDE modes:
    # - off: query-only dense heads
    # - replace: use HyDE passage heads only (unless HyDE fails)
    # - fuse: run both query and HyDE dense heads, then fuse via RRF
    include_query_dense = (hyde_mode != "replace") or (not hyde_usable)
    include_hyde_dense = hyde_usable and hyde_mode in ("replace", "fuse")

    text_r_kw = {"k": k_fetch}
    tasks: list[tuple[str, Callable[[], list[Document]]]] = []

    if include_query_dense:
        text_retriever_q = text_vs.as_retriever(search_kwargs=text_r_kw)
        caption_retriever_q = caption_vs.as_retriever(search_kwargs=text_r_kw)

        def _dense_text_q() -> list[Document]:
            return list(text_retriever_q.invoke(q))

        def _dense_caption_q() -> list[Document]:
            return list(caption_retriever_q.invoke(q))

        tasks.append(("dense_text_q", _dense_text_q))
        tasks.append(("dense_caption_q", _dense_caption_q))

    if include_hyde_dense and H is not None:
        text_retriever_h = text_vs.as_retriever(search_kwargs=text_r_kw)
        caption_retriever_h = caption_vs.as_retriever(search_kwargs=text_r_kw)
        hh = H

        def _dense_text_h() -> list[Document]:
            return list(text_retriever_h.invoke(hh))

        def _dense_caption_h() -> list[Document]:
            return list(caption_retriever_h.invoke(hh))

        tasks.append(("dense_text_h", _dense_text_h))
        tasks.append(("dense_caption_h", _dense_caption_h))

    # Hybrid adds lexical BM25 heads. These are optional because the sparse corpus
    # may not exist for older indices or dense-only builds.
    if strategy == "hybrid" and bm25 is not None:

        def _bm25_text() -> list[Document]:
            return bm25.search_text(q, k_fetch)

        tasks.append(("bm25_text", _bm25_text))
        if bm25.has_caption_index:

            def _bm25_caption() -> list[Document]:
                return bm25.search_captions(q, k_fetch)

            tasks.append(("bm25_caption", _bm25_caption))

    hierarchy_active = hierarchy_sqlite_path is not None
    if hierarchy_active:
        # This head is dense retrieval over the same text index, but its results
        # are used *as child hits* that can later be expanded to full parent-page
        # context. It stays in RRF so it competes with other heads.
        hier_retriever = text_vs.as_retriever(search_kwargs=text_r_kw)

        def _hier_child() -> list[Document]:
            return list(hier_retriever.invoke(q))

        tasks.append(("hier_child", _hier_child))

    heads = _execute_heads_parallel(tasks)

    k_rrf = settings.rrf_k
    cap = settings.ensemble_cap
    # Fusion happens before reranking so the reranker only sees a bounded,
    # de-duplicated candidate set.
    merged = ensemble_rrf(heads, k_rrf=k_rrf, cap=cap)

    if settings.retrieval_debug:
        logger.info(
            "retrieval_debug heads=%s rrf_keys=%s request_id=%s",
            [(h, len(xs)) for h, xs in heads],
            len(merged),
            request_id or "",
        )

    if not merged:
        return []

    mode = _reranker_mode(request, settings)
    try:
        if mode == "cosine":
            merged = _cosine_rerank(q, merged, embeddings)
        elif mode == "cross_encoder":
            merged = _cross_encoder_rerank(q, merged, settings.cross_encoder_model)
        elif mode == "llm":
            merged = _llm_rerank(q, merged, settings, request_id=request_id)
        elif mode == "off":
            pass
    except Exception as exc:
        logger.warning("Rerank failed, using ensemble order: %s", exc)

    top = merged[:k]

    if settings.retrieval_debug and top:
        logger.info(
            "retrieval_debug post_rerank first_heads=%s request_id=%s",
            [(d.metadata or {}).get("ensemble_head") for d in top[:3]],
            request_id or "",
        )

    # Parent expansion is intentionally last: it changes document content and can
    # produce fewer than k results after collapsing children into unique parents.
    expand = _resolve_expand(request, settings, hierarchy_active)
    if expand and hierarchy_sqlite_path is not None and hierarchy_sqlite_path.is_file():
        top = expand_child_hits_to_parents(
            top,
            hierarchy_sqlite_path,
            max_parents=settings.max_hierarchy_parents,
            max_total_chars=settings.parent_context_chars,
        )
    return top
