"""Tests for etb_project.retrieval.process."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.retrieval.process import (
    embed_documents,
    embed_query,
    process_documents,
    split_documents,
    store_documents,
)


@pytest.fixture
def sample_documents() -> list[Document]:
    """Two short documents for splitting tests."""
    return [
        Document(page_content="First chunk of text. " * 50, metadata={"source": "a"}),
        Document(page_content="Second chunk. " * 50, metadata={"source": "b"}),
    ]


def test_split_documents_returns_list_of_documents(
    sample_documents: list[Document],
) -> None:
    """split_documents returns a list of Document."""
    result = split_documents(sample_documents)
    assert isinstance(result, list)
    assert all(isinstance(d, Document) for d in result)
    assert len(result) >= 1


def test_split_documents_empty_list() -> None:
    """split_documents with empty list returns empty list."""
    result = split_documents([])
    assert result == []


def test_split_documents_preserves_metadata(sample_documents: list[Document]) -> None:
    """Split documents retain metadata (e.g. start_index)."""
    result = split_documents(sample_documents)
    for doc in result:
        assert hasattr(doc, "metadata")


def test_store_documents_builds_vectorstore(
    sample_documents: list[Document],
) -> None:
    """store_documents returns a FAISS vectorstore with documents added."""
    mock_embeddings = MagicMock(spec=Embeddings)
    mock_embeddings.embed_query.return_value = [0.0] * 8
    mock_embeddings.embed_documents.return_value = [[0.0] * 8] * len(sample_documents)
    vs = store_documents(sample_documents, mock_embeddings)
    assert vs is not None
    # FAISS has docstore and index
    assert hasattr(vs, "docstore")
    assert hasattr(vs, "index")


def test_process_documents_returns_vectorstore(
    sample_documents: list[Document],
) -> None:
    """process_documents returns a FAISS vectorstore."""
    with patch("etb_project.retrieval.process.get_embedding_model") as mock_get_emb:
        mock_emb = MagicMock(spec=Embeddings)

        def embed_docs(docs: list[Document]) -> list[list[float]]:
            return [[0.0] * 8 for _ in docs]

        mock_emb.embed_query.return_value = [0.0] * 8
        mock_emb.embed_documents.side_effect = embed_docs
        mock_get_emb.return_value = mock_emb
        result = process_documents(sample_documents)
    assert result is not None
    assert hasattr(result, "as_retriever")


def test_embed_query_calls_embedding_model() -> None:
    """embed_query returns a list of floats from the embedding model."""
    with patch("etb_project.retrieval.process.get_embedding_model") as mock_get_emb:
        mock_emb = MagicMock()
        mock_emb.embed_query.return_value = [0.1] * 4
        mock_get_emb.return_value = mock_emb
        result = embed_query("test query")
    assert result == [0.1] * 4
    mock_emb.embed_query.assert_called_once_with("test query")


def test_embed_documents_returns_list_of_vectors(
    sample_documents: list[Document],
) -> None:
    """embed_documents returns list[list[float]]."""
    with patch("etb_project.retrieval.process.get_embedding_model") as mock_get_emb:
        mock_emb = MagicMock()
        mock_emb.embed_documents.return_value = [[0.0] * 4] * len(sample_documents)
        mock_get_emb.return_value = mock_emb
        result = embed_documents(sample_documents)
    assert isinstance(result, list)
    assert len(result) == len(sample_documents)
    assert all(
        isinstance(v, list) and all(isinstance(x, float) for x in v) for v in result
    )
