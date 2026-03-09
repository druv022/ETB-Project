"""
Forecasting and planning report.

Provides simple time-series forecasts for revenue and units using
moving-average style baselines. This is intentionally lightweight and
intended for illustrative purposes rather than production forecasting.
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
class ForecastingPlanningReport(BaseReport):
    """Concrete implementation of the forecasting & planning report."""

    name: str = "forecasting_planning"
    category: str = "forecasting and planning"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        # For forecasting we look at history up to the end of the current period.
        history_df = data_access.load_transactions(
            end_date=ctx.end.isoformat(),
            config=self._db_config,
        )
        if history_df.empty:
            return {"history": pd.DataFrame()}

        history_df = history_df.copy()
        history_df["Transaction_Date"] = pd.to_datetime(history_df["Transaction_Date"])
        hist_by_day = (
            history_df.groupby("Transaction_Date")
            .agg(
                revenue=("Net_Sales_Value", "sum"),
                units=("Quantity_Sold", "sum"),
            )
            .reset_index()
        )
        hist_by_day["revenue_ma_7"] = (
            hist_by_day["revenue"].rolling(window=7, min_periods=1).mean()
        )

        return {"history": hist_by_day}

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []
        hist_by_day = stats["history"]

        if isinstance(hist_by_day, pd.DataFrame) and not hist_by_day.empty:
            fig, ax = plt.subplots(figsize=(8, 4))
            sns.lineplot(
                data=hist_by_day,
                x="Transaction_Date",
                y="revenue",
                label="Actual revenue",
                ax=ax,
            )
            sns.lineplot(
                data=hist_by_day,
                x="Transaction_Date",
                y="revenue_ma_7",
                label="7-day moving average",
                ax=ax,
            )
            ax.set_title(f"Revenue history and simple forecast baseline – {ctx.label}")
            ax.set_xlabel("Date")
            ax.set_ylabel("Revenue")
            figures.append(fig)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        hist_by_day = stats["history"]
        if not isinstance(hist_by_day, pd.DataFrame) or hist_by_day.empty:
            return (
                f"No transaction history is available prior to or during {ctx.label}, "
                "so a time-series based forecast cannot be produced."
            )

        last_row = hist_by_day.iloc[-1]
        latest_revenue = float(last_row["revenue"])
        ma_7 = float(last_row["revenue_ma_7"])

        narrative_parts = [
            (
                f"The forecasting view for {ctx.label} is based on observed daily "
                "revenue up to the end of the period. The latest day in the series "
                f"shows revenue of {latest_revenue:,.2f}, compared with a seven-day "
                f"moving average of {ma_7:,.2f}."
            ),
            (
                "Although a simple moving average is a deliberately conservative "
                "baseline, it provides an intuitive starting point for near-term "
                "planning: if actuals consistently exceed the baseline the plan may "
                "need to be revised upward, while sustained under-performance may "
                "signal demand softness that should be reflected in inventory and "
                "labour plans."
            ),
        ]

        return "\n\n".join(narrative_parts)
