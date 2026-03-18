from datetime import date

import pandas as pd
import pytest

pytest.importorskip("langchain_core")

from tools.data_generation.report_generation.llm_client import (
    generate_report_narrative,
    summarise_stats_for_llm,
)


def test_summarise_stats_for_llm_handles_scalars_and_pandas() -> None:
    df = pd.DataFrame(
        {
            "Customer_Type": ["New", "Returning"],
            "revenue": [100.0, 200.0],
        }
    )
    series = pd.Series({"A": 1.0, "B": 2.0})
    stats: dict[str, object] = {
        "summary": {"total_revenue": 300.0},
        "by_customer_type": df,
        "spend_per_customer": series,
    }

    result = summarise_stats_for_llm(stats, max_rows=1)

    assert "summary" in result
    assert result["summary"]["total_revenue"] == 300.0
    assert isinstance(result["by_customer_type"], list)
    assert len(result["by_customer_type"]) == 1
    assert isinstance(result["spend_per_customer"], dict)
    assert "A" in result["spend_per_customer"]


def test_generate_report_narrative_raises_for_unsupported_backend() -> None:
    stats: dict[str, object] = {"summary": {"revenue": 123.0}}

    try:
        generate_report_narrative(
            category="sales",
            period_label="2020-01",
            period_start=date(2020, 1, 1),
            period_end=date(2020, 1, 31),
            granularity="monthly",
            stats=stats,
            baseline_narrative="Baseline text",
            target_words=100,
            backend="unknown-backend",
            model=None,
        )
    except ValueError as exc:
        assert "Unsupported LLM backend" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported backend")
