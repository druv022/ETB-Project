"""
Lightweight PDF helpers built on Matplotlib.

We keep PDF generation simple and dependency-light by relying on
`matplotlib.backends.backend_pdf.PdfPages` rather than full document
layout engines. Each report period is composed of:

- A title/summary page with key KPIs rendered as text.
- One or more pages with Seaborn/Matplotlib charts.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


def _normalize_markdown_text(text: str) -> str:
    """
    Strip the most common lightweight Markdown markers so the PDF
    renders clean prose instead of raw Markdown syntax.

    We deliberately keep list prefixes like "1." or "-" but remove
    emphasis markers (`*`, `_`, `` ` ``) and bold markers (`**`, `__`).
    """

    # Bold / strong
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    # Emphasis / italics
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Inline code ticks
    text = text.replace("`", "")
    return text


def _sanitize_text(text: str) -> str:
    """
    Make text safe for Matplotlib's mathtext parser.

    Matplotlib will interpret unescaped '$' as mathtext, which can raise
    parsing errors for natural language like currency amounts. We escape
    dollar signs so they render as literal characters in PDFs.
    """
    return text.replace("$", r"\$")


_PAGE_MARKER_RE = re.compile(r"^\s*--\s*\d+\s+of\s+\d+\s*--\s*$", re.IGNORECASE)
_HR_RE = re.compile(r"^\s*---+\s*$")
_H_RE = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
_NUMBERED_RE = re.compile(r"^\s*(?P<num>\d+)\.\s+(?P<text>.+?)\s*$")


_GARBLED_TOKEN_REPLACEMENTS: dict[str, str] = {
    "InnStore": "In-Store",
    "innstore": "in-store",
    "Storenlevel": "Store-level",
    "storenlevel": "store-level",
    "Store nLevel": "Store-Level",
    "Store‑Level": "Store-Level",
    "under nperforming": "under-performing",
    "under‑performing": "under-performing",
    "near nequal": "near-equal",
    "near‑equal": "near-equal",
    "channel nspecific": "channel-specific",
    "channel‑specific": "channel-specific",
    "Product nLevel": "Product-Level",
    "Product‑Level": "Product-Level",
    "Action nOriented": "Action-Oriented",
    "Action‑Oriented": "Action-Oriented",
    "pickup nspecific": "pickup-specific",
    "pickup‑specific": "pickup-specific",
    "cross nsell": "cross-sell",
    "cross‑sell": "cross-sell",
    "Basket nSize": "Basket-Size",
    "Basket‑Size": "Basket-Size",
    "time ndimensional": "time-dimensional",
    "time‑dimensional": "time-dimensional",
    "year nayo": "year-ago",
    "year‑ago": "year-ago",
    "one nthird": "one-third",
    "one‑third": "one-third",
    "high‑ and low‑performing": "high- and low-performing",
}


def _deterministic_cleanup(text: str) -> str:
    """
    Deterministically remove known noisy artifacts and normalise a small
    set of common garbled tokens seen in generated narratives.
    """

    cleaned_lines: list[str] = []
    for line in text.splitlines():
        if _PAGE_MARKER_RE.match(line):
            continue
        cleaned_lines.append(line)
    cleaned = "\n".join(cleaned_lines)

    for bad, good in _GARBLED_TOKEN_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)

    return cleaned


@dataclass(frozen=True)
class _MdBlock:
    kind: str
    text: str
    level: int = 0
    indent: int = 0


