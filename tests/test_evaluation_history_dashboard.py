"""Tests for evaluation history and dashboard generation."""

from __future__ import annotations

from pathlib import Path

import pytest

from etb_project.evaluation.dashboard import write_dashboard_html
from etb_project.evaluation.history import (
    append_history,
    compute_metric_delta,
    compute_testset_hash,
    evals_root,
    last_record,
)
from etb_project.evaluation.schemas import EvalRow, RunRecord


def test_compute_testset_hash_deterministic() -> None:
    """Same rows yield same stable short hash."""
    rows = [EvalRow(question="q", ground_truth="gt"), EvalRow(question="q2")]
    h1 = compute_testset_hash(rows)
    h2 = compute_testset_hash(rows)
    assert h1 == h2
    assert len(h1) == 16


def test_history_append_last_and_delta(tmp_path: Path) -> None:
    """History append writes JSONL and delta compares aggregates."""
    repo_root = tmp_path
    (evals_root(repo_root) / "runs").mkdir(parents=True, exist_ok=True)
    r1 = RunRecord(
        run_id="r1",
        iso_timestamp="t1",
        dataset_path="d1",
        metrics_path="m1",
        report_path="p1",
        aggregate_metrics={"faithfulness": 0.5},
    )
    append_history(repo_root, r1)
    assert last_record(repo_root).run_id == "r1"

    r2 = RunRecord(
        run_id="r2",
        iso_timestamp="t2",
        dataset_path="d2",
        metrics_path="m2",
        report_path="p2",
        aggregate_metrics={"faithfulness": 0.7},
        metric_delta_vs_previous=compute_metric_delta(r1, {"faithfulness": 0.7}),
    )
    append_history(repo_root, r2)
    last = last_record(repo_root)
    assert last.run_id == "r2"
    assert last.metric_delta_vs_previous["faithfulness"] == pytest.approx(0.2)


def test_write_dashboard_html(tmp_path: Path) -> None:
    """Dashboard HTML embeds history JSON and filter controls."""
    repo_root = tmp_path
    append_history(
        repo_root,
        RunRecord(
            run_id="r1",
            iso_timestamp="t1",
            dataset_path="d1",
            metrics_path="m1",
            report_path="runs/r1/report.html",
            aggregate_metrics={"faithfulness": 0.5},
            notes_ai="hello",
        ),
    )
    out = write_dashboard_html(repo_root)
    html = out.read_text(encoding="utf-8")
    assert "ETB Evaluation Dashboard" in html
    assert "Search Notes" in html
    assert '"run_id": "r1"' in html
