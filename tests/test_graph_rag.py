"""Tests for the LangGraph-based RAG graph."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pandas as pd
import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from etb_project.graph_rag import (
    RAGState,
    _extract_text_from_ai_message,
    build_rag_graph,
)
from etb_project.transaction_queries import TransactionLoadResult

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


def test_data_router_documents_skips_transaction_load(
    mock_llm: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """documents route never calls load_transactions."""
    calls: list[Any] = []

    def _boom(**_kwargs: Any) -> None:
        calls.append(True)
        raise AssertionError("load_transactions should not run")

    monkeypatch.setattr(
        "etb_project.graph_rag.transaction_queries.load_transactions",
        _boom,
    )
    mock_llm.invoke.side_effect = [
        AIMessage(content='{"data_route": "documents", "rationale": "x"}'),
        AIMessage(content="Answer from docs path."),
    ]
    retriever = DummyRetriever([])
    graph = build_rag_graph(
        llm=mock_llm,
        retriever=retriever,
        enable_orion_gate=False,
        enable_data_router=True,
    )
    result = graph.invoke({"query": "What is the policy?"})
    assert not calls
    assert result.get("data_route") == "documents"
    assert result.get("answer") == "Answer from docs path."


def test_data_router_transactions_runs_load_and_generate(
    mock_llm: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """transactions route: gate READY → fetch → generate."""
    mock_llm.invoke.side_effect = [
        AIMessage(content='{"data_route": "transactions"}'),
        AIMessage(
            content="READY TO QUERY:\n"
            '{"start_date": "2024-01-01", "end_date": "2024-01-31", "limit": 5}'
        ),
        AIMessage(content="Here are the figures."),
    ]

    def _load(**_kwargs: Any) -> TransactionLoadResult:
        df = pd.DataFrame([{"Net_Sales_Value": 10.0}])
        return TransactionLoadResult(dataframe=df, detail=None, truncated=False)

    monkeypatch.setattr(
        "etb_project.graph_rag.transaction_queries.load_transactions",
        _load,
    )
    retriever = DummyRetriever([])
    graph = build_rag_graph(
        llm=mock_llm,
        retriever=retriever,
        enable_orion_gate=False,
        enable_data_router=True,
    )
    result = graph.invoke({"query": "Sales in January?"})
    assert result.get("sql_meta_out") is not None
    assert result.get("sql_meta_out", {}).get("row_count") == 1
    assert result.get("answer") == "Here are the figures."
    tool_calls = result.get("tool_calls") or []
    assert any(c.get("tool") == "transaction_load" for c in tool_calls)
    assert not retriever.queries


def test_transaction_gate_clarify_skips_load(
    mock_llm: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    mock_llm.invoke.side_effect = [
        AIMessage(content='{"data_route": "transactions"}'),
        AIMessage(content="Which store region should I use?"),
    ]

    def _boom(**_kwargs: Any) -> TransactionLoadResult:
        raise AssertionError("load should not run")

    monkeypatch.setattr(
        "etb_project.graph_rag.transaction_queries.load_transactions",
        _boom,
    )
    graph = build_rag_graph(
        llm=mock_llm,
        retriever=DummyRetriever([]),
        enable_orion_gate=False,
        enable_data_router=True,
    )
    result = graph.invoke({"query": "Show sales"})
    assert result.get("route") == "clarify"
    assert result.get("clarify_gate") == "transactions"
    assert "region" in (result.get("answer") or "").lower()


def test_data_router_both_runs_txn_then_retrieve(
    mock_llm: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = [Document(page_content="Policy says X.", metadata={})]
    retriever = DummyRetriever(docs)
    mock_llm.invoke.side_effect = [
        AIMessage(content='{"data_route": "both"}'),
        AIMessage(
            content='READY TO QUERY:\n{"start_date": "2024-01-01", "end_date": "2024-01-02"}'
        ),
        AIMessage(content="Combined answer."),
    ]

    monkeypatch.setattr(
        "etb_project.graph_rag.transaction_queries.load_transactions",
        lambda **_kw: TransactionLoadResult(
            dataframe=pd.DataFrame([{"SKU": "A"}]),
            detail=None,
            truncated=False,
        ),
    )
    graph = build_rag_graph(
        llm=mock_llm,
        retriever=retriever,
        enable_orion_gate=False,
        enable_data_router=True,
    )
    result = graph.invoke({"query": "Policy and SKU mix"})
    assert retriever.queries
    assert result.get("sql_meta_out", {}).get("row_count") == 1
    assert result.get("answer") == "Combined answer."
