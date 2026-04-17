"""Single-query adapter that merges results from two retrievers.

This is primarily a UX/quality wrapper: the caller asks one question once, but
we query two different indices/heads (e.g. text chunks and image-caption docs)
and then merge results into a single list for downstream RAG.

Key behavior:
- De-duplicates near-identical documents across heads so the context window isn't
  wasted repeating the same source.
- Preserves head ordering bias (text results first, then caption results) while
  still allowing caption-only hits to appear.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from langchain_core.documents import Document
from langsmith import traceable

from etb_project.tracing.query_stats import query_stats_for_trace
from etb_project.tracing.settings import get_tracing_store


@dataclass
class DualRetriever:
    """Wrap text + caption retrievers behind one ``invoke`` method."""

    text_retriever: Any
    caption_retriever: Any
    k_total: int = 10

    def _doc_key(self, doc: Document) -> tuple[Any, ...]:
        """Return a stable identity key for de-duplication across heads.

        Preference order:
        - ``child_id`` when present (hierarchical retrieval emits stable IDs and
          page_content may be expanded/modified).
        - A best-effort composite key from content + common provenance fields.
        """
        metadata = doc.metadata or {}
        cid = metadata.get("child_id")
        if cid is not None:
            return (str(cid),)
        return (
            doc.page_content,
            metadata.get("source"),
            metadata.get("page"),
            metadata.get("path"),
        )

    def invoke(self, query: str) -> list[Document]:
        """Return merged and de-duplicated retrieval results for one query."""
        if not get_tracing_store().enabled:
            return self._invoke_impl(query)
        docs = self._invoke_impl(query)
        out = _dual_retriever_trace(
            retriever_kind="local_dual_faiss",
            k_total=self.k_total,
            query_stats=query_stats_for_trace(query),
            documents=docs,
        )
        return cast(list[Document], out["documents"])

    def _invoke_impl(self, query: str) -> list[Document]:
        text_docs = self.text_retriever.invoke(query)
        caption_docs = self.caption_retriever.invoke(query)

        merged: list[Document] = []
        seen: set[tuple[Any, ...]] = set()
        for doc in [*text_docs, *caption_docs]:
            key = self._doc_key(doc)
            if key in seen:
                continue
            seen.add(key)
            merged.append(doc)
            if len(merged) >= self.k_total:
                break

        return merged


@traceable(name="dual_retriever_local", run_type="retriever")
def _dual_retriever_trace(
    *,
    retriever_kind: str,
    k_total: int,
    query_stats: dict[str, Any],
    documents: list[Document],
) -> dict[str, Any]:
    return {
        "retriever_kind": retriever_kind,
        "k_total": k_total,
        "chunk_count": len(documents),
        "documents": documents,
    }
