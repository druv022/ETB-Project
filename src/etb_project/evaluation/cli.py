from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path

from etb_project.evaluation.dashboard import write_dashboard_html
from etb_project.evaluation.dataset_io import read_eval_rows, write_eval_rows
from etb_project.evaluation.git_commit import git_commit_eval_artifacts
from etb_project.evaluation.history import (
    append_history,
    compute_metric_delta,
    compute_testset_hash,
    evals_root,
    last_record,
)
from etb_project.evaluation.http_runner import collect_answers
from etb_project.evaluation.metrics_runner import evaluate_rows
from etb_project.evaluation.notes import generate_notes_ai
from etb_project.evaluation.report import write_metrics_json, write_run_report_html
from etb_project.evaluation.schemas import RunArtifacts, RunRecord, now_utc_iso
from etb_project.evaluation.synthetic import generate_synthetic_questions_from_pdf


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "off", "")


def _build_run_artifacts(repo_root: Path, run_id: str) -> RunArtifacts:
    out_dir = evals_root(repo_root) / "runs" / run_id
    return RunArtifacts(
        run_id=run_id,
        out_dir=out_dir,
        dataset_jsonl=out_dir / "run_dataset.jsonl",
        metrics_json=out_dir / "metrics.json",
        report_html=out_dir / "report.html",
    )


def cmd_synthetic(args: argparse.Namespace) -> int:
    rows = generate_synthetic_questions_from_pdf(
        pdf_path=Path(args.pdf), testset_size=args.testset_size
    )
    write_eval_rows(Path(args.out), rows)
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    base = read_eval_rows(Path(args.input))
    collected = collect_answers(
        base_rows=base,
        orchestrator_base_url=args.orchestrator_base_url,
        k=args.k,
        api_key=args.api_key,
        timeout_s=args.timeout_s,
    )
    write_eval_rows(Path(args.out), collected)
    return 0


def _commit_message(run_id: str, aggregate: dict[str, float], notes: str | None) -> str:
    # Keep first line short and grep-friendly.
    parts = [f"RAGAS eval: run {run_id}"]
    for key in sorted(aggregate.keys())[:3]:
        parts.append(f"{key}={aggregate[key]:.3f}")
    first = " | ".join(parts)
    if notes:
        note1 = notes.splitlines()[0].strip()
        if note1:
            first = f"{first} | notes: {note1[:80]}"
    return first


def cmd_evaluate(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_id = args.run_id or uuid.uuid4().hex[:12]
    iso = now_utc_iso()
    artifacts = _build_run_artifacts(repo_root, run_id)

    rows = read_eval_rows(Path(args.input))
    metrics = evaluate_rows(rows)

    testset_hash = compute_testset_hash(rows)
    metrics_payload = {
        "run_id": run_id,
        "iso_timestamp": iso,
        "testset_hash": testset_hash,
        "aggregate_metrics": metrics.aggregate,
        "per_row_metrics": metrics.per_row,
    }
    write_metrics_json(artifacts.metrics_json, payload=metrics_payload)
    write_run_report_html(
        artifacts,
        iso_timestamp=iso,
        rows=rows,
        per_row_metrics=metrics.per_row,
        aggregate_metrics=metrics.aggregate,
    )

    prev = last_record(repo_root)
    delta = compute_metric_delta(prev, metrics.aggregate)
    record = RunRecord(
        run_id=run_id,
        iso_timestamp=iso,
        dataset_path=str(Path(args.input)),
        metrics_path=str(artifacts.metrics_json.relative_to(repo_root)),
        report_path=str(artifacts.report_html.relative_to(repo_root)),
        aggregate_metrics=metrics.aggregate,
        metric_delta_vs_previous=delta,
        testset_hash=testset_hash,
    )

    if not args.no_notes_llm:
        record.notes_ai = generate_notes_ai(previous=prev, current=record)

    do_commit = bool(args.git_commit or _bool_env("ETB_EVAL_GIT_COMMIT", False))
    if do_commit:
        record.git_commit_message = _commit_message(
            run_id, metrics.aggregate, record.notes_ai
        )

    append_history(repo_root, record)
    dash_path = write_dashboard_html(repo_root)

    if do_commit:
        # Commit the key artifacts intended for review.
        to_add = [
            Path(record.metrics_path),
            Path(record.report_path),
            Path("data/evals/eval_history.jsonl"),
            Path(dash_path.relative_to(repo_root)),
        ]
        git_commit_eval_artifacts(
            repo_root=repo_root,
            paths_to_add=[repo_root / p for p in to_add],
            commit_message=record.git_commit_message or "",
        )

    return 0


def cmd_pipeline(args: argparse.Namespace) -> int:
    repo_root = _repo_root()
    run_id = args.run_id or uuid.uuid4().hex[:12]
    out_dir = evals_root(repo_root) / "runs" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    questions_path = out_dir / "synthetic_questions.jsonl"
    run_dataset_path = out_dir / "run_dataset.jsonl"

    rows = generate_synthetic_questions_from_pdf(
        pdf_path=Path(args.pdf), testset_size=args.testset_size
    )
    write_eval_rows(questions_path, rows)

    collected = collect_answers(
        base_rows=rows,
        orchestrator_base_url=args.orchestrator_base_url,
        k=args.k,
        api_key=args.api_key,
        timeout_s=args.timeout_s,
    )
    write_eval_rows(run_dataset_path, collected)

    # Reuse evaluate by invoking cmd_evaluate semantics.
    ns = argparse.Namespace(
        input=str(run_dataset_path),
        run_id=run_id,
        no_notes_llm=args.no_notes_llm,
        git_commit=args.git_commit,
    )
    return cmd_evaluate(ns)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="ETB RAGAS evaluation tooling (decoupled).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("synthetic", help="Generate synthetic questions from a PDF.")
    s.add_argument("--pdf", required=True)
    s.add_argument("--testset-size", type=int, default=20)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_synthetic)

    c = sub.add_parser(
        "collect", help="Collect answers from orchestrator for a dataset."
    )
    c.add_argument("--input", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--orchestrator-base-url", required=True)
    c.add_argument("--k", type=int, default=None)
    c.add_argument("--api-key", default=None)
    c.add_argument("--timeout-s", type=float, default=60.0)
    c.set_defaults(func=cmd_collect)

    e = sub.add_parser(
        "evaluate", help="Run RAGAS and write report + history + dashboard."
    )
    e.add_argument("--input", required=True)
    e.add_argument("--run-id", default=None)
    e.add_argument("--no-notes-llm", action="store_true", default=False)
    e.add_argument("--git-commit", action="store_true", default=False)
    e.set_defaults(func=cmd_evaluate)

    pl = sub.add_parser("pipeline", help="Synthetic → collect → evaluate (one run).")
    pl.add_argument("--pdf", required=True)
    pl.add_argument("--testset-size", type=int, default=20)
    pl.add_argument("--orchestrator-base-url", required=True)
    pl.add_argument("--k", type=int, default=None)
    pl.add_argument("--api-key", default=None)
    pl.add_argument("--timeout-s", type=float, default=60.0)
    pl.add_argument("--run-id", default=None)
    pl.add_argument("--no-notes-llm", action="store_true", default=False)
    pl.add_argument("--git-commit", action="store_true", default=False)
    pl.set_defaults(func=cmd_pipeline)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
