"""Export FAISS docstores to BM25 JSONL corpora (transactional writes)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

SPARSE_VERSION = "bm25_v1"


def stable_doc_id(doc: Document) -> str:
    """Deterministic id for sparse corpus rows (not used for RRF dedupe)."""
    meta = doc.metadata or {}
    source = str(meta.get("source", ""))
    page = str(meta.get("page", ""))
    start = str(meta.get("start_index", ""))
    prefix = doc.page_content[:64] if doc.page_content else ""
    raw = f"{source}|{page}|{start}|{prefix}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def documents_from_faiss(vectorstore: FAISS) -> list[Document]:
    """Return documents in FAISS index order (stable for rebuild)."""
    n = int(vectorstore.index.ntotal)
    out: list[Document] = []
    for i in range(n):
        doc_id = vectorstore.index_to_docstore_id[i]
        doc = vectorstore.docstore.search(doc_id)
        if isinstance(doc, Document):
            out.append(doc)
    return out


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".sparse_", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    lines = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    if lines == "\n":
        lines = ""
    _atomic_write_text(path, lines)


def export_sparse_corpus_from_documents(
    text_docs: list[Document],
    caption_docs: list[Document],
    vector_store_root: Path,
) -> None:
    """Write ``sparse/*.jsonl`` and ``version.txt`` under ``vector_store_root``."""
    sparse_dir = vector_store_root / "sparse"
    sparse_dir.mkdir(parents=True, exist_ok=True)

    text_rows = [
        {
            "doc_id": stable_doc_id(d),
            "text": d.page_content,
            "metadata": dict(d.metadata or {}),
        }
        for d in text_docs
    ]
    cap_rows = [
        {
            "doc_id": stable_doc_id(d),
            "text": d.page_content,
            "metadata": dict(d.metadata or {}),
        }
        for d in caption_docs
    ]

    tmp_root = sparse_dir.parent / ".sparse_export_tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    t_text = tmp_root / "text_corpus.jsonl"
    t_cap = tmp_root / "captions_corpus.jsonl"
    t_ver = tmp_root / "version.txt"

    _write_jsonl(t_text, text_rows)
    _write_jsonl(t_cap, cap_rows)
    _atomic_write_text(t_ver, SPARSE_VERSION + "\n")

    final_text = sparse_dir / "text_corpus.jsonl"
    final_cap = sparse_dir / "captions_corpus.jsonl"
    final_ver = sparse_dir / "version.txt"
    os.replace(t_text, final_text)
    os.replace(t_cap, final_cap)
    os.replace(t_ver, final_ver)
    try:
        tmp_root.rmdir()
    except OSError:
        pass


def export_sparse_corpus_from_vectorstores(
    text_vectorstore: FAISS,
    caption_vectorstore: FAISS,
    vector_store_root: Path,
) -> None:
    """Export both FAISS docstores to sparse JSONL files."""
    export_sparse_corpus_from_documents(
        documents_from_faiss(text_vectorstore),
        documents_from_faiss(caption_vectorstore),
        vector_store_root,
    )
