"""Tests for evaluation HTTP runner (mocked)."""

from __future__ import annotations

from etb_project.evaluation.http_runner import OrchestratorClient, collect_answers
from etb_project.evaluation.schemas import EvalRow


def test_collect_answers_maps_sources_and_phase(monkeypatch) -> None:
    """Collect maps sources.content into contexts and captures phase."""

    def fake_chat(self: OrchestratorClient, *, message: str, k=None):  # type: ignore[no-untyped-def]
        assert message == "q1"
        return {
            "answer": "a1",
            "phase": "answer",
            "sources": [{"content": "c1"}, {"content": ""}, {"content": "c2"}],
        }

    monkeypatch.setattr(OrchestratorClient, "chat", fake_chat)
    base = [EvalRow(question="q1", ground_truth="gt")]
    out = collect_answers(base_rows=base, orchestrator_base_url="http://x")
    assert out[0].answer == "a1"
    assert out[0].contexts == ["c1", "c2"]
    assert out[0].metadata["phase"] == "answer"
    assert out[0].ground_truth == "gt"
