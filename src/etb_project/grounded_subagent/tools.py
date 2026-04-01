"""LangChain tool schemas for the grounded writer (bodies are placeholders)."""

from __future__ import annotations

from langchain_core.tools import tool

from etb_project.grounded_subagent import templates as _t


@tool(description=_t.tool_description_record_thought())
def record_thought(thought: str) -> str:
    """Placeholder body; execution is in the writer graph."""
    return ""


@tool(description=_t.tool_description_submit_plan())
def submit_plan(steps: str) -> str:
    """Placeholder body; execution is in the writer graph."""
    return ""


@tool(description=_t.tool_description_retrieve_more())
def retrieve_more(query: str) -> str:
    """Placeholder body; execution is in the writer graph."""
    return ""


@tool(description=_t.tool_description_draft_code_hook())
def draft_code_hook(code: str, purpose: str) -> str:
    """Placeholder body; execution is in the writer graph."""
    return ""


@tool(description=_t.tool_description_submit_final_answer())
def submit_final_answer(answer: str) -> str:
    """Placeholder body; execution is in the writer graph."""
    return ""


WRITER_TOOLS = [
    record_thought,
    submit_plan,
    retrieve_more,
    draft_code_hook,
    submit_final_answer,
]

__all__ = [
    "WRITER_TOOLS",
    "draft_code_hook",
    "record_thought",
    "retrieve_more",
    "submit_final_answer",
    "submit_plan",
]
