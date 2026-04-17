"""HyDE dense heads: similarity search counts and mode resolution."""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage

from etb_project.api.schemas import RetrieveRequest
from etb_project.retrieval.hyde import (
    generate_hypothetical_passage,
    reset_hyde_llm_cache_for_tests,
    resolve_hyde_mode,
)
from etb_project.retrieval.pipeline import run_retrieval


def _fake_settings(**overrides: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "retrieval_k_fetch": 5,
        "k_fetch_hard_cap": 100,
        "max_retrieve_k": 100,
        "rrf_k": 60,
        "ensemble_cap": 80,
        "default_reranker": "off",
        "default_hyde_mode": "off",
        "hyde_max_tokens": 256,
        "hier_expand_default": True,
        "parent_context_chars": 12_000,
        "max_hierarchy_parents": 20,
        "retrieval_debug": False,
        "llm_rerank_batch_size": 8,
        "cross_encoder_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _vector_store_recording(calls: list[str]) -> MagicMock:
    """FAISS-like mock: as_retriever().invoke(arg) appends arg and returns one doc."""

    def as_retriever(search_kwargs: object | None = None) -> MagicMock:
        r = MagicMock()

        def invoke(q: str) -> list[Document]:
            calls.append(q)
            return [
                Document(page_content="hit", metadata={"source": "s.pdf", "page": 1})
            ]

        r.invoke.side_effect = invoke
        return r

    vs = MagicMock()
    vs.as_retriever.side_effect = as_retriever
    return vs


@pytest.fixture(autouse=True)
def _reset_hyde_llm() -> None:
    reset_hyde_llm_cache_for_tests()
    yield
    reset_hyde_llm_cache_for_tests()


def test_resolve_hyde_mode_request_overrides_env_default() -> None:
    req = RetrieveRequest(query="q", hyde_mode="fuse")
    settings = _fake_settings(default_hyde_mode="replace")
    assert resolve_hyde_mode(req, settings) == "fuse"


def test_resolve_hyde_mode_falls_back_to_settings() -> None:
    req = RetrieveRequest(query="q")
    settings = _fake_settings(default_hyde_mode="replace")
    assert resolve_hyde_mode(req, settings) == "replace"


def test_run_retrieval_off_two_dense_invokes_query_only() -> None:
    calls: list[str] = []
    text_vs = _vector_store_recording(calls)
    cap_vs = _vector_store_recording(calls)
    emb = MagicMock(spec=Embeddings)

    with patch(
        "etb_project.retrieval.pipeline.generate_hypothetical_passage",
        side_effect=AssertionError("HyDE LLM should not run when mode is off"),
    ):
        run_retrieval(
            request=RetrieveRequest(query="user query", hyde_mode="off"),
            k=2,
            strategy="dense",
            text_vs=text_vs,
            caption_vs=cap_vs,
            bm25=None,
            embeddings=emb,
            settings=_fake_settings(),
        )

    assert calls == ["user query", "user query"]


def test_run_retrieval_fuse_four_invokes_with_fixed_hyde() -> None:
    calls: list[str] = []
    text_vs = _vector_store_recording(calls)
    cap_vs = _vector_store_recording(calls)
    emb = MagicMock(spec=Embeddings)

    with patch(
        "etb_project.retrieval.pipeline.generate_hypothetical_passage",
        return_value="HYPOTHETICAL PASSAGE",
    ):
        run_retrieval(
            request=RetrieveRequest(query="user query", hyde_mode="fuse"),
            k=2,
            strategy="dense",
            text_vs=text_vs,
            caption_vs=cap_vs,
            bm25=None,
            embeddings=emb,
            settings=_fake_settings(),
        )

    assert Counter(calls) == Counter(
        [
            "user query",
            "user query",
            "HYPOTHETICAL PASSAGE",
            "HYPOTHETICAL PASSAGE",
        ]
    )


def test_run_retrieval_replace_two_invokes_hyde_only() -> None:
    calls: list[str] = []
    text_vs = _vector_store_recording(calls)
    cap_vs = _vector_store_recording(calls)
    emb = MagicMock(spec=Embeddings)

    with patch(
        "etb_project.retrieval.pipeline.generate_hypothetical_passage",
        return_value="H ONLY",
    ):
        run_retrieval(
            request=RetrieveRequest(query="user query", hyde_mode="replace"),
            k=2,
            strategy="dense",
            text_vs=text_vs,
            caption_vs=cap_vs,
            bm25=None,
            embeddings=emb,
            settings=_fake_settings(),
        )

    assert calls == ["H ONLY", "H ONLY"]


def test_run_retrieval_replace_hyde_fails_falls_back_to_query_dense() -> None:
    calls: list[str] = []
    text_vs = _vector_store_recording(calls)
    cap_vs = _vector_store_recording(calls)
    emb = MagicMock(spec=Embeddings)

    with patch(
        "etb_project.retrieval.pipeline.generate_hypothetical_passage",
        return_value=None,
    ):
        run_retrieval(
            request=RetrieveRequest(query="fallback q", hyde_mode="replace"),
            k=2,
            strategy="dense",
            text_vs=text_vs,
            caption_vs=cap_vs,
            bm25=None,
            embeddings=emb,
            settings=_fake_settings(),
        )

    assert calls == ["fallback q", "fallback q"]


def test_serialize_metadata_strips_ensemble_head() -> None:
    from etb_project.api.state import _serialize_metadata

    out = _serialize_metadata({"source": "a.pdf", "ensemble_head": "dense_text_q"})
    assert out == {"source": "a.pdf"}


def test_generate_hypothetical_passage_uses_injected_llm() -> None:
    llm = MagicMock()
    llm.bind.return_value = llm
    llm.invoke.return_value = AIMessage(content="  synthetic corpus paragraph  ")
    settings = _fake_settings(hyde_max_tokens=128)
    out = generate_hypothetical_passage("q", settings, llm=llm)
    assert out == "synthetic corpus paragraph"
    llm.bind.assert_called_once_with(max_tokens=128)
