"""Tests for etb_project.models embedding normalization."""

from unittest.mock import MagicMock

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings

from etb_project.models import (
    FaissCompatibleEmbeddings,
    _normalize_embed_documents_for_faiss,
    get_ollama_embedding_model,
)


def test_normalize_empty_texts() -> None:
    assert _normalize_embed_documents_for_faiss([[0.0, 1.0]], 0) == []


def test_normalize_single_document_flat_list() -> None:
    """Ollama-style mistake: one vector as flat [float, ...] instead of [[...]]."""
    flat = [0.1, 0.2, 0.3, 0.4]
    assert _normalize_embed_documents_for_faiss(flat, 1) == [flat]


def test_normalize_accepts_tuple_of_lists() -> None:
    """API may return a tuple of embedding rows instead of a list."""
    rows = ([0.1, 0.2], [0.3, 0.4])
    assert _normalize_embed_documents_for_faiss(rows, 2) == [[0.1, 0.2], [0.3, 0.4]]


def test_normalize_single_document_already_nested() -> None:
    nested = [[0.1, 0.2, 0.3]]
    assert _normalize_embed_documents_for_faiss(nested, 1) == nested


def test_normalize_batch_of_lists() -> None:
    batch = [[0.0, 1.0], [2.0, 3.0]]
    assert _normalize_embed_documents_for_faiss(batch, 2) == batch


def test_normalize_numpy_2d() -> None:
    arr = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    assert _normalize_embed_documents_for_faiss(arr, 2) == [[1.0, 2.0], [3.0, 4.0]]


def test_normalize_numpy_1d_single() -> None:
    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert _normalize_embed_documents_for_faiss(arr, 1) == [[1.0, 2.0, 3.0]]


def test_normalize_invalid_ndarray_raises() -> None:
    arr = np.array([1.0, 2.0])
    with pytest.raises(ValueError, match="Cannot normalize"):
        _normalize_embed_documents_for_faiss(arr, 2)


def test_normalize_non_list_raises() -> None:
    with pytest.raises(TypeError, match="embed_documents must return"):
        _normalize_embed_documents_for_faiss("bad", 1)


def test_get_ollama_embedding_model_uses_ollama_host_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama:11434")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    emb = get_ollama_embedding_model()
    inner = emb._inner
    assert inner.base_url == "http://ollama:11434"


def test_get_ollama_embedding_model_ollama_host_overrides_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://preferred:11434")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ignored:11434")
    emb = get_ollama_embedding_model()
    assert emb._inner.base_url == "http://preferred:11434"


def test_faiss_compatible_embeddings_wraps_inner() -> None:
    inner = MagicMock(spec=Embeddings)
    inner.embed_documents.return_value = [0.1, 0.2, 0.3]
    inner.embed_query.return_value = [0.0, 0.0]

    wrapped = FaissCompatibleEmbeddings(inner)
    assert wrapped.embed_documents(["one"]) == [[0.1, 0.2, 0.3]]
    inner.embed_documents.assert_called_once_with(["one"])
    assert wrapped.embed_query("q") == [0.0, 0.0]
    inner.embed_query.assert_called_once_with("q")
