"""
Chart-building helpers for the reporting workflow.

These utilities adapt the chart construction logic from the
category-specific report modules so that the workflow can request
charts in a consistent way and receive paths to saved image files.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path

import matplotlib.pyplot as plt

from .chart_style import apply_executive_theme
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


def build_charts(
    category: str,
    period_label: str,
    period_start: date,
    period_end: date,
    stats: Mapping[str, object],
    output_dir: Path,
) -> list[Path]:
    """
    Build Seaborn/Matplotlib charts for a given period and save them to disk.

    Returns a list of paths to the generated image files.
    """

    # Ensure a consistent executive-style theme for all figures.
    apply_executive_theme()

    report_cls = CATEGORY_REPORT_MAP.get(category)
    if report_cls is None:
        raise ValueError(f"Unsupported category: {category}")

    report = report_cls()
    ctx = ReportContext(label=period_label, start=period_start, end=period_end)

    figures: Sequence[plt.Figure] = report.build_period_figures(ctx, stats)
    if not figures:
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for idx, fig in enumerate(figures, start=1):
        filename = f"{category}_{period_label}_chart_{idx}.png"
        img_path = output_dir / filename
        fig.savefig(img_path, bbox_inches="tight")
        paths.append(img_path)
        plt.close(fig)

    return paths
