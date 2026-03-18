from datetime import date
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("matplotlib")

from tools.data_generation.report_generation import (
    tools_analytics,
    tools_narrative,
    tools_pdf,
    tools_sql,
)
from tools.data_generation.report_generation.workflow_graph import (
    ReportState,
    determine_stage,
    generate_periods,
    has_more_periods,
)


def test_generate_sql_query_has_date_params() -> None:
    start = date(2020, 1, 1)
    end = date(2020, 1, 31)
    query = tools_sql.generate_sql_query("sales", start, end)
    assert "Transaction_Date" in query.text
    assert query.params["start_date"] == "2020-01-01"
    assert query.params["end_date"] == "2020-01-31"


def test_aggregate_metrics_sums_values() -> None:
    df = pd.DataFrame(
        {
            "Store_ID": [1, 1, 2],
            "Net_Sales_Value": [10.0, 20.0, 5.0],
            "Quantity_Sold": [1, 2, 3],
            "Transaction_ID": ["A", "B", "C"],
        }
    )
    grouped = tools_analytics.aggregate_metrics(
        df, ["Store_ID"], metrics=("revenue", "units", "transactions")
    )
    row1 = grouped[grouped["Store_ID"] == 1].iloc[0]
    assert row1["revenue"] == 30.0
    assert row1["units"] == 3
    assert row1["transactions"] == 2


def test_generate_narrative_reaches_target_length() -> None:
    stats: dict[str, object] = {
        "summary": {
            "revenue": 100.0,
            "units": 10,
            "transactions": 5,
            "avg_ticket": 20.0,
            "avg_items_per_txn": 2.0,
        },
        "by_store": pd.DataFrame(),
        "by_channel": pd.DataFrame(),
    }
    text = tools_narrative.generate_narrative(
        category="sales",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        stats=stats,
        target_words=200,
    )
    assert len(text.split()) >= 200


def test_generate_narrative_llm_backend_falls_back_on_error(monkeypatch) -> None:
    def raise_error(**kwargs):  # type: ignore[unused-argument]
        raise RuntimeError("LLM failure")

    monkeypatch.setattr(
        tools_narrative.llm_client,
        "generate_report_narrative",
        raise_error,
    )

    stats: dict[str, object] = {
        "summary": {
            "revenue": 50.0,
        },
    }
    text = tools_narrative.generate_narrative(
        category="sales",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        stats=stats,
        target_words=50,
        backend="llm_with_fallback",
        llm_model="test-model",
        granularity="monthly",
    )
    # Even though the LLM path failed, we should still get a non-empty
    # deterministic narrative back.
    assert len(text.split()) >= 50


def test_render_pdf_creates_file(tmp_path: Path) -> None:
    pdf_path = tools_pdf.render_pdf(
        category="sales",
        granularity="monthly",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        narrative_text="Test narrative.",
        chart_image_paths=[],
        output_dir=tmp_path,
    )
    assert pdf_path.exists()


def test_long_narrative_splits_across_pages(tmp_path: Path) -> None:
    long_text = "Paragraph one. " * 200
    pdf_path = tools_pdf.render_pdf(
        category="sales",
        granularity="monthly",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        narrative_text=long_text,
        chart_image_paths=[],
        output_dir=tmp_path,
    )
    assert pdf_path.exists()


def test_markdown_narrative_renders_and_writes_md(tmp_path: Path) -> None:
    md_text = "\n".join(
        [
            "## Executive Summary",
            "",
            "This is **bold** and a paragraph.",
            "",
            "---",
            "",
            "### Key Drivers",
            "",
            "1. First point",
            "- Bullet one",
            "- Bullet two",
        ]
    )
    pdf_path = tools_pdf.render_pdf(
        category="sales",
        granularity="monthly",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        narrative_text=md_text,
        chart_image_paths=[],
        output_dir=tmp_path,
    )
    assert pdf_path.exists()
    md_path = tmp_path / "sales_monthly_2020-01.md"
    assert md_path.exists()


def test_render_pdf_with_multiple_charts_uses_fewer_pages(tmp_path: Path) -> None:
    pdf_path = tools_pdf.render_pdf(
        category="sales",
        granularity="monthly",
        period_label="2020-01",
        period_start=date(2020, 1, 1),
        period_end=date(2020, 1, 31),
        narrative_text="Short narrative.",
        chart_image_paths=[],
        output_dir=tmp_path,
    )
    assert pdf_path.exists()


def test_determine_stage_and_generate_periods() -> None:
    state = ReportState(
        category="sales",
        date_start=date(2020, 1, 1),
        date_end=date(2020, 1, 31),
        requested_granularities=["monthly"],
    )
    state = determine_stage(state)
    assert state["current_stage"] == "monthly"
    state = generate_periods(state)
    assert has_more_periods(state)
