"""
Analytics helpers for the reporting workflow.

These helpers wrap the lower-level utilities in `data_access` and the
category-specific report modules so they can be called from a generic
workflow or graph.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd

from . import data_access
from .customer_analytics_report import CustomerAnalyticsReport
from .financial_margin_report import FinancialMarginReport
from .forecasting_planning_report import ForecastingPlanningReport
from .inventory_operations_report import InventoryOperationsReport
from .product_category_report import ProductCategoryReport
from .promotions_pricing_report import PromotionsPricingReport
from .report_base import ReportContext
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


def aggregate_metrics(
    df: pd.DataFrame,
    group_by_cols: list[str],
    metrics: Iterable[data_access.Metric],
) -> pd.DataFrame:
    """
    Aggregate transaction-level data into higher-level metrics.

    This is a thin wrapper around `data_access.aggregate_transactions`.
    """

    return data_access.aggregate_transactions(df, group_by_cols, metrics)


def compute_period_stats(
    category: str,
    period_label: str,
    period_start: date,
    period_end: date,
) -> dict[str, object]:
    """
    Compute category-specific KPIs and summary statistics for a period.

    This helper delegates to the corresponding report implementation so
    that the same business logic is reused between the batch scripts and
    the workflow-oriented reporting.
    """

    report_cls = CATEGORY_REPORT_MAP.get(category)
    if report_cls is None:
        raise ValueError(f"Unsupported category: {category}")

    report = report_cls()
    ctx = ReportContext(label=period_label, start=period_start, end=period_end)
    return report.compute_period_stats(ctx)
