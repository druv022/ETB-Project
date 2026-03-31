"""Tests for the LangGraph-based RAG graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from etb_project.graph_rag import (
    RAGState,
    _extract_text_from_ai_message,
    build_rag_graph,
)

if TYPE_CHECKING:
    pass


class DummyRetriever:
    """Simple retriever stub that records queries and returns predefined documents."""

    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        return list(self._docs)


@pytest.fixture
def mock_llm() -> MagicMock:
    """Return a MagicMock LLM that yields a simple AIMessage."""
    llm = MagicMock()
    llm.invoke.return_value = AIMessage(content="Mock answer from LLM")
    return llm


def test_build_rag_graph_produces_answer_with_context(mock_llm: MagicMock) -> None:
    """Graph returns an answer and records retriever/tool calls when context exists."""
    docs = [Document(page_content="Some context from the document.", metadata={})]
    retriever = DummyRetriever(docs)
    graph = build_rag_graph(llm=mock_llm, retriever=retriever, enable_orion_gate=False)

    initial_state: RAGState = {"query": "What is in the document?"}
    result: dict[str, Any] = graph.invoke(initial_state)

    assert result["query"] == "What is in the document?"
    assert isinstance(result.get("answer"), str)
    assert result["answer"]
    assert retriever.queries == ["What is in the document?"]
    mock_llm.invoke.assert_called_once()

    tool_calls = result.get("tool_calls") or []
    assert any(call.get("tool") == "vector_retriever" for call in tool_calls)


def test_build_rag_graph_handles_empty_context(mock_llm: MagicMock) -> None:
    """Graph still produces an answer when no context documents are retrieved."""
    retriever = DummyRetriever(docs=[])
    graph = build_rag_graph(llm=mock_llm, retriever=retriever, enable_orion_gate=False)

    initial_state: RAGState = {"query": "Question with no context"}
    result: dict[str, Any] = graph.invoke(initial_state)

    assert isinstance(result.get("answer"), str)
    assert result["answer"]
    # Ensure retriever was called even though it returned no documents
    assert retriever.queries == ["Question with no context"]


def test_extract_text_from_ai_message_list_content() -> None:
    """_extract_text_from_ai_message flattens list-based AIMessage content."""
    message = AIMessage(
        content=[
            {"type": "text", "text": "First part."},
            {"type": "text", "text": "Second part."},
        ]
    )
    text = _extract_text_from_ai_message(message)
    assert "First part." in text
    assert "Second part." in text


def test_orion_clarify_skips_retriever(mock_llm: MagicMock) -> None:
    """With Orion enabled, a clarifying reply does not call the retriever."""
    retriever = DummyRetriever(docs=[])
    graph = build_rag_graph(llm=mock_llm, retriever=retriever, enable_orion_gate=True)
    mock_llm.invoke.return_value = AIMessage(
        content="Which fiscal year should I use for revenue?"
    )
    result: dict[str, Any] = graph.invoke({"query": "How is revenue?"})
    assert result.get("route") == "clarify"
    assert retriever.queries == []
    assert "fiscal" in (result.get("answer") or "").lower()
    mock_llm.invoke.assert_called_once()


def test_orion_ready_invokes_retriever_with_refined_query(mock_llm: MagicMock) -> None:
    """Orion READY TO RETRIEVE uses refined query for retrieval and second LLM call."""
    docs = [Document(page_content="ctx", metadata={})]
    retriever = DummyRetriever(docs)
    graph = build_rag_graph(llm=mock_llm, retriever=retriever, enable_orion_gate=True)
    mock_llm.invoke.side_effect = [
        AIMessage(content="OK. READY TO RETRIEVE: What was revenue in Q3 2024?"),
        AIMessage(content="Final answer from RAG."),
    ]
    result: dict[str, Any] = graph.invoke({"query": "revenue?"})
    assert result.get("route") == "retrieve"
    assert retriever.queries == ["What was revenue in Q3 2024?"]
    assert result.get("answer") == "Final answer from RAG."
    assert mock_llm.invoke.call_count == 2
