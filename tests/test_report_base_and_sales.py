from datetime import date
from pathlib import Path

from tools.data_generation.report_generation.report_base import (
    BaseReport,
    ReportContext,
)
from tools.data_generation.report_generation.sales_performance_report import (
    SalesPerformanceReport,
)


def test_ensure_target_word_count_expands_text() -> None:
    short_text = "This is short."
    result = BaseReport._ensure_target_word_count(short_text, target_words=50)
    assert len(result.split()) >= 50


def test_get_periods_monthly() -> None:
    report = SalesPerformanceReport()
    periods = report.get_periods(
        "monthly",
        start=date(2020, 1, 1),
        end=date(2020, 3, 31),
    )
    labels = [p.label for p in periods]
    assert labels == ["2020-01", "2020-02", "2020-03"]


def test_generate_for_period_works_with_empty_data(tmp_path: Path) -> None:
    ctx = ReportContext(label="test", start=date(2020, 1, 1), end=date(2020, 1, 7))
    report = SalesPerformanceReport()
    # This will rely on an empty database and should still produce a PDF file.
    output_path = report.generate_for_period(
        ctx,
        granularity="weekly",
        output_dir=tmp_path,
    )
    assert output_path.exists()
