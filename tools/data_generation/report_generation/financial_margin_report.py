"""
Financial and margin report.

Focuses on gross vs net sales, discount impact, and tax collections as
observable from the transaction dataset.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt

from .report_base import BaseReport, ReportContext


class FinancialMarginReport(BaseReport):
    """Concrete implementation of the financial & margin report."""

    name: str = "financial_margin"
    category: str = "financial and margin"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {"summary": {}}

        gross = float(df["Gross_Sales_Value"].sum())
        discounts = float(df["Discount_Amount"].sum())
        net = float(df["Net_Sales_Value"].sum())
        tax = float(df["Tax_amount"].sum())

        summary = {
            "gross": gross,
            "discounts": discounts,
            "net": net,
            "tax": tax,
        }

        return {"summary": summary}

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        summary = stats["summary"]
        figures: list[plt.Figure] = []

        if not summary:
            return figures

        steps = ["Gross sales", "Discounts", "Net sales", "Tax collected"]
        values = [
            summary["gross"],
            -summary["discounts"],
            summary["net"],
            summary["tax"],
        ]

        fig, ax = plt.subplots(figsize=(6, 4))
        running = 0.0
        for idx, val in enumerate(values):
            start = running
            running += val
            ax.bar(idx, running - start, bottom=start, color="C0")
            ax.text(
                idx,
                running,
                f"{running:,.0f}",
                ha="center",
                va="bottom",
                fontsize=8,
            )

        ax.set_xticks(list(range(len(steps))))
        ax.set_xticklabels(steps, rotation=20)
        ax.set_title(f"Financial waterfall – {ctx.label}")
        ax.set_ylabel("Value")
        figures.append(fig)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        summary = stats["summary"]
        if not summary:
            return (
                f"For {ctx.label} there is no financial data in the transaction "
                "table, so the gross, net, discount and tax components cannot be "
                "analyzed."
            )

        gross = summary["gross"]
        discounts = summary["discounts"]
        net = summary["net"]
        tax = summary["tax"]

        narrative_parts = [
            (
                f"From a financial standpoint, transactions in {ctx.label} generated "
                f"{gross:,.2f} in gross sales value before discounts. Across all "
                f"orders, discounts worth {discounts:,.2f} were applied, resulting in "
                f"net sales of {net:,.2f}. Tax collected on these net amounts totalled "
                f"{tax:,.2f}."
            ),
            (
                "This simple decomposition clarifies how much of the top-line demand "
                "is being traded away through price-based activity and how that flows "
                "through to net revenue and statutory obligations. It is a useful "
                "starting point for more sophisticated margin analysis that would "
                "layer in cost of goods sold and operating expenses."
            ),
        ]

        return "\n\n".join(narrative_parts)
