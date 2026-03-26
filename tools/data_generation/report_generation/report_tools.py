"""
Report generation tools as LangGraph nodes and LangChain tools.

Each reporting step (SQL, stats, charts, narrative, PDF) is implemented as:
- A graph node function that reads/writes ReportState so the pipeline is
  visible in LangGraph Studio.
- A LangChain StructuredTool with explicit inputs/outputs so an LLM agent
  can later decide which tools to call and in what order.

Graph nodes take full state and return a partial state update (merged by
LangGraph). Tools take explicit parameters and return serializable dicts.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_core.tools import StructuredTool

from .tools_analytics import compute_period_stats
from .tools_charts import build_charts
from .tools_narrative import generate_narrative, no_data_narrative
from .tools_pdf import render_pdf
from .tools_sql import execute_sql
from .workflow_graph import ReportState, build_sql_for_current_period

# ---- Graph node functions (state in, partial state out) ----


def run_sql_tool_node(state: ReportState) -> dict[str, Any]:
    """
    Tool node: run SQL for the current period and store the result in state.
    Next node (compute_stats) will read current_period_df.
    """
    query = build_sql_for_current_period(state)
    df: pd.DataFrame = execute_sql(query)
    return {
        "current_period_df": df,
        "current_period_stats": None,
        "current_period_chart_paths": None,
        "current_period_narrative": None,
    }


def compute_stats_tool_node(state: ReportState) -> dict[str, Any]:
    """
    Tool node: compute period statistics from current_period_df (or empty stats
    if no data) and store in state. Clears current_period_df after use.
    """
    period = state["periods"][state["current_period_index"]]
    # Always compute stats via the report implementation so the returned
    # structure (e.g. `summary`, `by_store`, `by_channel`) is consistent,
    # even when there is no underlying data for the period.
    stats = compute_period_stats(
        category=state["category"],
        period_label=period["label"],
        period_start=period["start"],
        period_end=period["end"],
    )

    return {
        "current_period_df": None,
        "current_period_stats": stats,
    }


def build_charts_tool_node(state: ReportState) -> dict[str, Any]:
    """
    Tool node: build charts for the current period from current_period_stats
    and store chart paths in state.
    """
    period = state["periods"][state["current_period_index"]]
    stats = state.get("current_period_stats") or {}
    output_dir = Path(state["output_dir"]) / "charts"
    chart_paths: list[Path] = build_charts(
        category=state["category"],
        period_label=period["label"],
        period_start=period["start"],
        period_end=period["end"],
        stats=stats,
        output_dir=output_dir,
    )
    return {"current_period_chart_paths": [str(p) for p in chart_paths]}


def generate_narrative_tool_node(state: ReportState) -> dict[str, Any]:
    """
    Tool node: generate narrative text for the current period from
    current_period_stats and store in state. Uses placeholder when no data.
    """
    period = state["periods"][state["current_period_index"]]
    stats = state.get("current_period_stats") or {}

    if not stats:
        narrative = no_data_narrative(period["label"], period["start"], period["end"])
    else:
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

    return {"current_period_narrative": narrative}


def render_pdf_tool_node(state: ReportState) -> dict[str, Any]:
    """
    Tool node: render PDF from current_period_narrative and chart paths,
    append to generated_reports, advance period index, and clear period state.
    """
    period = state["periods"][state["current_period_index"]]
    narrative = state.get("current_period_narrative") or ""
    chart_path_strs = state.get("current_period_chart_paths") or []
    chart_paths = [Path(p) for p in chart_path_strs]

    pdf_path = render_pdf(
        category=state["category"],
        granularity=state.get("current_stage") or "",
        period_label=period["label"],
        period_start=period["start"],
        period_end=period["end"],
        narrative_text=narrative,
        chart_image_paths=chart_paths,
        output_dir=Path(state["output_dir"]),
    )

    reports = list(state.get("generated_reports") or [])
    reports.append(
        {
            "stage": state.get("current_stage"),
            "period_label": period["label"],
            "start": period["start"].isoformat(),
            "end": period["end"].isoformat(),
            "pdf_path": str(pdf_path),
        }
    )

    return {
        "generated_reports": reports,
        "current_period_index": state.get("current_period_index", 0) + 1,
        "current_period_df": None,
        "current_period_stats": None,
        "current_period_chart_paths": None,
        "current_period_narrative": None,
    }


# ---- LangChain tools (explicit args, for LLM agent use) ----


def _run_sql_impl(
    category: str,
    period_start: str,
    period_end: str,
) -> dict:
    """Execute SQL for the given category and date range. Returns row count and preview."""
    from .tools_sql import execute_sql, generate_sql_query

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    query = generate_sql_query(category=category, period_start=start, period_end=end)
    df = execute_sql(query)
    return {"row_count": len(df), "columns": list(df.columns) if not df.empty else []}


def _compute_stats_impl(
    category: str,
    period_label: str,
    period_start: str,
    period_end: str,
    row_count: int,
) -> dict:
    """Compute analytics stats for a period. Use after run_sql; row_count is for context."""

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    from .tools_analytics import compute_period_stats

    stats = compute_period_stats(
        category=category,
        period_label=period_label,
        period_start=start,
        period_end=end,
    )
    return {"stats_keys": list(stats.keys()), "row_count_used": row_count}


run_sql_tool = StructuredTool.from_function(
    name="run_sql",
    description="Run a parameterised SQL query for the given report category and date range (period_start, period_end as YYYY-MM-DD). Returns row count and column list.",
    func=_run_sql_impl,
)

compute_stats_tool = StructuredTool.from_function(
    name="compute_stats",
    description="Compute period statistics (KPIs, aggregates) for the given category and period. Call after run_sql for the same period.",
    func=_compute_stats_impl,
)


# Stub tools for charts, narrative, pdf - they need full state in graph; for LLM they can take explicit args and call the same helpers.
def _build_charts_impl(
    category: str,
    period_label: str,
    period_start: str,
    period_end: str,
    output_dir: str,
    stats_json: str,
) -> dict:
    import json

    from .tools_charts import build_charts

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    stats = json.loads(stats_json) if stats_json else {}
    paths = build_charts(
        category=category,
        period_label=period_label,
        period_start=start,
        period_end=end,
        stats=stats,
        output_dir=Path(output_dir),
    )
    return {"chart_paths": [str(p) for p in paths]}


def _generate_narrative_impl(
    category: str,
    period_label: str,
    period_start: str,
    period_end: str,
    stats_json: str,
    backend: str = "deterministic",
    target_words: int = 1000,
) -> dict:
    import json

    from .tools_narrative import generate_narrative

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    stats = json.loads(stats_json) if stats_json else {}
    text = generate_narrative(
        category=category,
        period_label=period_label,
        period_start=start,
        period_end=end,
        stats=stats,
        target_words=target_words,
        backend=backend,
    )
    return {"narrative": text, "word_count": len(text.split())}


def _render_pdf_impl(
    category: str,
    granularity: str,
    period_label: str,
    period_start: str,
    period_end: str,
    narrative_text: str,
    chart_paths: list[str],
    output_dir: str,
) -> dict:
    from .tools_pdf import render_pdf

    start = date.fromisoformat(period_start)
    end = date.fromisoformat(period_end)
    paths = [Path(p) for p in (chart_paths or [])]
    pdf_path = render_pdf(
        category=category,
        granularity=granularity,
        period_label=period_label,
        period_start=start,
        period_end=end,
        narrative_text=narrative_text,
        chart_image_paths=paths,
        output_dir=Path(output_dir),
    )
    return {"pdf_path": str(pdf_path)}


build_charts_tool = StructuredTool.from_function(
    name="build_charts",
    description="Build Seaborn/Matplotlib charts for the period and save to output_dir. Requires stats from compute_stats.",
    func=_build_charts_impl,
)

generate_narrative_tool = StructuredTool.from_function(
    name="generate_narrative",
    description="Generate report narrative text from stats (and optional LLM). Returns narrative and word count.",
    func=_generate_narrative_impl,
)

render_pdf_tool = StructuredTool.from_function(
    name="render_pdf",
    description="Assemble and save the final PDF from narrative text and chart image paths.",
    func=_render_pdf_impl,
)


def get_report_tools_for_agent() -> list[StructuredTool]:
    """Return the list of LangChain tools for use by an LLM agent."""
    return [
        run_sql_tool,
        compute_stats_tool,
        build_charts_tool,
        generate_narrative_tool,
        render_pdf_tool,
    ]


__all__ = [
    "run_sql_tool_node",
    "compute_stats_tool_node",
    "build_charts_tool_node",
    "generate_narrative_tool_node",
    "render_pdf_tool_node",
    "run_sql_tool",
    "compute_stats_tool",
    "build_charts_tool",
    "generate_narrative_tool",
    "render_pdf_tool",
    "get_report_tools_for_agent",
]
