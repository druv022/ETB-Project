"""
Sales performance report.

Provides PDF reports with KPIs and charts for overall sales health
across different time granularities (weekly, bi-weekly, monthly,
quarterly, semi-annual, yearly).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import data_access
from .report_base import BaseReport, ReportContext


@dataclass
class SalesPerformanceReport(BaseReport):
    """Concrete implementation of the sales performance report."""

    name: str = "sales_performance"
    category: str = "sales performance"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "summary": {},
                "by_store": pd.DataFrame(),
                "by_channel": pd.DataFrame(),
            }

        summary = {
            "revenue": float(df["Net_Sales_Value"].sum()),
            "units": int(df["Quantity_Sold"].sum()),
            "transactions": int(df["Transaction_ID"].nunique()),
        }
        summary["avg_ticket"] = (
            summary["revenue"] / summary["transactions"]
            if summary["transactions"] > 0
            else 0.0
        )
        summary["avg_items_per_txn"] = (
            summary["units"] / summary["transactions"]
            if summary["transactions"] > 0
            else 0.0
        )

        by_store = data_access.aggregate_transactions(
            df, ["Store_ID", "Store_Region"], ["revenue", "units"]
        )
        by_channel = data_access.aggregate_transactions(
            df, ["Order_Channel"], ["revenue", "transactions"]
        )

        return {
            "summary": summary,
            "by_store": by_store,
            "by_channel": by_channel,
        }

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []
        by_store = stats["by_store"]
        by_channel = stats["by_channel"]

        if isinstance(by_store, pd.DataFrame) and not by_store.empty:
            top_stores = by_store.sort_values("revenue", ascending=False).head(10)
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.barplot(
                data=top_stores,
                x="Store_ID",
                y="revenue",
                hue="Store_Region",
                ax=ax1,
            )
            ax1.set_title(f"Top 10 stores by revenue – {ctx.label}")
            ax1.set_xlabel("Store ID")
            ax1.set_ylabel("Revenue")
            figures.append(fig1)

        if isinstance(by_channel, pd.DataFrame) and not by_channel.empty:
            fig2, ax2 = plt.subplots(figsize=(6, 4))
            sns.barplot(
                data=by_channel,
                x="Order_Channel",
                y="revenue",
                ax=ax2,
            )
            ax2.set_title(f"Revenue by channel – {ctx.label}")
            ax2.set_xlabel("Channel")
            ax2.set_ylabel("Revenue")
            figures.append(fig2)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        summary: dict[str, object] = stats["summary"]  # type: ignore[assignment]
        if not summary:
            return (
                f"For the period {ctx.label} ({ctx.start} to {ctx.end}) no transactions "
                "were recorded in the dataset. This report therefore focuses on the "
                "absence of activity, which may indicate a data ingestion issue or a "
                "planned outage rather than typical business performance."
            )

        revenue = summary["revenue"]
        units = summary["units"]
        txns = summary["transactions"]
        avg_ticket = summary["avg_ticket"]
        avg_items = summary["avg_items_per_txn"]

        narrative_parts = [
            (
                f"During the period {ctx.label} (from {ctx.start} to {ctx.end}), the "
                f"business generated total net sales of approximately {revenue:,.2f} "
                f"across {txns:,} customer transactions. In aggregate this represents "
                f"{units:,} individual units sold, giving an average basket value of "
                f"{avg_ticket:,.2f} per transaction and an average of "
                f"{avg_items:,.2f} items per basket."
            ),
            (
                "From an operational perspective these figures provide a concise view "
                "of top-line performance: revenue tracks the overall health of the "
                "business, while transaction count and basket composition highlight "
                "engagement and ticket-building effectiveness at the point of sale."
            ),
        ]

        return "\n\n".join(narrative_parts)
