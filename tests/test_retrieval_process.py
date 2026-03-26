"""Tests for etb_project.retrieval.process."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.retrieval.process import (
    build_two_vectorstores,
    embed_documents,
    embed_query,
    process_documents,
    process_pdf_to_vectorstores,
    process_prechunked_documents,
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


def test_store_documents_handles_flat_single_embedding(
    sample_documents: list[Document],
) -> None:
    """Single-doc flat vector from embed_documents is stacked for FAISS."""
    one_doc = [sample_documents[0]]
    mock_embeddings = MagicMock(spec=Embeddings)
    mock_embeddings.embed_query.return_value = [0.0] * 8
    mock_embeddings.embed_documents.return_value = [0.0] * 8
    vs = store_documents(one_doc, mock_embeddings)
    assert vs.index.ntotal == 1


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


def test_process_prechunked_documents_uses_store_documents(
    sample_documents: list[Document],
) -> None:
    """process_prechunked_documents delegates to store_documents with default embeddings."""
    with patch("etb_project.retrieval.process.get_embedding_model") as mock_get_emb:
        mock_emb = MagicMock(spec=Embeddings)
        mock_emb.embed_query.return_value = [0.0] * 8
        mock_get_emb.return_value = mock_emb

        with patch("etb_project.retrieval.process.store_documents") as mock_store:
            mock_vectorstore = MagicMock()
            mock_store.return_value = mock_vectorstore

            result = process_prechunked_documents(sample_documents)

    mock_get_emb.assert_called_once()
    mock_store.assert_called_once_with(sample_documents, mock_emb)
    assert result is mock_vectorstore


def test_build_two_vectorstores_builds_both_stores_when_captions_present() -> None:
    """build_two_vectorstores calls process_prechunked_documents for both doc sets."""
    text_docs = [Document(page_content="text", metadata={})]
    caption_docs = [Document(page_content="Image caption: x", metadata={})]

    fake_text_vs = MagicMock()
    fake_caption_vs = MagicMock()

    with patch(
        "etb_project.retrieval.process.process_prechunked_documents",
        side_effect=[fake_text_vs, fake_caption_vs],
    ) as mock_process_prechunked:
        text_vs, caption_vs = build_two_vectorstores(text_docs, caption_docs)

    assert text_vs is fake_text_vs
    assert caption_vs is fake_caption_vs
    assert mock_process_prechunked.call_count == 2
    mock_process_prechunked.assert_any_call(text_docs)
    mock_process_prechunked.assert_any_call(caption_docs)


def test_build_two_vectorstores_uses_empty_store_when_captions_empty() -> None:
    """build_two_vectorstores returns an empty captions store when no caption docs exist."""
    text_docs = [Document(page_content="text", metadata={})]
    caption_docs: list[Document] = []

    fake_text_vs = MagicMock()
    fake_caption_vs = MagicMock()

    with (
        patch(
            "etb_project.retrieval.process.process_prechunked_documents",
            side_effect=[fake_text_vs, fake_caption_vs],
        ) as mock_process_prechunked,
    ):
        text_vs, caption_vs = build_two_vectorstores(text_docs, caption_docs)

    assert text_vs is fake_text_vs
    assert caption_vs is fake_caption_vs
    assert mock_process_prechunked.call_count == 2
    mock_process_prechunked.assert_any_call(text_docs)
    mock_process_prechunked.assert_any_call(caption_docs)


def test_process_pdf_to_vectorstores_delegates_to_dual_builder() -> None:
    """process_pdf_to_vectorstores delegates extraction + building to helper functions."""
    fake_text_docs = [Document(page_content="text", metadata={})]
    fake_caption_docs = [Document(page_content="Image caption: x", metadata={})]
    fake_text_vs = MagicMock()
    fake_caption_vs = MagicMock()

    with (
        patch(
            "etb_project.retrieval.process.process_pdf_to_text_and_caption_docs",
            return_value=(fake_text_docs, fake_caption_docs),
        ) as mock_extract,
        patch(
            "etb_project.retrieval.process.build_two_vectorstores",
            return_value=(fake_text_vs, fake_caption_vs),
        ) as mock_build,
    ):
        result_text_vs, result_caption_vs = process_pdf_to_vectorstores(
            pdf_path="input.pdf",
            output_dir="out",
            chunking_config=None,
            image_captioner=None,
        )

    assert result_text_vs is fake_text_vs
    assert result_caption_vs is fake_caption_vs
    mock_extract.assert_called_once()
    mock_build.assert_called_once_with(fake_text_docs, fake_caption_docs)
