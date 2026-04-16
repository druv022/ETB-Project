from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class EvalRow(BaseModel):
    """One evaluation example for RAGAS."""

    question: str = Field(min_length=1)
    answer: str | None = None
    contexts: list[str] = Field(default_factory=list)
    ground_truth: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunArtifacts(BaseModel):
    run_id: str = Field(min_length=1)
    out_dir: Path
    dataset_jsonl: Path
    metrics_json: Path
    report_html: Path


class RunRecord(BaseModel):
    """Append-only history record (one line per run)."""

    run_id: str = Field(min_length=1)
    iso_timestamp: str
    dataset_path: str
    metrics_path: str
    report_path: str
    aggregate_metrics: dict[str, float] = Field(default_factory=dict)
    metric_delta_vs_previous: dict[str, float] = Field(default_factory=dict)
    notes_ai: str | None = None
    testset_hash: str | None = None
    git_commit_message: str | None = None


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
