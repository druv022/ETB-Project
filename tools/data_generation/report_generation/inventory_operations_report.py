"""
Inventory and operations report.

Uses transaction timestamps and store information to approximate demand
patterns that are useful for staffing and replenishment decisions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .report_base import BaseReport, ReportContext


class InventoryOperationsReport(BaseReport):
    """Concrete implementation of the inventory & operations report."""

    name: str = "inventory_operations"
    category: str = "inventory and operations"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "by_hour_dow": pd.DataFrame(),
            }

        df = df.copy()
        df["Transaction_DateTime"] = pd.to_datetime(
            df["Transaction_Date"] + " " + df["Transaction_Time"]
        )
        df["hour"] = df["Transaction_DateTime"].dt.hour
        df["dow"] = df["Transaction_DateTime"].dt.dayofweek

        by_hour_dow = (
            df.groupby(["dow", "hour"])
            .agg(transactions=("Transaction_ID", "nunique"))
            .reset_index()
        )

        return {
            "by_hour_dow": by_hour_dow,
        }

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []
        by_hour_dow = stats["by_hour_dow"]

        if isinstance(by_hour_dow, pd.DataFrame) and not by_hour_dow.empty:
            pivot = by_hour_dow.pivot(
                index="dow", columns="hour", values="transactions"
            )
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.heatmap(pivot, cmap="Blues", ax=ax1)
            ax1.set_title(f"Transactions heatmap by day-of-week and hour – {ctx.label}")
            ax1.set_xlabel("Hour of day")
            ax1.set_ylabel("Day of week (0=Mon)")
            figures.append(fig1)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        by_hour_dow = stats["by_hour_dow"]
        if not isinstance(by_hour_dow, pd.DataFrame) or by_hour_dow.empty:
            return (
                f"No transaction timestamp data is available for the period "
                f"{ctx.label}, so this report does not surface any operational "
                "patterns that could inform staffing or replenishment."
            )

        narrative_parts = [
            (
                f"The heatmap of transactions by hour of day and day of week for "
                f"{ctx.label} highlights when stores experience their heaviest load. "
                "These peaks are the natural candidates for enhanced staffing and "
                "more aggressive on-shelf availability checks."
            ),
            (
                "In a mature operational cadence, store teams use this type of view "
                "to set labour schedules, define delivery windows, and time key tasks "
                "such as planogram resets to avoid clashing with peak customer demand."
            ),
        ]

        return "\n\n".join(narrative_parts)
