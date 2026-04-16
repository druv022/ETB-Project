from __future__ import annotations

import hashlib
from pathlib import Path

from etb_project.evaluation.dataset_io import read_jsonl, write_jsonl
from etb_project.evaluation.schemas import EvalRow, RunRecord


def evals_root(repo_root: Path) -> Path:
    return repo_root / "data" / "evals"


def history_path(repo_root: Path) -> Path:
    return evals_root(repo_root) / "eval_history.jsonl"


def compute_testset_hash(rows: list[EvalRow]) -> str:
    h = hashlib.sha256()
    for r in rows:
        h.update((r.question or "").encode("utf-8"))
        h.update(b"\n")
        h.update((r.ground_truth or "").encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def load_history(repo_root: Path) -> list[RunRecord]:
    hp = history_path(repo_root)
    if not hp.exists():
        return []
    return [RunRecord.model_validate(o) for o in read_jsonl(hp)]


def append_history(repo_root: Path, record: RunRecord) -> None:
    hp = history_path(repo_root)
    prev = load_history(repo_root)
    prev.append(record)
    write_jsonl(hp, (r.model_dump() for r in prev))


def compute_metric_delta(
    previous: RunRecord | None, current_aggregate: dict[str, float]
) -> dict[str, float]:
    if previous is None:
        return {}
    out: dict[str, float] = {}
    for k, v in current_aggregate.items():
        pv = previous.aggregate_metrics.get(k)
        if isinstance(pv, (int, float)):
            out[k] = float(v) - float(pv)
    return out


def last_record(repo_root: Path) -> RunRecord | None:
    hist = load_history(repo_root)
    return hist[-1] if hist else None
