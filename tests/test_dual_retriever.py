"""Tests for the dual retriever adapter."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from etb_project.retrieval.dual_retriever import DualRetriever


@dataclass
class _StubRetriever:
    docs: list[Document]

    def __post_init__(self) -> None:
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        return list(self.docs)


def test_invoke_combines_both_retriever_results() -> None:
    text_doc = Document(page_content="text result", metadata={"source": "text"})
    caption_doc = Document(
        page_content="caption result", metadata={"source": "caption"}
    )
    text = _StubRetriever([text_doc])
    caption = _StubRetriever([caption_doc])
    retriever = DualRetriever(
        text_retriever=text, caption_retriever=caption, k_total=10
    )

    result = retriever.invoke("combined query")

    assert text.queries == ["combined query"]
    assert caption.queries == ["combined query"]
    assert result == [text_doc, caption_doc]


def test_invoke_deduplicates_same_document_from_both_retrievers() -> None:
    duplicate_text = Document(
        page_content="same content",
        metadata={"source": "file.pdf", "page": 2},
    )
    duplicate_caption = Document(
        page_content="same content",
        metadata={"source": "file.pdf", "page": 2},
    )
    text = _StubRetriever([duplicate_text])
    caption = _StubRetriever([duplicate_caption])
    retriever = DualRetriever(
        text_retriever=text, caption_retriever=caption, k_total=10
    )

    result = retriever.invoke("dedupe")

    assert result == [duplicate_text]


def test_invoke_preserves_deterministic_order_text_then_captions() -> None:
    text_docs = [
        Document(page_content="text-1", metadata={"source": "t"}),
        Document(page_content="text-2", metadata={"source": "t"}),
    ]
    caption_docs = [
        Document(page_content="caption-1", metadata={"source": "c"}),
        Document(page_content="caption-2", metadata={"source": "c"}),
    ]
    retriever = DualRetriever(
        text_retriever=_StubRetriever(text_docs),
        caption_retriever=_StubRetriever(caption_docs),
        k_total=10,
    )

    result = retriever.invoke("ordered")

    assert [doc.page_content for doc in result] == [
        "text-1",
        "text-2",
        "caption-1",
        "caption-2",
    ]


def test_invoke_handles_empty_retriever_results() -> None:
    retriever = DualRetriever(
        text_retriever=_StubRetriever([]),
        caption_retriever=_StubRetriever([]),
        k_total=10,
    )

    result = retriever.invoke("nothing")

    assert result == []


def test_invoke_respects_k_total_limit() -> None:
    text_docs = [
        Document(page_content="text-1", metadata={"source": "t"}),
        Document(page_content="text-2", metadata={"source": "t"}),
    ]
    caption_docs = [
        Document(page_content="caption-1", metadata={"source": "c"}),
        Document(page_content="caption-2", metadata={"source": "c"}),
    ]
    retriever = DualRetriever(
        text_retriever=_StubRetriever(text_docs),
        caption_retriever=_StubRetriever(caption_docs),
        k_total=3,
    )

    result = retriever.invoke("cap")

    assert len(result) == 3
    assert [doc.page_content for doc in result] == ["text-1", "text-2", "caption-1"]
