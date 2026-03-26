"""
Shared chart styling helpers for executive-quality reporting visuals.

This module centralises Seaborn/Matplotlib style configuration so that
all report charts share a consistent, consulting-ready look and feel.
"""

from __future__ import annotations

import matplotlib as mpl
import seaborn as sns

EXECUTIVE_PALETTE: list[str] = [
    "#1f4e79",  # deep blue
    "#6c8ebf",  # muted blue
    "#a3b9d7",  # light blue
    "#4f81bd",  # accent blue
    "#838b8b",  # grey
]


def apply_executive_theme() -> None:
    """
    Configure Seaborn/Matplotlib for executive-style charts.

    This is idempotent and lightweight enough to call before building
    figures in the reporting workflow.
    """

    sns.set_theme(
        style="whitegrid",
        context="talk",
        palette=EXECUTIVE_PALETTE,
    )

    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#cccccc",
            "axes.titleweight": "bold",
            "axes.titlesize": 14,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "grid.color": "#e5e5e5",
        }
    )


def format_axis_labels(
    ax: mpl.axes.Axes, xlabel: str | None = None, ylabel: str | None = None
) -> None:
    """
    Apply consistent labelling and tick formatting to an axis.
    """

    if xlabel is not None:
        ax.set_xlabel(xlabel)
    if ylabel is not None:
        ax.set_ylabel(ylabel)

    for label in ax.get_xticklabels():
        label.set_rotation(20)
        label.set_ha("right")

    ax.grid(True, axis="y", linestyle="-", linewidth=0.5, alpha=0.7)


def annotate_bar_values(ax: mpl.axes.Axes, fmt: str = "{:,.0f}") -> None:
    """
    Add value labels on top of bars for easier reading.
    """

    ymin, ymax = ax.get_ylim()
    offset = (ymax - ymin) * 0.01

    for patch in ax.patches:
        height = patch.get_height()
        if height is None:
            continue
        x = patch.get_x() + patch.get_width() / 2.0
        label = fmt.format(height)
        ax.text(
            x,
            height + offset,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
            rotation=0,
        )


__all__ = [
    "apply_executive_theme",
    "format_axis_labels",
    "annotate_bar_values",
    "EXECUTIVE_PALETTE",
]
