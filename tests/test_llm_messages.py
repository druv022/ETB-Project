"""Tests for orchestrator llm_messages helpers."""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document

from etb_project.orchestrator.llm_messages import (
    build_grounded_answer_human_message,
    strip_llm_tool_markup,
    truncate_documents_by_chars,
)


def test_truncate_documents_by_chars_first_seen() -> None:
    docs = [
        Document(page_content="a" * 100, metadata={}),
        Document(page_content="b" * 100, metadata={}),
    ]
    out, truncated = truncate_documents_by_chars(docs, 150)
    assert truncated is True
    assert len(out) == 2
    assert len(out[0].page_content) == 100
    assert len(out[1].page_content) == 50


def test_strip_llm_tool_markup_fake_tool_call() -> None:
    raw = (
        "<tool_call> <function=finalize_answer> <parameter=answer> Hello world. "
        "</parameter> </function> </tool_call>"
    )
    assert strip_llm_tool_markup(raw) == "Hello world."


def test_strip_llm_tool_markup_plain_text_unchanged() -> None:
    assert strip_llm_tool_markup("No tags here.") == "No tags here."


def test_build_grounded_answer_includes_delimiters() -> None:
    human = build_grounded_answer_human_message(
        question="Q?",
        documents=[Document(page_content="body", metadata={})],
        context_truncated=False,
    )
    text = human.content if isinstance(human.content, str) else str(human.content)
    assert "---BEGIN CONTEXT---" in text
    assert "---END CONTEXT---" in text
