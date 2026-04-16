from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from etb_project.evaluation.schemas import EvalRow


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)
    items: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def read_eval_rows(path: Path) -> list[EvalRow]:
    return [EvalRow.model_validate(o) for o in read_jsonl(path)]


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
    path.write_text(data, encoding="utf-8")


def write_eval_rows(path: Path, rows: Iterable[EvalRow]) -> None:
    write_jsonl(path, (r.model_dump() for r in rows))


def merge_rows(base: list[EvalRow], updates: list[EvalRow]) -> list[EvalRow]:
    """Merge by index (same ordering), preferring non-null update fields."""
    if len(base) != len(updates):
        raise ValueError("base and updates must be same length")
    out: list[EvalRow] = []
    for b, u in zip(base, updates, strict=True):
        if b.question != u.question:
            raise ValueError("base and updates questions must align")
        merged = EvalRow(
            question=b.question,
            answer=u.answer if u.answer is not None else b.answer,
            contexts=u.contexts if u.contexts else b.contexts,
            ground_truth=(
                u.ground_truth if u.ground_truth is not None else b.ground_truth
            ),
            metadata={**b.metadata, **u.metadata},
        )
        out.append(merged)
    return out
