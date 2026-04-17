"""Unit tests for RRF ensemble, cosine rerank, and cross-encoder rerank."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage

from etb_project.retrieval.pipeline import (
    _cosine_rerank,
    _cross_encoder_rerank,
    _llm_rerank,
    ensemble_rrf,
    rrf_doc_key,
)


def test_ensemble_rrf_three_lists_prefers_multi_list_doc() -> None:
    """Doc appearing in three heads ranks above single-head docs with same per-list rank."""
    d_triple = Document(page_content="triple", metadata={"source": "a", "page": 1})
    d_a = Document(page_content="a_only", metadata={"source": "a", "page": 2})
    d_b = Document(page_content="b_only", metadata={"source": "a", "page": 3})
    d_c = Document(page_content="c_only", metadata={"source": "a", "page": 4})
    heads = [
        ("dense_text_q", [d_triple, d_a]),
        ("dense_caption_q", [d_triple, d_b]),
        ("bm25_text", [d_triple, d_c]),
    ]
    out = ensemble_rrf(heads, k_rrf=60, cap=10)
    assert out[0] is d_triple


def test_ensemble_rrf_tie_break_dense_text_before_caption() -> None:
    """Equal RRF score: first appearance in HEAD_ORDER (dense_text_q before dense_caption_q)."""
    d_text = Document(page_content="x1", metadata={"source": "s", "page": 1})
    d_cap = Document(page_content="x2", metadata={"source": "s", "page": 2})
    heads = [
        ("dense_text_q", [d_text]),
        ("dense_caption_q", [d_cap]),
    ]
    k_rrf = 60
    s_text = 1.0 / (k_rrf + 1)
    s_cap = 1.0 / (k_rrf + 1)
    assert abs(s_text - s_cap) < 1e-9
    out = ensemble_rrf(heads, k_rrf=k_rrf, cap=10)
    assert out[0] is d_text
    assert rrf_doc_key(d_text) != rrf_doc_key(d_cap)


def test_cosine_rerank_orders_by_similarity() -> None:
    """Mock embeddings so second doc aligns with query; rerank should list it first."""
    docs = [
        Document(page_content="aaa", metadata={}),
        Document(page_content="bbb", metadata={}),
    ]
    emb = MagicMock(spec=Embeddings)
    emb.embed_query.return_value = [1.0, 0.0]
    emb.embed_documents.return_value = [
        [0.0, 1.0],
        [1.0, 0.0],
    ]
    out = _cosine_rerank("q", docs, emb)
    assert [d.page_content for d in out] == ["bbb", "aaa"]


def test_cross_encoder_rerank_orders_by_scores() -> None:
    docs = [
        Document(page_content="low", metadata={}),
        Document(page_content="high", metadata={}),
    ]
    mock_ce = MagicMock()
    mock_ce.predict.return_value = np.array([0.1, 0.9])

    with patch(
        "etb_project.retrieval.pipeline._get_cross_encoder", return_value=mock_ce
    ):
        out = _cross_encoder_rerank("query", docs, "dummy-model")

    assert [d.page_content for d in out] == ["high", "low"]
    mock_ce.predict.assert_called_once()
    pairs = mock_ce.predict.call_args[0][0]
    assert pairs == [["query", "low"], ["query", "high"]]


def test_llm_rerank_orders_by_parsed_scores() -> None:
    docs = [
        Document(page_content="a", metadata={}),
        Document(page_content="b", metadata={}),
    ]
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.invoke.return_value = AIMessage(content='{"scores": [2, 9]}')

    settings = SimpleNamespace(llm_rerank_batch_size=8)

    with patch(
        "etb_project.retrieval.pipeline.get_retriever_chat_llm", return_value=llm
    ):
        out = _llm_rerank("q", docs, settings)

    assert [d.page_content for d in out] == ["b", "a"]
