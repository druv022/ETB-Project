"""BM25 sparse export, RRF pipeline, and lexical ordering."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.retrieval.pipeline import ensemble_rrf, rrf_doc_key
from etb_project.retrieval.process import store_documents
from etb_project.retrieval.sparse_retriever import (
    Bm25DualSparseRetriever,
    tokenize_bm25,
)
from etb_project.vectorstore.sparse_export import (
    export_sparse_corpus_from_vectorstores,
    stable_doc_id,
)


def test_tokenize_bm25_lowercase_splits() -> None:
    assert tokenize_bm25("Hello WORLD") == ["hello", "world"]


def test_stable_doc_id_is_deterministic() -> None:
    d = Document(
        page_content="same content prefix here",
        metadata={"source": "a.pdf", "page": 1, "start_index": 0},
    )
    assert stable_doc_id(d) == stable_doc_id(d)


def test_ensemble_rrf_prefers_doc_in_multiple_lists() -> None:
    d_shared = Document(page_content="both", metadata={"source": "x", "page": 1})
    d_only_a = Document(page_content="a_only", metadata={"source": "x", "page": 2})
    d_only_b = Document(page_content="b_only", metadata={"source": "x", "page": 3})
    heads = [
        ("dense_text_q", [d_shared, d_only_a]),
        ("dense_caption_q", [d_shared, d_only_b]),
    ]
    out = ensemble_rrf(heads, k_rrf=60, cap=10)
    assert out[0] is d_shared


def test_rrf_doc_key_matches_flat_tuple() -> None:
    d = Document(page_content="t", metadata={"source": "s", "page": 2, "path": "p"})
    assert rrf_doc_key(d) == ("flat", "t", "s", 2, "p")


def test_bm25_export_roundtrip_prefers_keyword_hit(tmp_path) -> None:
    pytest.importorskip("rank_bm25")
    emb = MagicMock(spec=Embeddings)
    emb.embed_query.return_value = [0.0] * 4
    emb.embed_documents.side_effect = lambda texts: [
        [0.1 * i] * 4 for i in range(len(texts))
    ]

    text_docs = [
        Document(
            page_content="alpha beta raretoken xyz",
            metadata={"source": "s1.pdf", "page": 0},
        ),
        Document(
            page_content="gamma delta epsilon",
            metadata={"source": "s1.pdf", "page": 1},
        ),
    ]
    text_vs = store_documents(text_docs, emb)
    cap_vs = store_documents([], emb)

    export_sparse_corpus_from_vectorstores(text_vs, cap_vs, tmp_path)

    bundle = Bm25DualSparseRetriever.load(tmp_path)
    assert not bundle.has_caption_index
    hits = bundle.search_text("raretoken", 5)
    assert hits[0].page_content.startswith("alpha beta")
