"""Tests for AI notes generation and git commit helper (mocked)."""

from __future__ import annotations

from pathlib import Path

from etb_project.evaluation.git_commit import git_commit_eval_artifacts
from etb_project.evaluation.notes import generate_notes_ai
from etb_project.evaluation.schemas import RunRecord


def test_generate_notes_first_run_no_prev() -> None:
    """First run uses deterministic message."""
    current = RunRecord(
        run_id="r",
        iso_timestamp="t",
        dataset_path="d",
        metrics_path="m",
        report_path="p",
        aggregate_metrics={"faithfulness": 0.5},
    )
    out = generate_notes_ai(previous=None, current=current)
    assert "First recorded run" in out


def test_generate_notes_uses_llm(monkeypatch) -> None:
    """When previous exists, uses ChatOpenAI.invoke output."""

    class FakeMsg:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeLLM:
        def __init__(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
            self.kwargs = kwargs

        def invoke(self, prompt: str):  # type: ignore[no-untyped-def]
            assert "Previous aggregate metrics" in prompt
            return FakeMsg("Changed because X.")

    monkeypatch.setattr("etb_project.evaluation.notes.ChatOpenAI", FakeLLM)
    prev = RunRecord(
        run_id="p",
        iso_timestamp="t0",
        dataset_path="d0",
        metrics_path="m0",
        report_path="p0",
        aggregate_metrics={"faithfulness": 0.4},
    )
    current = RunRecord(
        run_id="c",
        iso_timestamp="t1",
        dataset_path="d1",
        metrics_path="m1",
        report_path="p1",
        aggregate_metrics={"faithfulness": 0.6},
        metric_delta_vs_previous={"faithfulness": 0.2},
    )
    out = generate_notes_ai(previous=prev, current=current)
    assert out == "Changed because X."


def test_git_commit_eval_artifacts_runs_git(monkeypatch, tmp_path: Path) -> None:
    """Stages and commits the provided files."""
    calls: list[list[str]] = []

    def fake_run(cmd, cwd=None, check=None):  # type: ignore[no-untyped-def]
        assert cwd == tmp_path
        assert check is True
        calls.append(list(cmd))
        return 0

    monkeypatch.setattr("etb_project.evaluation.git_commit.subprocess.run", fake_run)
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    git_commit_eval_artifacts(
        repo_root=tmp_path,
        paths_to_add=[tmp_path / "a.txt"],
        commit_message="msg",
    )
    assert calls[0][:2] == ["git", "add"]
    assert calls[1][:2] == ["git", "commit"]
