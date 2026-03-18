"""
Promotions and pricing report.

Leverages discount information in the transaction data to examine the
penetration and impact of promotional activity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .report_base import BaseReport, ReportContext


class PromotionsPricingReport(BaseReport):
    """Concrete implementation of the promotions & pricing report."""

    name: str = "promotions_pricing"
    category: str = "promotions and pricing"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "summary": {},
                "discounted": pd.DataFrame(),
                "by_category": pd.DataFrame(),
            }

        df = df.copy()
        df["is_discounted"] = df["Discount_%"] > 0

        total_units = int(df["Quantity_Sold"].sum())
        discounted_units = int(df.loc[df["is_discounted"], "Quantity_Sold"].sum())
        total_revenue = float(df["Net_Sales_Value"].sum())
        discounted_revenue = float(df.loc[df["is_discounted"], "Net_Sales_Value"].sum())

        summary = {
            "promo_unit_share": (
                (discounted_units / total_units * 100) if total_units > 0 else 0.0
            ),
            "promo_revenue_share": (
                (discounted_revenue / total_revenue * 100) if total_revenue > 0 else 0.0
            ),
        }

        by_category = (
            df.groupby(["Category", "is_discounted"])
            .agg(
                revenue=("Net_Sales_Value", "sum"),
                units=("Quantity_Sold", "sum"),
            )
            .reset_index()
        )

        return {
            "summary": summary,
            "by_category": by_category,
        }

    def build_period_figures(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> Sequence[plt.Figure]:
        figures: list[plt.Figure] = []

        by_category = stats["by_category"]
        if isinstance(by_category, pd.DataFrame) and not by_category.empty:
            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.barplot(
                data=by_category,
                x="Category",
                y="revenue",
                hue="is_discounted",
                ax=ax1,
            )
            ax1.set_title(f"Revenue by category and discount flag – {ctx.label}")
            ax1.set_xlabel("Category")
            ax1.set_ylabel("Revenue")
            ax1.tick_params(axis="x", rotation=45)
            figures.append(fig1)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        summary = stats["summary"]
        if not summary:
            return (
                f"For the period {ctx.label}, no promotional or discount activity "
                "is visible in the data. This may reflect either a period with no "
                "price-based activity or a gap in how discounts are captured."
            )

        promo_unit_share = summary["promo_unit_share"]
        promo_revenue_share = summary["promo_revenue_share"]

        narrative_parts = [
            (
                f"In the {ctx.label} period, approximately {promo_unit_share:,.1f}% "
                "of all units sold carried some form of discount, accounting for "
                f"{promo_revenue_share:,.1f}% of net sales value. This indicates the "
                "degree to which promotional mechanics contribute to overall volume."
            ),
            (
                "When a large share of volume is sold under promotion, the business "
                "may become reliant on deal-driven behavior, which can compress "
                "margins and make baseline demand harder to interpret. Conversely, "
                "too little promotional activity may mean missed opportunities to "
                "stimulate trial, shift mix, or defend share during key seasons."
            ),
        ]

        return "\n\n".join(narrative_parts)
