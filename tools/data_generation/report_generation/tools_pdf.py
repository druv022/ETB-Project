"""
PDF assembly helpers for the reporting workflow.

These utilities wrap the lower-level helpers in `pdf_utils` so that a
workflow can request a fully composed multi-page PDF given narrative
text and chart image paths.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from pathlib import Path

from .pdf_reportlab_utils import build_narrative_and_charts_pdf


def render_pdf(
    category: str,
    granularity: str,
    period_label: str,
    period_start: date,
    period_end: date,
    narrative_text: str,
    chart_image_paths: Iterable[Path],
    output_dir: Path,
) -> Path:
    """
    Assemble a PDF for a single period and return the file path.

    The first one or more pages contain the narrative text with a
    title and \"Executive Summary\" heading; subsequent pages embed the
    provided chart images.
    """

    title = (
        f"{category.title()} report – {granularity} – "
        f"{period_label} ({period_start} to {period_end})"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    filename_base = f"{category}_{granularity}_{period_label}"
    pdf_path = output_dir / f"{filename_base}.pdf"
    md_path = output_dir / f"{filename_base}.md"

    # Persist the narrative markdown alongside the generated PDF so downstream
    # tools (or manual QA) can edit/re-render quickly.
    md_path.write_text(narrative_text, encoding="utf-8")

    chart_paths_list: list[Path] = [Path(p) for p in chart_image_paths]
    build_narrative_and_charts_pdf(
        output_path=pdf_path,
        title=title,
        narrative_text=narrative_text,
        chart_paths=chart_paths_list,
    )

    return pdf_path
