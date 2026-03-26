"""
CLI entrypoint for the workflow-based report generation.

This script is intentionally independent from the main application in
`src/`. It operates entirely on the synthetic transaction database and
the reporting utilities under `tools/data_generation/report_generation/`.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from tools.data_generation.report_generation.report_langgraph import build_report_graph
from tools.data_generation.report_generation.workflow_graph import ReportState

ALL_CATEGORIES = [
    "sales",
    "product_category",
    "customer",
    "promotions",
    "inventory",
    "financial",
    "risk",
    "forecasting",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the workflow-based retail reporting pipeline."
    )
    parser.add_argument(
        "--category",
        required=False,
        choices=ALL_CATEGORIES,
        help=(
            "Report category to generate. If omitted, the workflow runs all categories."
        ),
    )
    parser.add_argument(
        "--granularities",
        nargs="+",
        choices=["weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly"],
        help="One or more granularities to run (default: all in order).",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD) of the reporting window.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD) of the reporting window.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="tools/data_generation/report_generation/output",
        help="Directory where PDF files will be written.",
    )
    parser.add_argument(
        "--narrative-backend",
        choices=["deterministic", "llm", "llm_with_fallback"],
        default="deterministic",
        help=(
            "Backend to use for narrative generation. "
            "Use 'deterministic' to rely on built-in report logic or 'llm' / "
            "'llm_with_fallback' to call a reasoning LLM (requires API configuration)."
        ),
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        help=(
            "Optional model identifier for the LLM backend. "
            "If omitted, a project-wide default will be used."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)
    output_dir = Path(args.output_dir)
    categories = [args.category] if args.category is not None else ALL_CATEGORIES
    graph = build_report_graph()

    for category in categories:
        print(f"Running workflow for category: {category}")

        initial_state: ReportState = {
            "category": category,
            "date_start": start,
            "date_end": end,
            "requested_granularities": args.granularities,
            "current_stage": None,
            "periods": [],
            "current_period_index": 0,
            "generated_reports": [],
            "output_dir": output_dir,
            "narrative_backend": args.narrative_backend,
            "llm_model": args.llm_model,
        }

        state = graph.invoke(initial_state)

        print("Generated reports:")
        for item in state["generated_reports"]:
            print(
                f"- {item['stage']} {item['period_label']}: {item['start']} → "
                f"{item['end']} → {item['pdf_path']}"
            )


if __name__ == "__main__":
    main()
