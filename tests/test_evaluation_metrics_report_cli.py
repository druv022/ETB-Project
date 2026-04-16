"""Tests for metrics/report writing and CLI evaluate flow (mocked)."""

from __future__ import annotations

import json
from pathlib import Path

from etb_project.evaluation.cli import cmd_evaluate
from etb_project.evaluation.dataset_io import write_eval_rows
from etb_project.evaluation.schemas import EvalRow


def test_cmd_evaluate_writes_metrics_report_history_dashboard(
    monkeypatch, tmp_path: Path
) -> None:
    """Evaluate command writes expected artifacts and updates history/dashboard."""

    # Fake repo root used by cli._repo_root()
    monkeypatch.setattr("etb_project.evaluation.cli._repo_root", lambda: tmp_path)

    # Prepare input dataset.
    in_path = tmp_path / "in.jsonl"
    write_eval_rows(in_path, [EvalRow(question="q", answer="a", contexts=["c"])])

    class FakeMetrics:
        per_row = [{"faithfulness": 0.9}]
        aggregate = {"faithfulness": 0.9}

    monkeypatch.setattr(
        "etb_project.evaluation.cli.evaluate_rows", lambda rows: FakeMetrics()
    )
    monkeypatch.setattr(
        "etb_project.evaluation.cli.generate_notes_ai",
        lambda previous, current: "notes",
    )
    # Avoid git operations.
    monkeypatch.setattr("etb_project.evaluation.cli._bool_env", lambda *a, **k: False)

    ns = type("Args", (), {})()
    ns.input = str(in_path)
    ns.run_id = "run123"
    ns.no_notes_llm = False
    ns.git_commit = False

    rc = cmd_evaluate(ns)
    assert rc == 0

    metrics_path = tmp_path / "data" / "evals" / "runs" / "run123" / "metrics.json"
    report_path = tmp_path / "data" / "evals" / "runs" / "run123" / "report.html"
    hist_path = tmp_path / "data" / "evals" / "eval_history.jsonl"
    dash_path = tmp_path / "data" / "evals" / "dashboard.html"

    assert metrics_path.exists()
    assert report_path.exists()
    assert hist_path.exists()
    assert dash_path.exists()

    payload = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run123"
    assert payload["aggregate_metrics"]["faithfulness"] == 0.9
