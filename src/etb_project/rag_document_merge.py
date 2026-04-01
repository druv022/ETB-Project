"""Merge and dedupe RAG document chunks (shared by orchestrator and grounded subagent).

Uses **content** (SHA-256 of stripped text), not ``source``/``chunk_id``, so multiple
chunks from the same file are not collapsed incorrectly.
"""

from __future__ import annotations

import hashlib

from langchain_core.documents import Document

# Minimum suffix/prefix match length to merge consecutive chunks (sliding-window overlap).
_MIN_BOUNDARY_OVERLAP_CHARS = 15


def content_fingerprint(text: str) -> str:
    """SHA-256 hex of stripped UTF-8 text — stable across processes (unlike ``hash()``)."""
    t = (text or "").strip()
    return hashlib.sha256(t.encode("utf-8", errors="replace")).hexdigest()


def _filter_subsumed_by_content(docs: list[Document]) -> list[Document]:
    """Drop shorter chunks whose stripped text is strictly contained in another chunk."""
    n = len(docs)
    if n <= 1:
        return docs
    texts = [(d.page_content or "").strip() for d in docs]
    removed = [False] * n
    for i in range(n):
        if not texts[i]:
            continue
        for j in range(n):
            if i == j or removed[i]:
                break
            if not texts[j]:
                continue
            li, lj = len(texts[i]), len(texts[j])
            if li < lj and texts[i] in texts[j]:
                removed[i] = True
                break
    return [docs[i] for i in range(n) if not removed[i]]


def merge_boundary_if_overlap(left: str, right: str, *, min_overlap: int) -> str | None:
    """If ``left`` ends with a prefix of ``right``, return ``left + right[k:]``."""
    if not left or not right:
        return None
    max_k = min(len(left), len(right))
    for k in range(max_k, min_overlap - 1, -1):
        if left[-k:] == right[:k]:
            return left + right[k:]
    return None


def merge_consecutive_overlaps(
    docs: list[Document], *, min_overlap: int = _MIN_BOUNDARY_OVERLAP_CHARS
) -> list[Document]:
    """Merge consecutive chunks that share a long suffix/prefix (RAG window overlap)."""
    if not docs:
        return []
    out: list[Document] = [docs[0]]
    for d in docs[1:]:
        left_text = out[-1].page_content or ""
        right_text = d.page_content or ""
        merged_text = merge_boundary_if_overlap(
            left_text, right_text, min_overlap=min_overlap
        )
        if merged_text is not None:
            out[-1] = Document(
                page_content=merged_text,
                metadata=dict(out[-1].metadata or {}),
            )
        else:
            out.append(d)
    return out


def merge_documents(
    existing: list[Document], new_docs: list[Document]
) -> list[Document]:
    """Merge chunks from repeated retrieve calls.

    1. Exact duplicate (same stripped text, by SHA-256) — keep first only.
    2. Shorter text fully contained in a longer chunk — drop the shorter.
    3. Consecutive chunks with boundary overlap (>= threshold) — merge text.
    """
    combined = list(existing) + list(new_docs)
    if not combined:
        return []

    seen_fp: set[str] = set()
    exact_deduped: list[Document] = []
    for d in combined:
        t = (d.page_content or "").strip()
        fp = content_fingerprint(t)
        if fp in seen_fp:
            continue
        seen_fp.add(fp)
        exact_deduped.append(d)

    subsumed_filtered = _filter_subsumed_by_content(exact_deduped)
    return merge_consecutive_overlaps(subsumed_filtered)


__all__ = [
    "content_fingerprint",
    "merge_boundary_if_overlap",
    "merge_consecutive_overlaps",
    "merge_documents",
]
