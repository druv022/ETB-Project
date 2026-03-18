"""
Risk, fraud and controls report.

Identifies unusual transaction patterns – such as very high-value
transactions – that could warrant additional review.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .report_base import BaseReport, ReportContext


class RiskFraudReport(BaseReport):
    """Concrete implementation of the risk, fraud & controls report."""

    name: str = "risk_fraud"
    category: str = "risk and fraud"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "high_value": pd.DataFrame(),
            }

        txn_values = (
            df.groupby("Transaction_ID")["Total_Value"].sum().rename("txn_value")
        )
        threshold = txn_values.quantile(0.99) if not txn_values.empty else 0.0
        high_value = txn_values[txn_values >= threshold].reset_index()

        return {
            "threshold": float(threshold),
            "high_value": high_value,
        }

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []
        high_value = stats["high_value"]

        if isinstance(high_value, pd.DataFrame) and not high_value.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            sns.histplot(high_value["txn_value"], bins=20, ax=ax)
            ax.set_title(f"Distribution of top 1% transaction values – {ctx.label}")
            ax.set_xlabel("Transaction value")
            ax.set_ylabel("Count")
            figures.append(fig)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        threshold = stats.get("threshold", 0.0)
        high_value = stats["high_value"]
        if not isinstance(high_value, pd.DataFrame) or high_value.empty:
            return (
                f"For {ctx.label} the data does not contain a meaningful tail of very "
                "high-value transactions based on the simple percentile rule of "
                "thumb applied here, so no specific risk hotspots are highlighted."
            )

        narrative_parts = [
            (
                f"In {ctx.label} the top 1% of transactions, defined by a simple "
                f"value threshold of approximately {threshold:,.2f}, represent a "
                "small but financially material slice of activity. These high-value "
                "purchases are generally low in volume but important to monitor."
            ),
            (
                "While the synthetic data does not encode explicit fraud or refund "
                "signals, in a production setting this tail of large transactions "
                "would be cross-referenced with payment method, store, channel, and "
                "customer identifiers to flag patterns that deviate from local norms."
            ),
        ]

        return "\n\n".join(narrative_parts)
