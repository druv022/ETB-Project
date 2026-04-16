"""Tests for evaluation dataset JSONL IO and merging."""

from __future__ import annotations

from pathlib import Path

import pytest

from etb_project.evaluation.dataset_io import (
    merge_rows,
    read_eval_rows,
    read_jsonl,
    write_eval_rows,
    write_jsonl,
)
from etb_project.evaluation.schemas import EvalRow


def test_write_and_read_jsonl_roundtrip(tmp_path: Path) -> None:
    """Writes JSONL and reads it back."""
    p = tmp_path / "x.jsonl"
    write_jsonl(p, [{"a": 1}, {"b": "two"}])
    assert read_jsonl(p) == [{"a": 1}, {"b": "two"}]


def test_read_jsonl_missing_file(tmp_path: Path) -> None:
    """Reading a missing file should raise."""
    with pytest.raises(FileNotFoundError):
        read_jsonl(tmp_path / "missing.jsonl")


def test_write_and_read_eval_rows_roundtrip(tmp_path: Path) -> None:
    """Writes EvalRows and reads them back."""
    rows = [
        EvalRow(question="q1", answer="a1", contexts=["c1"]),
        EvalRow(question="q2", ground_truth="gt2"),
    ]
    p = tmp_path / "rows.jsonl"
    write_eval_rows(p, rows)
    got = read_eval_rows(p)
    assert got[0].question == "q1"
    assert got[0].contexts == ["c1"]
    assert got[1].ground_truth == "gt2"


def test_merge_rows_prefers_updates(tmp_path: Path) -> None:
    """Merge keeps base question and prefers update fields."""
    base = [
        EvalRow(
            question="q", answer=None, contexts=[], ground_truth="gt", metadata={"a": 1}
        )
    ]
    upd = [
        EvalRow(
            question="q",
            answer="a",
            contexts=["c"],
            ground_truth=None,
            metadata={"b": 2},
        )
    ]
    merged = merge_rows(base, upd)
    assert merged[0].answer == "a"
    assert merged[0].contexts == ["c"]
    assert merged[0].ground_truth == "gt"
    assert merged[0].metadata == {"a": 1, "b": 2}


def test_merge_rows_length_mismatch_raises() -> None:
    """Mismatched lengths are invalid."""
    with pytest.raises(ValueError):
        merge_rows(
            [EvalRow(question="q1")], [EvalRow(question="q1"), EvalRow(question="q2")]
        )


def test_merge_rows_question_mismatch_raises() -> None:
    """Mismatched ordering/questions are invalid."""
    with pytest.raises(ValueError):
        merge_rows([EvalRow(question="q1")], [EvalRow(question="q2")])
