"""LangGraph implementation of the reporting workflow.

This module builds a detailed ``StateGraph`` around the reporting helpers in
``workflow_graph.py`` so that the full control flow (stages and periods) is
visible in LangGraph Studio.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from .report_tools import (
    build_charts_tool_node,
    compute_stats_tool_node,
    generate_narrative_tool_node,
    render_pdf_tool_node,
    run_sql_tool_node,
)
from .workflow_graph import (
    GRANULARITY_ORDER,
    ReportState,
    determine_stage,
    generate_periods,
    has_more_periods,
)


def _init_state(
    *,
    category: str,
    date_start: date,
    date_end: date,
    requested_granularities: list[str] | None = None,
    output_dir: Path | None = None,
    narrative_backend: str = "deterministic",
    llm_model: str | None = None,
) -> ReportState:
    """Construct the initial ``ReportState`` for the graph."""

    return {
        "category": category,
        "date_start": date_start,
        "date_end": date_end,
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


def init_state_node(state: ReportState) -> ReportState:
    """Graph entry node: normalise and initialise the state structure.

    This allows Studio callers to provide a partial state (e.g. only category
    and date range) while ensuring the internal fields are always present.
    """

    category = state.get("category")
    if not category:
        raise ValueError("Report graph requires 'category' in the state.")

    start_raw = state.get("date_start")
    end_raw = state.get("date_end")
    if start_raw is None or end_raw is None:
        raise ValueError(
            "Report graph requires 'date_start' and 'date_end' in the state."
        )

    if isinstance(start_raw, date):
        start = start_raw
    else:
        start = date.fromisoformat(str(start_raw))

    if isinstance(end_raw, date):
        end = end_raw
    else:
        end = date.fromisoformat(str(end_raw))

    requested_granularities = state.get("requested_granularities")
    if requested_granularities is not None:
        # Defensive copy and validation.
        requested_granularities = [
            g for g in requested_granularities if g in GRANULARITY_ORDER
        ]

    output_dir_raw = state.get("output_dir")
    if isinstance(output_dir_raw, Path):
        output_dir = output_dir_raw
    elif output_dir_raw is None:
        output_dir = None
    else:
        output_dir = Path(str(output_dir_raw))

    narrative_backend = state.get("narrative_backend") or "deterministic"
    llm_model = state.get("llm_model")

    return _init_state(
        category=str(category),
        date_start=start,
        date_end=end,
        requested_granularities=requested_granularities,
        output_dir=output_dir,
        narrative_backend=narrative_backend,
        llm_model=llm_model,
    )


def stage_decision(state: ReportState) -> str:
    """Decide whether to continue with another stage or end the workflow."""

    current_stage = state.get("current_stage")
    return "end" if current_stage is None else "continue"


def period_decision(state: ReportState) -> str:
    """Decide whether there are more periods to process in the current stage."""

    return "more" if has_more_periods(state) else "no_more"


def build_report_graph() -> Any:
    """Build and compile the LangGraph ``StateGraph`` for reports.

    Nodes:
    - ``init_state``: normalise and populate the initial ``ReportState``.
    - ``determine_stage``: choose or advance the current granularity.
    - ``generate_periods``: populate the periods for the chosen stage.
    - Tool nodes (one per reporting step): ``run_sql``, ``compute_stats``,
      ``build_charts``, ``generate_narrative``, ``render_pdf``. Each reads
      from state and returns a partial state update.

    Control flow:
    - ``init_state`` → ``determine_stage``
    - From ``determine_stage``: if no stage → ``END``; else → ``generate_periods``
    - From ``generate_periods``: if no periods → ``determine_stage``;
      else → ``run_sql`` (start of tool chain)
    - Tool chain: ``run_sql`` → ``compute_stats`` → ``build_charts`` →
      ``generate_narrative`` → ``render_pdf``
    - From ``render_pdf``: if more periods → ``run_sql``; else → ``determine_stage``
    """

    graph = StateGraph(ReportState)

    graph.add_node("init_state", init_state_node)
    graph.add_node("determine_stage", determine_stage)
    graph.add_node("generate_periods", generate_periods)
    graph.add_node("run_sql", run_sql_tool_node)
    graph.add_node("compute_stats", compute_stats_tool_node)
    graph.add_node("build_charts", build_charts_tool_node)
    graph.add_node("generate_narrative", generate_narrative_tool_node)
    graph.add_node("render_pdf", render_pdf_tool_node)

    graph.set_entry_point("init_state")
    graph.add_edge("init_state", "determine_stage")

    graph.add_conditional_edges(
        "determine_stage",
        stage_decision,
        {"end": END, "continue": "generate_periods"},
    )

    graph.add_conditional_edges(
        "generate_periods",
        period_decision,
        {
            "more": "run_sql",
            "no_more": "determine_stage",
        },
    )

    graph.add_edge("run_sql", "compute_stats")
    graph.add_edge("compute_stats", "build_charts")
    graph.add_edge("build_charts", "generate_narrative")
    graph.add_edge("generate_narrative", "render_pdf")

    graph.add_conditional_edges(
        "render_pdf",
        period_decision,
        {
            "more": "run_sql",
            "no_more": "determine_stage",
        },
    )

    return graph.compile()


__all__ = ["build_report_graph"]
