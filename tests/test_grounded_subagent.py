"""Tests for grounded writer subagent (templates, merge, graph; mocked LLM)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from etb_project.grounded_subagent.graph import build_writer_graph
from etb_project.grounded_subagent.session_merge import merge_writer_messages_for_parent
from etb_project.grounded_subagent.templates import build_writer_system_prompt
from etb_project.orchestrator.llm_messages import build_grounded_answer_human_message


def _tool_call(name: str, args: dict[str, Any], tid: str) -> dict[str, Any]:
    return {"name": name, "args": args, "id": tid}


class DummyRetriever:
    def __init__(self, docs: list[Document]) -> None:
        self._docs = docs
        self.queries: list[str] = []

    def invoke(self, query: str) -> list[Document]:
        self.queries.append(query)
        return list(self._docs)


def test_build_writer_system_prompt_includes_limits() -> None:
    s = build_writer_system_prompt(max_steps=7, max_retrieve=3)
    assert "7" in s
    assert "3" in s
    assert "submit_final_answer" in s.lower() or "submit" in s.lower()


def test_merge_writer_messages_answer_only_vs_full() -> None:
    writer_msgs: list[Any] = [
        HumanMessage(content="ctx"),
        ToolMessage(content="ok", tool_call_id="t1"),
        AIMessage(content="thinking"),
    ]
    ao = merge_writer_messages_for_parent(
        policy="answer_only",
        tool_call_id="fc1",
        final_answer="Hello.",
        writer_messages=writer_msgs,
    )
    assert len(ao) == 2
    assert isinstance(ao[0], ToolMessage)
    assert ao[0].tool_call_id == "fc1"
    assert isinstance(ao[1], AIMessage)
    assert ao[1].content == "Hello."

    full = merge_writer_messages_for_parent(
        policy="full",
        tool_call_id="fc1",
        final_answer="Hello.",
        writer_messages=writer_msgs,
    )
    assert len(full) == 1 + len(writer_msgs)


def test_merge_writer_messages_no_tool_call_id() -> None:
    out = merge_writer_messages_for_parent(
        policy="answer_only",
        tool_call_id=None,
        final_answer="X",
        writer_messages=[],
    )
    assert len(out) == 1
    assert out[0].content == "X"


def test_writer_graph_submit_final_answer(mock_llm: MagicMock) -> None:
    writer_tools = MagicMock()
    mock_llm.bind_tools.return_value = writer_tools
    writer_tools.invoke.return_value = AIMessage(
        content="",
        tool_calls=[
            _tool_call("submit_final_answer", {"answer": "Final from writer."}, "s1")
        ],
    )
    retriever = DummyRetriever([])
    human = build_grounded_answer_human_message(
        question="Q?",
        documents=[],
        context_truncated=False,
    )
    graph = build_writer_graph(
        mock_llm,
        retriever,
        max_steps=5,
        max_retrieve=2,
        max_context_chars=1000,
        max_messages=40,
    )
    result = graph.invoke(
        {
            "messages": [human],
            "parent_messages": [],
            "query": "Q?",
            "working_docs": [],
            "writer_steps": 0,
            "writer_retrieve_used": 0,
            "writer_tool_calls": [],
            "no_tool_retry_used": False,
            "answer_prefix": "",
            "max_context_chars": 1000,
        }
    )
    assert result.get("writer_route") == "done"
    assert "Final from writer." in (result.get("final_answer") or "")


def test_writer_graph_retrieve_budget(mock_llm: MagicMock) -> None:
    writer_tools = MagicMock()
    mock_llm.bind_tools.return_value = writer_tools
    docs = [Document(page_content="extra", metadata={})]
    retriever = DummyRetriever(docs)
    writer_tools.invoke.side_effect = [
        AIMessage(
            content="",
            tool_calls=[_tool_call("retrieve_more", {"query": "a"}, "r1")],
        ),
        AIMessage(
            content="",
            tool_calls=[_tool_call("retrieve_more", {"query": "b"}, "r2")],
        ),
        AIMessage(
            content="",
            tool_calls=[_tool_call("submit_final_answer", {"answer": "Done."}, "s1")],
        ),
    ]
    human = build_grounded_answer_human_message(
        question="Q",
        documents=[],
        context_truncated=False,
    )
    graph = build_writer_graph(
        mock_llm,
        retriever,
        max_steps=8,
        max_retrieve=1,
        max_context_chars=2000,
        max_messages=40,
    )
    result = graph.invoke(
        {
            "messages": [human],
            "parent_messages": [],
            "query": "Q",
            "working_docs": [],
            "writer_steps": 0,
            "writer_retrieve_used": 0,
            "writer_tool_calls": [],
            "no_tool_retry_used": False,
            "answer_prefix": "",
            "max_context_chars": 2000,
        }
    )
    assert retriever.queries == ["a"]
    assert result.get("writer_route") == "done"
    assert (result.get("final_answer") or "").strip() == "Done."


@pytest.fixture
def mock_llm() -> MagicMock:
    return MagicMock()
