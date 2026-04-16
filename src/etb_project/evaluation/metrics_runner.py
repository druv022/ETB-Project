from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

from datasets import Dataset

from etb_project.evaluation.eval_models import build_ragas_scoring_llm_and_embeddings
from etb_project.evaluation.schemas import EvalRow


@dataclass(frozen=True)
class EvalMetricsResult:
    per_row: list[dict[str, Any]]
    aggregate: dict[str, float]


def _has_ground_truth(rows: list[EvalRow]) -> bool:
    return any((r.ground_truth or "").strip() for r in rows)


def _float_score(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        x = float(v)
        return None if math.isnan(x) else x
    if hasattr(v, "value") and isinstance(v.value, (int, float)):
        x = float(v.value)
        return None if math.isnan(x) else x
    return None


def _aggregate_from_scores(scores: list[dict[str, Any]]) -> dict[str, float]:
    """Mean per metric across rows (RAGAS-style nan-safe aggregate)."""
    if not scores:
        return {}
    try:
        from ragas.utils import safe_nanmean
    except Exception:  # pragma: no cover
        safe_nanmean = None  # type: ignore[assignment]

    keys = scores[0].keys()
    out: dict[str, float] = {}
    for k in keys:
        vals: list[float] = []
        for row in scores:
            fv = _float_score(row.get(k))
            if fv is not None:
                vals.append(fv)
        if not vals:
            continue
        if safe_nanmean is not None:
            out[str(k)] = float(safe_nanmean(vals))
        else:
            out[str(k)] = float(sum(vals) / len(vals))
    return out


def _per_row_records(result: Any) -> list[dict[str, Any]]:
    try:
        df = result.to_pandas()
        return cast(list[dict[str, Any]], df.to_dict(orient="records"))
    except Exception:  # pragma: no cover
        pass
    try:
        scores = getattr(result, "scores", None) or []
        ds = getattr(result, "dataset", None)
        if ds is None or not scores:
            return []
        rows_out: list[dict[str, Any]] = []
        n = min(len(scores), len(ds))
        for i in range(n):
            base = dict(ds[i]) if hasattr(ds, "__getitem__") else {}
            merged = {**base, **scores[i]}
            rows_out.append(merged)
        return rows_out
    except Exception:  # pragma: no cover
        return []


def _build_metrics(
    *,
    llm: Any,
    embeddings: Any,
    has_ground_truth: bool,
) -> list[Any]:
    from ragas.metrics.collections import (
        AnswerCorrectness,
        AnswerRelevancy,
        ContextPrecision,
        ContextPrecisionWithoutReference,
        ContextRecall,
        Faithfulness,
    )

    metrics: list[Any] = [
        Faithfulness(llm=llm),
        AnswerRelevancy(llm=llm, embeddings=embeddings),
    ]
    if has_ground_truth:
        metrics.extend(
            [
                ContextPrecision(llm=llm),
                ContextRecall(llm=llm),
                AnswerCorrectness(llm=llm, embeddings=embeddings),
            ]
        )
    else:
        metrics.append(
            ContextPrecisionWithoutReference(llm=llm, name="context_precision")
        )
    return metrics


def evaluate_rows(rows: list[EvalRow]) -> EvalMetricsResult:
    """Run RAGAS metrics over collected rows."""
    try:
        from ragas import evaluate
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            'ragas is not installed. Install with: pip install -e ".[eval]"'
        ) from exc

    llm, embeddings = build_ragas_scoring_llm_and_embeddings()
    has_gt = _has_ground_truth(rows)
    metrics = _build_metrics(llm=llm, embeddings=embeddings, has_ground_truth=has_gt)

    payload: dict[str, Any] = {
        "question": [r.question for r in rows],
        "answer": [r.answer or "" for r in rows],
        "contexts": [r.contexts for r in rows],
    }
    if has_gt:
        payload["ground_truth"] = [r.ground_truth or "" for r in rows]

    ds = Dataset.from_dict(payload)

    result = evaluate(
        ds,
        metrics=metrics,
        llm=llm,
        embeddings=embeddings,
        raise_exceptions=False,
    )

    per_row = _per_row_records(result)
    aggregate: dict[str, float] = {}
    try:
        scores = getattr(result, "scores", None)
        if isinstance(scores, list):
            aggregate = _aggregate_from_scores(scores)
    except Exception:  # pragma: no cover
        aggregate = {}

    return EvalMetricsResult(per_row=per_row, aggregate=aggregate)
