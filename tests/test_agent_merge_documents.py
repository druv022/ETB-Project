"""Tests for content-based _merge_documents in the agent graph."""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")
from langchain_core.documents import Document

from etb_project.orchestrator.agent_graph import _merge_documents


def test_merge_same_source_different_content_keeps_both() -> None:
    """Regression: metadata source must not collapse distinct chunks."""
    a = Document(page_content="Text chunk about revenue.", metadata={"source": "x.pdf"})
    b = Document(
        page_content="Image caption: chart shows Q3 growth.",
        metadata={"source": "x.pdf"},
    )
    out = _merge_documents([], [a, b])
    assert len(out) == 2
    bodies = {d.page_content.strip() for d in out}
    assert "Text chunk about revenue." in bodies
    assert "Image caption: chart shows Q3 growth." in bodies


def test_merge_exact_duplicate_one_kept() -> None:
    d1 = Document(page_content="same body", metadata={"id": "1"})
    d2 = Document(page_content="same body", metadata={"id": "2"})
    out = _merge_documents([d1], [d2])
    assert len(out) == 1
    assert out[0].page_content == "same body"


def test_merge_substring_drops_shorter() -> None:
    long_doc = Document(
        page_content="The full paragraph about metrics and KPIs.", metadata={}
    )
    short_doc = Document(page_content="metrics", metadata={})
    out = _merge_documents([], [long_doc, short_doc])
    assert len(out) == 1
    assert "metrics" in (out[0].page_content or "")
    assert "KPIs" in (out[0].page_content or "")


def test_merge_consecutive_boundary_overlap() -> None:
    left = "a" * 10 + "OVERLAP_SHARED_15"
    right = "OVERLAP_SHARED_15" + "b" * 10
    d1 = Document(page_content=left, metadata={"chunk": 1})
    d2 = Document(page_content=right, metadata={"chunk": 2})
    out = _merge_documents([], [d1, d2])
    assert len(out) == 1
    assert "OVERLAP_SHARED_15" in (out[0].page_content or "")
    assert left + right[len("OVERLAP_SHARED_15") :] == out[0].page_content
