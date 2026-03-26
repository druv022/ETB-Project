"""
Workflow-style orchestration for report generation.

This module organises the reporting process into a sequence of logical
steps (\"nodes\") that can be wired into a LangGraph graph or executed
directly in Python. It operates entirely under `tools/` and does not
depend on the main `src/` application.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd

from . import time_windows
from .llm_client import (
    evaluate_report_quality,
    load_evaluation_config,
    rewrite_report_narrative,
)
from .tools_analytics import compute_period_stats
from .tools_charts import build_charts
from .tools_narrative import generate_narrative, no_data_narrative
from .tools_pdf import render_pdf
from .tools_sql import SQLQuery, execute_sql, generate_sql_query

GRANULARITY_ORDER = [
    "weekly",
    "biweekly",
    "monthly",
    "quarterly",
    "semiannual",
    "yearly",
]


class PeriodDict(TypedDict):
    # Single reporting period, identified by a label and an inclusive date range.
    label: str
    start: date
    end: date


class ReportState(TypedDict, total=False):
    # Mutable workflow state shared across nodes in the reporting pipeline.
    category: str
    date_start: date
    date_end: date
    requested_granularities: list[str] | None
    current_stage: str | None
    periods: list[PeriodDict]
    current_period_index: int
    generated_reports: list[dict[str, object]]
    output_dir: Path
    narrative_backend: str
    llm_model: str | None
    # Intermediate outputs from tool nodes (per current period).
    # current_period_df is in-memory only; other fields are JSON-serializable.
    current_period_df: Any  # pd.DataFrame, used between sql and stats nodes
    current_period_stats: dict[str, object] | None
    current_period_chart_paths: list[str] | None  # paths as strings for serialization
    current_period_narrative: str | None
    current_period_quality_score: float | None
    current_period_quality_feedback: str | None
    current_period_attempt: int


def determine_stage(state: ReportState) -> ReportState:
    """Set or advance the current granularity stage."""

    allowed = state.get("requested_granularities") or GRANULARITY_ORDER
    if state.get("current_stage") is None:
        state["current_stage"] = allowed[0]
        return state

    try:
        idx = allowed.index(state.get("current_stage"))
    except ValueError:
        state["current_stage"] = None
        return state

    if idx + 1 < len(allowed):
        state["current_stage"] = allowed[idx + 1]
    else:
        state["current_stage"] = None
    return state


def generate_periods(state: ReportState) -> ReportState:
    """Populate the list of periods for the current stage."""

    if state.get("current_stage") is None:
        state["periods"] = []
        return state

    start, end = state["date_start"], state["date_end"]
    stage = state.get("current_stage")

    raw_periods = time_windows.get_periods_for_granularity(stage, start, end)  # type: ignore[arg-type]

    state["periods"] = [
        PeriodDict(label=p.label, start=p.start, end=p.end) for p in raw_periods
    ]
    state["current_period_index"] = 0
    return state


def has_more_periods(state: ReportState) -> bool:
    return state.get("current_period_index", 0) < len(state.get("periods", []))


def build_sql_for_current_period(state: ReportState) -> SQLQuery:
    period = state["periods"][state["current_period_index"]]
    return generate_sql_query(
        category=state["category"],
        period_start=period["start"],
        period_end=period["end"],
        dimensions=None,
        metrics=None,
    )


def process_current_period(state: ReportState) -> ReportState:
    """
    Run the full pipeline for the current period:
    - SQL query and execution
    - Stats computation
    - Chart generation
    - Narrative generation
    - PDF assembly
    """

    period = state["periods"][state["current_period_index"]]
    query = build_sql_for_current_period(state)
    df: pd.DataFrame = execute_sql(query)

    eval_cfg = load_evaluation_config()
    eval_enabled = bool(eval_cfg.get("evaluation_enabled", False))
    max_attempts = int(eval_cfg.get("max_regeneration_attempts", 1) or 1)
    min_score = float(eval_cfg.get("evaluation_min_score", 0.0) or 0.0)

    if df.empty:
        stats: dict[str, object] = {}
        chart_paths: list[Path] = []
        narrative = no_data_narrative(period["label"], period["start"], period["end"])
    else:
        stats = compute_period_stats(
            category=state["category"],
            period_label=period["label"],
            period_start=period["start"],
            period_end=period["end"],
        )
        charts_dir = state["output_dir"] / "charts"
        chart_paths = build_charts(
            category=state["category"],
            period_label=period["label"],
            period_start=period["start"],
            period_end=period["end"],
            stats=stats,
            output_dir=charts_dir,
        )
        narrative = generate_narrative(
            category=state["category"],
            period_label=period["label"],
            period_start=period["start"],
            period_end=period["end"],
            stats=stats,
            target_words=1000,
            backend=state.get("narrative_backend", "deterministic"),
            llm_model=state.get("llm_model"),
            granularity=state.get("current_stage"),
        )

    # Optional evaluation and regeneration loop.
    attempt = 0
    best_score: float | None = None
    best_narrative = narrative

    while eval_enabled and attempt < max_attempts:
        attempt += 1
        try:
            chart_titles = [p.name for p in chart_paths]
            eval_result = evaluate_report_quality(
                category=state["category"],
                granularity=state.get("current_stage"),
                period_label=period["label"],
                period_start=period["start"],
                period_end=period["end"],
                narrative_text=best_narrative,
                chart_titles=chart_titles,
            )
        except Exception:
            break

        score = eval_result.get("score")
        feedback_text = str(eval_result.get("raw_text") or "")

        if not isinstance(score, (int, float)):
            break

        if best_score is None or score > best_score:
            best_score = float(score)

        if score >= min_score:
            break

        # Try to improve the narrative based on feedback.
        try:
            improved = rewrite_report_narrative(
                category=state["category"],
                granularity=state.get("current_stage"),
                period_label=period["label"],
                period_start=period["start"],
                period_end=period["end"],
                original_narrative=best_narrative,
                evaluation_feedback=feedback_text,
            )
            best_narrative = improved
        except Exception:
            break

    final_narrative = best_narrative

    pdf_path = render_pdf(
        category=state["category"],
        granularity=state.get("current_stage") or "",
        period_label=period["label"],
        period_start=period["start"],
        period_end=period["end"],
        narrative_text=final_narrative,
        chart_image_paths=chart_paths,
        output_dir=state["output_dir"],
    )

    state.setdefault("generated_reports", []).append(
        {
            "stage": state.get("current_stage"),
            "period_label": period["label"],
            "start": period["start"].isoformat(),
            "end": period["end"].isoformat(),
            "pdf_path": str(pdf_path),
            "quality_score": best_score,
        }
    )
    state["current_period_index"] = state.get("current_period_index", 0) + 1
    return state


def run_workflow(
    category: str,
    start_date: date,
    end_date: date,
    requested_granularities: list[str] | None = None,
    output_dir: Path | None = None,
    narrative_backend: str = "deterministic",
    llm_model: str | None = None,
) -> ReportState:
    """
    Execute the reporting workflow over the requested date range.

    This function can be called directly from a CLI script or wrapped in
    a LangGraph StateGraph if desired.
    """

    state: ReportState = {
        "category": category,
        "date_start": start_date,
        "date_end": end_date,
        "requested_granularities": requested_granularities,
        "current_stage": None,
        "periods": [],
        "current_period_index": 0,
        "generated_reports": [],
        "output_dir": output_dir
        or Path("tools/data_generation/report_generation/output"),
        "narrative_backend": narrative_backend,
        "llm_model": llm_model,
    }

    # Iterate over all requested stages and periods.
    state = determine_stage(state)
    while state.get("current_stage") is not None:
        state = generate_periods(state)
        while has_more_periods(state):
            state = process_current_period(state)
        state = determine_stage(state)

    return state
