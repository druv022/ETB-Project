"""Tests for synthetic generation and metrics runner (mocked)."""

from __future__ import annotations

import os
import types
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from etb_project.evaluation.metrics_runner import _aggregate_from_scores, evaluate_rows
from etb_project.evaluation.schemas import EvalRow
from etb_project.evaluation.synthetic import generate_synthetic_questions_from_pdf


def test_generate_synthetic_questions_from_pdf_extracts_rows(
    monkeypatch, tmp_path: Path
) -> None:
    """Synthetic generator extracts question + ground_truth fields."""
    pdf = tmp_path / "x.pdf"
    pdf.write_text("dummy", encoding="utf-8")

    # Avoid touching real PDF loading.
    monkeypatch.setattr("etb_project.evaluation.synthetic.load_pdf", lambda p: ["doc1"])
    monkeypatch.setattr(
        "etb_project.evaluation.synthetic.build_generation_models",
        lambda: ("llm", "emb"),
    )

    class FakeTestset:
        def to_pandas(self):  # type: ignore[no-untyped-def]
            class FakeDF:
                def to_dict(self, orient="records"):  # type: ignore[no-untyped-def]
                    return [{"question": "Q1", "ground_truth": "GT1"}]

            return FakeDF()

    class FakeGen:
        @classmethod
        def from_langchain(
            cls, llm, embedding_model, knowledge_graph=None, llm_context=None
        ):  # type: ignore[no-untyped-def]
            return cls()

        def generate_with_langchain_docs(self, documents, testset_size):  # type: ignore[no-untyped-def]
            assert testset_size == 1
            return FakeTestset()

    fake_mod = types.SimpleNamespace(TestsetGenerator=FakeGen)
    monkeypatch.setitem(
        __import__("sys").modules,
        "ragas.testset.synthesizers.generate",
        fake_mod,
    )

    rows = generate_synthetic_questions_from_pdf(pdf_path=pdf, testset_size=1)
    assert rows[0].question == "Q1"
    assert rows[0].ground_truth == "GT1"


def test_evaluate_rows_uses_ragas_and_returns_aggregate(monkeypatch) -> None:
    """Metrics runner calls ragas.evaluate with metric instances and returns aggregate scores."""
    rows = [EvalRow(question="q", answer="a", contexts=["c"])]

    class FakeResult:
        scores = [{"faithfulness": 0.9}]

        def to_pandas(self):  # type: ignore[no-untyped-def]
            return pd.DataFrame([{"question": "q", "answer": "a", "faithfulness": 0.9}])

    def fake_evaluate(ds, metrics=None, llm=None, embeddings=None, **kwargs):  # type: ignore[no-untyped-def]
        assert "question" in ds.column_names
        assert metrics is not None
        assert len(metrics) == 3
        return FakeResult()

    monkeypatch.setattr(
        "etb_project.evaluation.metrics_runner.build_ragas_scoring_llm_and_embeddings",
        lambda: (MagicMock(), MagicMock()),
    )
    monkeypatch.setattr(
        "etb_project.evaluation.metrics_runner._build_metrics",
        lambda **kwargs: [MagicMock(), MagicMock(), MagicMock()],
    )
    monkeypatch.setattr("ragas.evaluate", fake_evaluate)

    res = evaluate_rows(rows)
    assert res.aggregate["faithfulness"] == 0.9
    assert res.per_row[0]["faithfulness"] == 0.9


def test_aggregate_from_scores_skips_non_numeric() -> None:
    """Aggregate ignores missing or non-numeric score cells."""
    scores = [
        {"faithfulness": 1.0, "context_precision": None},
        {"faithfulness": 0.0, "context_precision": 0.5},
    ]
    agg = _aggregate_from_scores(scores)
    assert agg["faithfulness"] == 0.5
    assert agg["context_precision"] == 0.5


@pytest.mark.integration
def test_evaluate_rows_real_ragas_smoke() -> None:
    """Optional real RAGAS call; requires API key and eval extras."""
    if not (
        os.environ.get("ETB_EVAL_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    ):
        pytest.skip("No OpenAI API key for integration test")

    pytest.importorskip("ragas")

    rows = [
        EvalRow(
            question="What is 2+2?",
            answer="4",
            contexts=["Basic arithmetic: two plus two equals four."],
            ground_truth="Four",
        )
    ]
    res = evaluate_rows(rows)
    assert res.aggregate
    assert isinstance(next(iter(res.aggregate.values())), float)
