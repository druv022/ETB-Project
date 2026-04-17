"""BM25 lexical retrieval over exported sparse corpora."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from etb_project.vectorstore.sparse_export import SPARSE_VERSION


def tokenize_bm25(text: str) -> list[str]:
    """Tokenize for BM25.

    Intentionally simple (whitespace + lowercase) because:
    - It's fast and dependency-light.
    - The sparse corpus is an auxiliary signal fused with dense heads (RRF),
      so perfection here is less critical than determinism and robustness.
    """
    return [t for t in text.lower().split() if t]


class Bm25DualSparseRetriever:
    """Two BM25 indices (text + captions). Caption index may be absent (empty corpus)."""

    def __init__(
        self,
        *,
        text_docs: list[Document],
        text_bm25: BM25Okapi,
        caption_docs: list[Document],
        caption_bm25: BM25Okapi | None,
    ) -> None:
        self._text_docs = text_docs
        self._text_bm25 = text_bm25
        self._caption_docs = caption_docs
        self._caption_bm25 = caption_bm25

    @staticmethod
    def load(root: Path) -> Bm25DualSparseRetriever:
        sparse = root / "sparse"
        ver_path = sparse / "version.txt"
        if not ver_path.is_file():
            raise FileNotFoundError(f"Missing sparse version: {ver_path}")
        version = ver_path.read_text(encoding="utf-8").strip()
        if version != SPARSE_VERSION:
            raise ValueError(
                f"Unsupported sparse corpus version {version!r}; expected {SPARSE_VERSION!r}"
            )

        text_path = sparse / "text_corpus.jsonl"
        cap_path = sparse / "captions_corpus.jsonl"
        if not text_path.is_file() or not cap_path.is_file():
            raise FileNotFoundError(
                "Missing sparse/text_corpus.jsonl or captions_corpus.jsonl"
            )

        text_docs, text_tok = _load_jsonl_corpus(text_path)
        cap_docs, cap_tok = _load_jsonl_corpus(cap_path)

        # Text BM25 is mandatory for hybrid mode. Caption BM25 is optional because
        # some PDFs have no images/captions, and we still want hybrid retrieval.
        if not text_docs:
            raise ValueError("BM25 text corpus is empty")

        text_bm25 = BM25Okapi(text_tok)
        cap_bm25: BM25Okapi | None = None
        # If the caption corpus is empty (or tokenizes to empty strings), we
        # treat it as "no caption BM25 head" rather than creating a useless index.
        if cap_docs and any(tok for tok in cap_tok):
            cap_bm25 = BM25Okapi(cap_tok)

        return Bm25DualSparseRetriever(
            text_docs=text_docs,
            text_bm25=text_bm25,
            caption_docs=cap_docs,
            caption_bm25=cap_bm25,
        )

    def search_text(self, query: str, k_fetch: int) -> list[Document]:
        return _bm25_top_k(self._text_bm25, self._text_docs, query, k_fetch)

    def search_captions(self, query: str, k_fetch: int) -> list[Document]:
        if self._caption_bm25 is None:
            return []
        return _bm25_top_k(self._caption_bm25, self._caption_docs, query, k_fetch)

    @property
    def has_caption_index(self) -> bool:
        return self._caption_bm25 is not None


def _load_jsonl_corpus(path: Path) -> tuple[list[Document], list[list[str]]]:
    docs: list[Document] = []
    tokenized: list[list[str]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row: dict[str, Any] = json.loads(line)
            text = str(row.get("text", ""))
            meta = dict(row.get("metadata") or {})
            docs.append(Document(page_content=text, metadata=meta))
            tokenized.append(tokenize_bm25(text))
    return docs, tokenized


def _bm25_top_k(
    bm25: BM25Okapi,
    docs: list[Document],
    query: str,
    k_fetch: int,
) -> list[Document]:
    q_tok = tokenize_bm25(query)
    if not q_tok:
        # Avoid scoring on an empty token list (would return arbitrary ordering).
        return []
    scores = bm25.get_scores(q_tok)
    indexed = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )
    k = min(k_fetch, len(indexed))
    return [docs[i] for i in indexed[:k]]
