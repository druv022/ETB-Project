"""Hierarchical SQLite store and post-rerank parent expansion."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document

from etb_project.document_processing.processor import HierarchicalParent
from etb_project.vectorstore.hierarchy_store import (
    expand_child_hits_to_parents,
    get_parents_ordered,
    replace_all_hierarchy,
)


def test_get_parents_ordered_follows_first_seen_order(tmp_path: Path) -> None:
    db = tmp_path / "hierarchy.sqlite"
    parents = [
        HierarchicalParent(
            parent_id="doc::page::1",
            source="/doc.pdf",
            page_start=1,
            page_end=1,
            full_text="P1",
            metadata={"page": 1},
        ),
        HierarchicalParent(
            parent_id="doc::page::2",
            source="/doc.pdf",
            page_start=2,
            page_end=2,
            full_text="P2",
            metadata={"page": 2},
        ),
    ]
    children = [
        Document(
            page_content="c1",
            metadata={
                "child_id": "doc::p1::c0",
                "parent_id": "doc::page::1",
                "chunk_index": 0,
            },
        ),
    ]
    replace_all_hierarchy(db, parents, children)
    out = get_parents_ordered(db, ["doc::page::2", "doc::page::1", "doc::page::2"])
    assert [x[0] for x in out] == ["doc::page::2", "doc::page::1"]
    assert out[0][1] == "P2"


def test_expand_collapses_parents_preserves_caption(tmp_path: Path) -> None:
    db = tmp_path / "hierarchy.sqlite"
    parents = [
        HierarchicalParent(
            parent_id="a::page::1",
            source="a.pdf",
            page_start=1,
            page_end=1,
            full_text="FULL_ONE",
            metadata={"page": 1},
        ),
        HierarchicalParent(
            parent_id="a::page::2",
            source="a.pdf",
            page_start=2,
            page_end=2,
            full_text="FULL_TWO",
            metadata={"page": 2},
        ),
    ]
    children = [
        Document(
            page_content="x",
            metadata={"child_id": "c0", "parent_id": "a::page::1", "chunk_index": 0},
        ),
    ]
    replace_all_hierarchy(db, parents, children)

    ranked = [
        Document(
            page_content="child1",
            metadata={"child_id": "c1", "parent_id": "a::page::1", "chunk_index": 0},
        ),
        Document(
            page_content="Image caption: cap",
            metadata={"source": "a.pdf", "page": 1},
        ),
        Document(
            page_content="child2",
            metadata={"child_id": "c2", "parent_id": "a::page::1", "chunk_index": 1},
        ),
        Document(
            page_content="child3",
            metadata={"child_id": "c3", "parent_id": "a::page::2", "chunk_index": 0},
        ),
    ]
    out = expand_child_hits_to_parents(
        ranked,
        db,
        max_parents=10,
        max_total_chars=10_000,
    )
    assert len(out) == 3
    assert out[0].page_content == "FULL_ONE"
    assert out[0].metadata.get("hierarchy_expanded") is True
    assert "caption" in out[1].page_content.lower()
    assert out[2].page_content == "FULL_TWO"


def test_expand_respects_max_parents_and_chars(tmp_path: Path) -> None:
    db = tmp_path / "hierarchy.sqlite"
    parents = [
        HierarchicalParent(
            parent_id=f"p{i}",
            source="s",
            page_start=i,
            page_end=i,
            full_text="ABCDEFGH",
            metadata={},
        )
        for i in range(3)
    ]
    ch = [
        Document(
            page_content="t",
            metadata={"child_id": f"cc{i}", "parent_id": f"p{i}", "chunk_index": 0},
        )
        for i in range(3)
    ]
    replace_all_hierarchy(db, parents, ch)

    ranked = [
        Document(
            page_content="x",
            metadata={"child_id": f"k{i}", "parent_id": f"p{i}", "chunk_index": 0},
        )
        for i in range(3)
    ]
    out = expand_child_hits_to_parents(
        ranked,
        db,
        max_parents=1,
        max_total_chars=4,
    )
    assert len(out) == 1
    assert out[0].page_content == "ABCD"


def test_expand_no_db_returns_input() -> None:
    docs = [Document(page_content="x", metadata={"parent_id": "p"})]
    assert (
        expand_child_hits_to_parents(
            docs,
            Path("/nonexistent/nope.sqlite"),
            max_parents=5,
            max_total_chars=100,
        )
        is docs
    )
