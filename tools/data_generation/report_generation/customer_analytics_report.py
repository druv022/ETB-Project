"""
Customer analytics report.

Uses transaction-level customer identifiers and types to approximate
engagement, new vs returning mix, and spend distributions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .report_base import BaseReport, ReportContext


class CustomerAnalyticsReport(BaseReport):
    """Concrete implementation of the customer analytics report."""

    name: str = "customer_analytics"
    category: str = "customer analytics"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "summary": {},
                "by_customer_type": pd.DataFrame(),
                "spend_per_customer": pd.Series(dtype="float"),
            }

        spend_per_customer = (
            df.groupby("Customer_ID")["Net_Sales_Value"].sum().rename("spend")
        )

        by_customer_type = (
            df.groupby("Customer_Type")
            .agg(
                revenue=("Net_Sales_Value", "sum"),
                transactions=("Transaction_ID", "nunique"),
            )
            .reset_index()
        )

        summary = {
            "active_customers": int(spend_per_customer.shape[0]),
            "total_revenue": float(df["Net_Sales_Value"].sum()),
        }

        return {
            "summary": summary,
            "by_customer_type": by_customer_type,
            "spend_per_customer": spend_per_customer,
        }

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []
        by_type = stats["by_customer_type"]
        spend_series = stats["spend_per_customer"]

        if isinstance(by_type, pd.DataFrame) and not by_type.empty:
            fig1, ax1 = plt.subplots(figsize=(6, 4))
            sns.barplot(
                data=by_type,
                x="Customer_Type",
                y="revenue",
                ax=ax1,
            )
            ax1.set_title(f"Revenue by customer type – {ctx.label}")
            ax1.set_xlabel("Customer type")
            ax1.set_ylabel("Revenue")
            ax1.tick_params(axis="x", rotation=30)
            figures.append(fig1)

        if isinstance(spend_series, pd.Series) and not spend_series.empty:
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            sns.histplot(spend_series, bins=30, ax=ax2)
            ax2.set_title(f"Distribution of spend per customer – {ctx.label}")
            ax2.set_xlabel("Spend per customer")
            ax2.set_ylabel("Customer count")
            figures.append(fig2)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        summary = stats["summary"]
        if not summary:
            return (
                f"For the period {ctx.label} there is no observable customer "
                "activity in the transactional dataset. That makes it difficult "
                "to draw conclusions about customer engagement or loyalty."
            )

        active_customers = summary["active_customers"]
        total_revenue = summary["total_revenue"]
        avg_revenue_per_customer = (
            total_revenue / active_customers if active_customers > 0 else 0.0
        )

        narrative_parts = [
            (
                f"Across the period {ctx.label}, approximately {active_customers:,} "
                f"distinct customers generated {total_revenue:,.2f} in net sales, "
                f"equating to an average of {avg_revenue_per_customer:,.2f} per "
                "active customer."
            ),
            (
                "Customer analytics at this level helps quantify how broad and deep "
                "the customer base is. A large number of customers each spending a "
                "modest amount typically indicates healthy reach, while a small set "
                "of very high-value customers may point to concentration risk."
            ),
        ]

        return "\n\n".join(narrative_parts)
