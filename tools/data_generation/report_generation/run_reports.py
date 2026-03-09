"""
CLI entrypoint for generating PDF reports from the transaction database.

Example usage from the project root:

    PYTHONPATH=. python tools/data_generation/report_generation/run_reports.py \\
        --category sales \\
        --granularity monthly \\
        --start-date 2020-01-01 \\
        --end-date 2020-03-31 \\
        --output-dir reports/
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .customer_analytics_report import CustomerAnalyticsReport
from .financial_margin_report import FinancialMarginReport
from .forecasting_planning_report import ForecastingPlanningReport
from .inventory_operations_report import InventoryOperationsReport
from .product_category_report import ProductCategoryReport
from .promotions_pricing_report import PromotionsPricingReport
from .report_base import BaseReport
from .risk_fraud_report import RiskFraudReport
from .sales_performance_report import SalesPerformanceReport

REPORT_TYPES: dict[str, type[BaseReport]] = {
    "sales": SalesPerformanceReport,
    "product_category": ProductCategoryReport,
    "customer": CustomerAnalyticsReport,
    "promotions": PromotionsPricingReport,
    "inventory": InventoryOperationsReport,
    "financial": FinancialMarginReport,
    "risk": RiskFraudReport,
    "forecasting": ForecastingPlanningReport,
}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate PDF reports from transactions."
    )
    parser.add_argument(
        "--category",
        choices=list(REPORT_TYPES.keys()),
        required=True,
        help="Report category to generate.",
    )
    parser.add_argument(
        "--granularity",
        choices=["weekly", "biweekly", "monthly", "quarterly", "semiannual", "yearly"],
        required=True,
        help="Time granularity for the report.",
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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date)

    report_cls = REPORT_TYPES[args.category]
    report = report_cls()

    contexts = report.get_periods(args.granularity, start, end)
    output_dir = Path(args.output_dir)

    for ctx in contexts:
        report.generate_for_period(ctx, args.granularity, output_dir)


if __name__ == "__main__":
    main()
