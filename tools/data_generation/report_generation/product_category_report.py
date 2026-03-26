"""
Product and category performance report.

Analyzes which products and categories drive sales, using contribution
and ranking style views.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import data_access
from .report_base import BaseReport, ReportContext


class ProductCategoryReport(BaseReport):
    """Concrete implementation of the product & category performance report."""

    name: str = "product_category"
    category: str = "product and category performance"

    def compute_period_stats(self, ctx: ReportContext) -> dict[str, object]:
        df = self.load_transactions_for_period(ctx)
        if df.empty:
            return {
                "by_product": pd.DataFrame(),
                "by_category": pd.DataFrame(),
            }

        by_product = data_access.aggregate_transactions(
            df, ["Product_ID", "SKU"], ["revenue", "units"]
        )
        by_category = (
            df.groupby("Category")
            .agg(
                revenue=("Net_Sales_Value", "sum"),
                units=("Quantity_Sold", "sum"),
            )
            .reset_index()
        )

        total_revenue = by_category["revenue"].sum() or 1.0
        by_category["contribution_pct"] = by_category["revenue"] / total_revenue * 100

        return {
            "by_product": by_product,
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
            sorted_cat = by_category.sort_values("revenue", ascending=False)

            fig1, ax1 = plt.subplots(figsize=(8, 4))
            sns.barplot(
                data=sorted_cat,
                x="Category",
                y="revenue",
                ax=ax1,
            )
            ax1.set_title(f"Revenue by category – {ctx.label}")
            ax1.set_xlabel("Category")
            ax1.set_ylabel("Revenue")
            ax1.tick_params(axis="x", rotation=45)
            figures.append(fig1)

        by_product = stats["by_product"]
        if isinstance(by_product, pd.DataFrame) and not by_product.empty:
            top_products = by_product.sort_values("revenue", ascending=False).head(15)
            fig2, ax2 = plt.subplots(figsize=(8, 4))
            sns.barplot(
                data=top_products,
                x="Product_ID",
                y="revenue",
                ax=ax2,
            )
            ax2.set_title(f"Top 15 products by revenue – {ctx.label}")
            ax2.set_xlabel("Product ID")
            ax2.set_ylabel("Revenue")
            figures.append(fig2)

        return figures

    def build_period_narrative(
        self,
        ctx: ReportContext,
        stats: Mapping[str, object],
    ) -> str:
        by_category = stats["by_category"]
        if not isinstance(by_category, pd.DataFrame) or by_category.empty:
            return (
                f"No product- or category-level transactions were recorded for "
                f"the period {ctx.label} ({ctx.start} to {ctx.end}). As a result, "
                "this report focuses on explaining the analytical framework rather "
                "than interpreting observed performance."
            )

        top_cat = by_category.sort_values("revenue", ascending=False).iloc[0]
        narrative_parts = [
            (
                f"For the period {ctx.label} (from {ctx.start} to {ctx.end}), the "
                "product and category view shows a clear concentration of revenue "
                f"in the {top_cat['Category']} category, which alone accounts for "
                f"approximately {top_cat['contribution_pct']:.1f}% of total sales."
            ),
            (
                "Understanding category concentration is critical when planning "
                "assortment and promotional activity. A handful of dominant "
                "categories often generate the majority of revenue, but over-"
                "reliance on a narrow set of segments can create risk if customer "
                "preferences or competitive dynamics shift."
            ),
        ]

        return "\n\n".join(narrative_parts)
