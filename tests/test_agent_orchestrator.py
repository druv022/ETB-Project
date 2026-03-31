"""Tests for the agentic orchestrator LangGraph (mocked LLM, no network)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from etb_project.orchestrator.agent_graph import build_agent_orchestrator_graph


class DummyRetriever:
    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        return list(self._docs)


def _tool_call(name: str, args: dict[str, Any], tid: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": tid}


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()


def test_agent_finalize_only(mock_llm: MagicMock) -> None:
    """Model calls finalize_answer; generation uses base llm.invoke."""
    llm_tools = MagicMock()
    mock_llm.bind_tools.return_value = llm_tools
    llm_tools.invoke.return_value = AIMessage(
        content="",
        tool_calls=[_tool_call("finalize_answer", {}, "fc1")],
    )
    mock_llm.invoke.return_value = AIMessage(content="The answer.")

    retriever = DummyRetriever([])
    graph = build_agent_orchestrator_graph(
        llm=mock_llm,
        retriever=retriever,
        max_retrieve=4,
        max_steps=10,
        max_context_chars=48_000,
    )
    result = graph.invoke({"query": "What is revenue?", "messages": []})
    assert result.get("route") == "answer"
    assert "answer" in result
    assert "The answer." in (result.get("answer") or "")
    assert retriever.queries == []


def test_agent_retrieve_then_finalize(mock_llm: MagicMock) -> None:
    docs = [Document(page_content="ctx text", metadata={"id": "1"})]
    retriever = DummyRetriever(docs)
    llm_tools = MagicMock()
    mock_llm.bind_tools.return_value = llm_tools
    llm_tools.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[_tool_call("retrieve", {"query": "revenue Q3"}, "r1")],
        ),
        AIMessage(
            content="",
            tool_calls=[_tool_call("finalize_answer", {}, "f1")],
        ),
    ]
    mock_llm.invoke.return_value = AIMessage(content="Grounded reply.")

    graph = build_agent_orchestrator_graph(
        llm=mock_llm,
        retriever=retriever,
        max_retrieve=4,
        max_steps=10,
        max_context_chars=48_000,
    )
    result = graph.invoke({"query": "revenue?", "messages": []})
    assert result.get("route") == "answer"
    assert retriever.queries == ["revenue Q3"]
    assert "Grounded reply." in (result.get("answer") or "")


def test_agent_ask_clarify_short_circuits(mock_llm: MagicMock) -> None:
    llm_tools = MagicMock()
    mock_llm.bind_tools.return_value = llm_tools
    llm_tools.invoke.return_value = AIMessage(
        content="",
        tool_calls=[_tool_call("ask_clarify", {"message": "Which fiscal year?"}, "c1")],
    )
    retriever = DummyRetriever([])
    graph = build_agent_orchestrator_graph(
        llm=mock_llm,
        retriever=retriever,
        max_retrieve=4,
        max_steps=10,
        max_context_chars=48_000,
    )
    result = graph.invoke({"query": "sales?", "messages": []})
    assert result.get("route") == "clarify"
    assert "fiscal year" in (result.get("answer") or "").lower()
    assert retriever.queries == []


def test_agent_no_tools_then_fallback_finalize(mock_llm: MagicMock) -> None:
    """Plain text twice triggers fallback generation."""
    llm_tools = MagicMock()
    mock_llm.bind_tools.return_value = llm_tools
    llm_tools.invoke.side_effect = [
        AIMessage(content="I will help."),
        AIMessage(content="Still no tools."),
    ]
    mock_llm.invoke.return_value = AIMessage(content="Fallback answer.")

    retriever = DummyRetriever([])
    graph = build_agent_orchestrator_graph(
        llm=mock_llm,
        retriever=retriever,
        max_retrieve=4,
        max_steps=10,
        max_context_chars=48_000,
    )
    result = graph.invoke({"query": "hello", "messages": []})
    assert result.get("route") == "answer"
    assert "Fallback answer." in (result.get("answer") or "")


def test_agent_max_steps_force_finalize(mock_llm: MagicMock) -> None:
    """Hit max_steps without finalize routes to force_finalize node."""
    llm_tools = MagicMock()
    mock_llm.bind_tools.return_value = llm_tools
    # Each loop: agent returns only retrieve (no finalize) until step cap
    llm_tools.invoke.return_value = AIMessage(
        content="",
        tool_calls=[_tool_call("retrieve", {"query": "q"}, "x")],
    )
    mock_llm.invoke.return_value = AIMessage(content="Forced.")

    retriever = DummyRetriever([Document(page_content="d", metadata={})])
    graph = build_agent_orchestrator_graph(
        llm=mock_llm,
        retriever=retriever,
        max_retrieve=10,
        max_steps=2,
        max_context_chars=48_000,
    )
    result = graph.invoke({"query": "q", "messages": []})
    assert result.get("route") == "answer"
    assert "Forced." in (result.get("answer") or "")
    assert "[Note: Step limit reached" in (
        result.get("answer") or ""
    ) or "Step limit" in (result.get("answer") or "")
