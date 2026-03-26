"""Single-query adapter that merges results from two retrievers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_core.documents import Document


@dataclass
class DualRetriever:
    """Wrap text + caption retrievers behind one ``invoke`` method."""

    text_retriever: Any
    caption_retriever: Any
    k_total: int = 10

    def _doc_key(self, doc: Document) -> tuple[str, Any, Any, Any]:
        metadata = doc.metadata or {}
        return (
            doc.page_content,
            metadata.get("source"),
            metadata.get("page"),
            metadata.get("path"),
        )

    def invoke(self, query: str) -> list[Document]:
        """Return merged and de-duplicated retrieval results for one query."""
        text_docs = self.text_retriever.invoke(query)
        caption_docs = self.caption_retriever.invoke(query)

        merged: list[Document] = []
        seen: set[tuple[str, Any, Any, Any]] = set()
        for doc in [*text_docs, *caption_docs]:
            key = self._doc_key(doc)
            if key in seen:
                continue
            seen.add(key)
            merged.append(doc)
            if len(merged) >= self.k_total:
                break

        return merged
