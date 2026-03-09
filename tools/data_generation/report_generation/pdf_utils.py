"""
Lightweight PDF helpers built on Matplotlib.

We keep PDF generation simple and dependency-light by relying on
`matplotlib.backends.backend_pdf.PdfPages` rather than full document
layout engines. Each report period is composed of:

- A title/summary page with key KPIs rendered as text.
- One or more pages with Seaborn/Matplotlib charts.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def create_text_page(
    title: str,
    narrative: str,
    page_size: tuple[float, float] = (8.27, 11.69),
) -> plt.Figure:
    """
    Create a simple text-only page for inclusion in a PDF.

    The narrative can be relatively long; Matplotlib will wrap it within
    the figure bounds with basic newlines. For very long text the caller
    should split into multiple pages.
    """

    fig = plt.figure(figsize=page_size)
    fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=14, weight="bold")
    fig.text(
        0.05,
        0.90,
        narrative,
        ha="left",
        va="top",
        fontsize=9,
        wrap=True,
    )
    plt.axis("off")
    return fig


def save_pdf(
    output_path: Path,
    figures: Sequence[plt.Figure] | Iterable[plt.Figure],
) -> None:
    """
    Save a sequence of Matplotlib figures into a single multi-page PDF.

    The caller is responsible for closing figures after calling this function
    if they are no longer needed.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(str(output_path)) as pdf:
        for fig in figures:
            pdf.savefig(fig)