def _parse_markdown_blocks(markdown_text: str) -> list[_MdBlock]:
    """
    Parse a small, deterministic subset of Markdown used by the narratives.

    Supported:
    - #/##/### headings
    - --- horizontal rules
    - numbered and bulleted lists (one level, with optional indentation)
    - paragraphs
    """

    text = _deterministic_cleanup(markdown_text)
    blocks: list[_MdBlock] = []

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()

        if not line:
            i += 1
            continue

        if _HR_RE.match(line):
            blocks.append(_MdBlock(kind="hr", text=""))
            i += 1
            continue

        hm = _H_RE.match(line)
        if hm:
            level = len(hm.group("level"))
            heading_text = hm.group("text").strip()
            blocks.append(_MdBlock(kind="heading", text=heading_text, level=level))
            i += 1
            continue

        bm = _BULLET_RE.match(raw)
        if bm:
            indent = max((len(raw) - len(raw.lstrip())) // 2, 0)
            blocks.append(
                _MdBlock(kind="bullet", text=bm.group("text").strip(), indent=indent)
            )
            i += 1
            continue

        nm = _NUMBERED_RE.match(raw)
        if nm:
            indent = max((len(raw) - len(raw.lstrip())) // 2, 0)
            blocks.append(
                _MdBlock(
                    kind="numbered",
                    text=f"{nm.group('num')}. {nm.group('text').strip()}",
                    indent=indent,
                )
            )
            i += 1
            continue

        # Paragraph: accumulate until blank line or a structural marker
        para_lines: list[str] = [line]
        i += 1
        while i < len(lines):
            peek_raw = lines[i].rstrip()
            peek = peek_raw.strip()
            if not peek:
                break
            if (
                _HR_RE.match(peek)
                or _H_RE.match(peek)
                or _BULLET_RE.match(peek_raw)
                or _NUMBERED_RE.match(peek_raw)
            ):
                break
            para_lines.append(peek)
            i += 1
        blocks.append(_MdBlock(kind="paragraph", text=" ".join(para_lines)))

    return blocks


def create_markdown_pages(
    *,
    title: str,
    markdown_text: str,
    page_size: tuple[float, float] = (8.27, 11.69),
) -> list[plt.Figure]:
    """
    Render a subset of Markdown into styled, paginated PDF pages.

    This treats Markdown markers as layout signals (e.g. ## headings)
    instead of showing them as literal characters.
    """

    # Preserve Markdown structure for headings, lists, and rules;
    # normalise inline emphasis markers and escape for Matplotlib.
    blocks = _parse_markdown_blocks(markdown_text)

    figures: list[plt.Figure] = []
    page_num = 0

    # Layout constants in figure coordinates (0..1)
    left = 0.06
    right = 0.94
    top = 0.95
    bottom = 0.06

    def new_page() -> tuple[plt.Figure, float]:
        nonlocal page_num
        page_num += 1
        fig = plt.figure(figsize=page_size)
        plt.axis("off")
        # Footer page number
        fig.text(
            0.95,
            0.03,
            str(page_num),
            ha="right",
            va="bottom",
            fontsize=8,
            color="#666666",
        )
        figures.append(fig)
        return fig, top

    fig, y = new_page()

    # Title (always rendered as H1-like)
    safe_title = _sanitize_text(_normalize_markdown_text(title))
    fig.text(0.5, y, safe_title, ha="center", va="top", fontsize=18, weight="bold")
    y -= 0.06

    def draw_wrapped(
        *,
        text: str,
        fontsize: int,
        weight: str | None = None,
        x: float = left,
        y_start: float,
        indent_levels: int = 0,
        line_step: float,
        wrap_width: int,
    ) -> float:
        safe = _sanitize_text(_normalize_markdown_text(text))
        wrapped = re.sub(r"\s+", " ", safe).strip()
        if not wrapped:
            return y_start
        wrapped_lines: list[str] = []
        for wline in wrapped.split("\n"):
            pattern = rf".{{1,{wrap_width}}}(?:\s+|$)"
            wrapped_lines.extend(re.findall(pattern, wline))
        wrapped_lines = [line.strip() for line in wrapped_lines if line.strip()]

        x0 = x + indent_levels * 0.03
        yy = y_start
        for line in wrapped_lines:
            if yy < bottom:
                nonlocal fig, y
                fig, yy = new_page()
            fig.text(
                x0, yy, line, ha="left", va="top", fontsize=fontsize, weight=weight
            )
            yy -= line_step
        return yy

    for block in blocks:
        if block.kind == "hr":
            # small spacing + divider line
            if y < bottom + 0.05:
                fig, y = new_page()
            y -= 0.01
            fig.add_artist(
                plt.Line2D(
                    [left, right],
                    [y, y],
                    transform=fig.transFigure,
                    color="#dddddd",
                    linewidth=1.0,
                )
            )
            y -= 0.03
            continue

        if block.kind == "heading":
            # Heading levels: 2/3 are common; map to sizes
            size_map = {1: 16, 2: 14, 3: 12, 4: 11, 5: 11, 6: 11}
            step_map = {1: 0.05, 2: 0.045, 3: 0.04, 4: 0.035, 5: 0.035, 6: 0.035}
            wrap_map = {1: 60, 2: 70, 3: 80, 4: 90, 5: 90, 6: 90}

            if y < bottom + 0.08:
                fig, y = new_page()
            y = draw_wrapped(
                text=block.text,
                fontsize=size_map.get(block.level, 12),
                weight="bold",
                y_start=y,
                indent_levels=0,
                line_step=step_map.get(block.level, 0.04),
                wrap_width=wrap_map.get(block.level, 80),
            )
            y -= 0.02
            continue

        if block.kind == "bullet":
            bullet_text = f"• {block.text}"
            y = draw_wrapped(
                text=bullet_text,
                fontsize=10,
                y_start=y,
                indent_levels=block.indent,
                line_step=0.028,
                wrap_width=95,
            )
            y -= 0.01
            continue

        if block.kind == "numbered":
            y = draw_wrapped(
                text=block.text,
                fontsize=10,
                weight="bold",
                y_start=y,
                indent_levels=block.indent,
                line_step=0.03,
                wrap_width=95,
            )
            y -= 0.01
            continue

        # paragraph
        y = draw_wrapped(
            text=block.text,
            fontsize=10,
            y_start=y,
            indent_levels=0,
            line_step=0.028,
            wrap_width=95,
        )
        y -= 0.02

    return figures


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
    # First normalise Markdown-style markers, then escape for Matplotlib.
    safe_title = _sanitize_text(_normalize_markdown_text(title))
    safe_narrative = _sanitize_text(_normalize_markdown_text(narrative))
    fig.text(0.5, 0.95, safe_title, ha="center", va="top", fontsize=16, weight="bold")
    fig.text(
        0.05,
        0.90,
        safe_narrative,
        ha="left",
        va="top",
        fontsize=10,
        wrap=True,
    )
    plt.axis("off")
    return fig


def _split_narrative_into_pages(
    narrative: str,
    max_chars_per_page: int = 2500,
) -> list[str]:
    """
    Split a long narrative into reasonably sized page chunks.

    This is a pragmatic text-based paginator that keeps paragraphs
    intact where possible and avoids overcrowding a single page.
    """

    paragraphs = [p.strip() for p in narrative.split("\n\n") if p.strip()]
    pages: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        if current and current_len + para_len > max_chars_per_page:
            pages.append("\n\n".join(current))
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        pages.append("\n\n".join(current))

    return pages


def create_narrative_pages(
    title: str,
    narrative: str,
    page_size: tuple[float, float] = (8.27, 11.69),
) -> list[plt.Figure]:
    """
    Create one or more pages for a narrative with basic headings.

    - Page 1: report title and \"Executive Summary\" heading.
    - Subsequent pages: continuation of the narrative body only.
    """

    pages = _split_narrative_into_pages(narrative)
    figures: list[plt.Figure] = []

    for i, page_text in enumerate(pages):
        fig = plt.figure(figsize=page_size)
        safe_title = _sanitize_text(_normalize_markdown_text(title))
        safe_body = _sanitize_text(_normalize_markdown_text(page_text))

        if i == 0:
            # Title at top
            fig.text(
                0.5,
                0.95,
                safe_title,
                ha="center",
                va="top",
                fontsize=16,
                weight="bold",
            )
            # Executive summary heading
            fig.text(
                0.05,
                0.88,
                "Executive Summary",
                ha="left",
                va="top",
                fontsize=12,
                weight="bold",
            )
            y_start = 0.84
        else:
            y_start = 0.94

        fig.text(
            0.05,
            y_start,
            safe_body,
            ha="left",
            va="top",
            fontsize=10,
            wrap=True,
        )
        plt.axis("off")
        figures.append(fig)

    return figures


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
