"""
Narrative generation helpers for the reporting workflow.

For now these helpers reuse the deterministic narrative logic from the
category-specific report modules and ensure that each narrative reaches
approximately a target word count. They are structured so that a true
LLM-backed implementation can be dropped in later if desired.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from . import llm_client
from .customer_analytics_report import CustomerAnalyticsReport
from .financial_margin_report import FinancialMarginReport
from .forecasting_planning_report import ForecastingPlanningReport
from .inventory_operations_report import InventoryOperationsReport
from .product_category_report import ProductCategoryReport
from .promotions_pricing_report import PromotionsPricingReport
from .report_base import BaseReport, ReportContext
from .risk_fraud_report import RiskFraudReport
from .sales_performance_report import SalesPerformanceReport

CATEGORY_REPORT_MAP = {
    "sales": SalesPerformanceReport,
    "product_category": ProductCategoryReport,
    "customer": CustomerAnalyticsReport,
    "promotions": PromotionsPricingReport,
    "inventory": InventoryOperationsReport,
    "financial": FinancialMarginReport,
    "risk": RiskFraudReport,
    "forecasting": ForecastingPlanningReport,
}


def no_data_narrative(period_label: str, period_start: date, period_end: date) -> str:
    """
    Standard narrative used when no transactions are returned for a period.

    This helper is shared between the workflow graph and LangGraph tool nodes
    so the \"no data\" wording is consistent across all reporting entrypoints.
    """

    return (
        f"For the period {period_label} ({period_start} to {period_end}), "
        "no transactions were returned from the database. This pdf is a "
        "placeholder indicating an absence of data for the selected "
        "combination of category, granularity, and dates."
    )


def generate_narrative(
    category: str,
    period_label: str,
    period_start: date,
    period_end: date,
    stats: Mapping[str, object],
    target_words: int = 1000,
    backend: str = "deterministic",
    llm_model: str | None = None,
    granularity: str | None = None,
) -> str:
    """
    Generate a narrative for a given category and period.

    The implementation delegates to the existing report classes for the
    core narrative content and then ensures that the result is expanded
    to approximately `target_words` using the helper from `BaseReport`.
    """

    report_cls = CATEGORY_REPORT_MAP.get(category)
    if report_cls is None:
        raise ValueError(f"Unsupported category: {category}")

    report: BaseReport = report_cls()
    ctx = ReportContext(label=period_label, start=period_start, end=period_end)
    base_text = report.build_period_narrative(ctx, stats)

    # Preserve the existing deterministic behaviour by default.
    if backend == "deterministic":
        return BaseReport._ensure_target_word_count(
            base_text, target_words=target_words
        )

    # LLM-backed path with safe fallback to deterministic narrative.
    try:
        narrative = llm_client.generate_report_narrative(
            category=category,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            granularity=granularity,
            stats=stats,
            baseline_narrative=base_text,
            target_words=target_words,
            model=llm_model,
        )
    except Exception:
        # On any failure, fall back to the deterministic narrative so that
        # batch runs still complete successfully.
        return BaseReport._ensure_target_word_count(
            base_text, target_words=target_words
        )

    if not narrative.strip():
        return BaseReport._ensure_target_word_count(
            base_text, target_words=target_words
        )

    # If the LLM returns a noticeably short narrative, extend it using the
    # same helper as the deterministic path to keep PDFs reasonably sized.
    if len(narrative.split()) < max(target_words // 2, 1):
        return BaseReport._ensure_target_word_count(
            narrative, target_words=target_words
        )

    return narrative
