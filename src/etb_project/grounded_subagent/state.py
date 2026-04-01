"""LangGraph state for the grounded writer subgraph."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class WriterState(TypedDict, total=False):
    """Internal writer loop state (not the parent orchestrator state)."""

    messages: Annotated[list[AnyMessage], add_messages]
    parent_messages: list[AnyMessage]
    query: str
    working_docs: list[Document]
    context_truncated_initial: bool
    writer_steps: int
    writer_retrieve_used: int
    writer_route: str | None
    final_answer: str | None
    context_docs: list[Document]
    context_truncated: bool
    writer_tool_calls: list[dict[str, Any]]
    no_tool_retry_used: bool
    request_id: str | None
    session_id: str | None
    answer_prefix: str
    max_context_chars: int


__all__ = ["WriterState"]
