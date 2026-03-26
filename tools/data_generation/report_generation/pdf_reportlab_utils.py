from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from reportlab.lib import colors, enums
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _normalize_markdown_text(text: str) -> str:
    """
    Lightweight Markdown normalisation similar to pdf_utils._normalize_markdown_text.

    Strips emphasis markers while keeping list prefixes.
    """
    import re

    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text.replace("`", "")


def _sanitize_text(text: str) -> str:
    """
    Escape characters that may be interpreted specially by ReportLab's
    underlying text engine. Currently we only escape '$' to avoid
    accidental math-style parsing.
    """
    # ReportLab Paragraph uses a mini XML-like markup; escape the basics.
    # Do NOT escape '$' here; unlike Matplotlib mathtext, ReportLab does not
    # treat '$' specially, and escaping it shows up as a literal backslash.
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _normalize_unicode_punctuation(text: str) -> str:
    """
    Normalize punctuation/spaces that commonly render as tofu (□/■)
    with default ReportLab fonts.

    This keeps the output deterministic and readable without requiring
    custom font embedding.
    """

    # Dashes/hyphens
    text = (
        text.replace("\u2010", "-")  # hyphen
        .replace("\u2011", "-")  # non-breaking hyphen
        .replace("\u2012", "-")  # figure dash
        .replace("\u2013", "-")  # en dash
        .replace("\u2014", "-")  # em dash
        .replace("\u2212", "-")  # minus sign
    )
    # Quotes/apostrophes
    text = (
        text.replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )
    # Spaces
    text = text.replace("\u00a0", " ").replace(  # no-break space
        "\u202f", " "
    )  # narrow no-break space
    return text


def _deterministic_cleanup(text: str) -> str:
    """
    Deterministically remove known noisy artifacts and normalize a small set
    of common garbled tokens seen in generated narratives.
    """

    import re

    page_marker_re = re.compile(r"^\s*--\s*\d+\s+of\s+\d+\s*--\s*$", re.IGNORECASE)
    lines = [ln for ln in text.splitlines() if not page_marker_re.match(ln)]
    cleaned = "\n".join(lines)

    replacements = {
        "InnStore": "In-Store",
        "innstore": "in-store",
        "Storenlevel": "Store-level",
        "storenlevel": "store-level",
        "channelnspecific": "channel-specific",
        "pickupnspecific": "pickup-specific",
        "lownperforming": "low-performing",
        "undernperforming": "under-performing",
        "timendimensional": "time-dimensional",
        "yearnago": "year-ago",
        "onnethird": "one-third",
        "nearnequal": "near-equal",
        "ActionnOriented": "Action-Oriented",
        "BasketnSize": "Basket-Size",
        "crossnsell": "cross-sell",
    }
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)
    return cleaned


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}
    styles["title"] = ParagraphStyle(
        "ReportTitle",
        parent=base["Heading1"],
        alignment=enums.TA_CENTER,
        fontSize=20,
        leading=24,
        spaceAfter=12,
    )
    styles["heading"] = ParagraphStyle(
        "SectionHeading",
        parent=base["Heading2"],
        alignment=enums.TA_LEFT,
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=6,
    )
    styles["subheading"] = ParagraphStyle(
        "SubHeading",
        parent=base["Heading3"],
        alignment=enums.TA_LEFT,
        fontSize=12,
        leading=15,
        spaceBefore=10,
        spaceAfter=4,
    )
    styles["body"] = ParagraphStyle(
        "BodyText",
        parent=base["BodyText"],
        alignment=enums.TA_JUSTIFY,
        fontSize=10,
        leading=14,
    )
    styles["bullet"] = ParagraphStyle(
        "BulletText",
        parent=styles["body"],
        leftIndent=14,
        bulletIndent=6,
        spaceBefore=2,
        spaceAfter=2,
    )
    styles["numbered"] = ParagraphStyle(
        "NumberedText",
        parent=styles["body"],
        leftIndent=10,
        spaceBefore=6,
        spaceAfter=2,
    )
    styles["caption"] = ParagraphStyle(
        "ChartCaption",
        parent=base["BodyText"],
        alignment=enums.TA_CENTER,
        fontSize=9,
        leading=11,
        textColor=colors.grey,
        spaceBefore=2,
        spaceAfter=6,
    )
    return styles


def _chunk_sequence(seq: Sequence[Path], size: int) -> list[list[Path]]:
    return [list(seq[i : i + size]) for i in range(0, len(seq), size)]


def _classify_image_orientation(img_path: Path) -> str:
    """
    Classify chart orientation as 'wide' or 'tall' using image aspect ratio.
    """
    from PIL import Image as PILImage

    with PILImage.open(img_path) as im:
        width, height = im.size
    if height == 0:
        return "wide"
    aspect = width / float(height)
    return "wide" if aspect >= 1.1 else "tall"


def _build_chart_tables(
    chart_paths: Sequence[Path],
    page_width: float,
    page_height: float,
    styles: dict[str, ParagraphStyle],
) -> list[Table | Image | PageBreak]:
    """
    Build a sequence of flowables (Tables/Images/PageBreak) for charts using
    a size-aware grid strategy:

    - 1 chart → full-width image on its own page.
    - 2 charts → either vertical stack or side-by-side depending on orientation.
    - 3 charts → one wide on top, two below.
    - 4 charts → 2x2 grid.
    """
    flowables: list[Table | Image | PageBreak] = []
    usable_width = page_width - 2 * inch

    i = 0
    n = len(chart_paths)
    while i < n:
        remaining = n - i
        group: list[Path]
        if remaining >= 4:
            group = list(chart_paths[i : i + 4])
        else:
            group = list(chart_paths[i:])
        count = len(group)

        if count == 1:
            img_path = group[0]
            img = Image(str(img_path), width=usable_width, hAlign="CENTER")
            flowables.append(img)
            flowables.append(Spacer(1, 0.12 * inch))
            flowables.append(PageBreak())
        elif count == 2:
            o1 = _classify_image_orientation(group[0])
            o2 = _classify_image_orientation(group[1])
            if o1 == "tall" and o2 == "tall":
                w = usable_width / 2.0
                row = [
                    Image(str(group[0]), width=w, hAlign="CENTER"),
                    Image(str(group[1]), width=w, hAlign="CENTER"),
                ]
                table = Table([row], colWidths=[w, w])
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ]
                    )
                )
                flowables.append(table)
            else:
                w = usable_width
                row1 = [Image(str(group[0]), width=w, hAlign="CENTER")]
                row2 = [Image(str(group[1]), width=w, hAlign="CENTER")]
                table = Table([row1, row2], colWidths=[w])
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                flowables.append(table)
            flowables.append(Spacer(1, 0.08 * inch))
            flowables.append(PageBreak())
        elif count == 3:
            w_full = usable_width
            w_half = usable_width / 2.0
            top = [Image(str(group[0]), width=w_full, hAlign="CENTER")]
            bottom = [
                Image(str(group[1]), width=w_half, hAlign="CENTER"),
                Image(str(group[2]), width=w_half, hAlign="CENTER"),
            ]
            table = Table([top, bottom], colWidths=[w_full, w_half])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                )
            )
            flowables.append(table)
            flowables.append(Spacer(1, 0.08 * inch))
            flowables.append(PageBreak())
        else:
            w = usable_width / 2.0
            rows: list[list[Image]] = []
            for chunk in _chunk_sequence(group, 2):
                if len(chunk) == 1:
                    row = [Image(str(chunk[0]), width=w, hAlign="CENTER"), Spacer(w, 0)]
                else:
                    row = [
                        Image(str(chunk[0]), width=w, hAlign="CENTER"),
                        Image(str(chunk[1]), width=w, hAlign="CENTER"),
                    ]
                rows.append(row)
            table = Table(rows, colWidths=[w, w])
            table.setStyle(
                TableStyle(
                    [
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            flowables.append(table)
            flowables.append(Spacer(1, 0.08 * inch))
            flowables.append(PageBreak())

        i += count

    return flowables


def _markdown_to_flowables(
    markdown_text: str, styles: dict[str, ParagraphStyle]
) -> list[object]:
    """
    Convert a small subset of Markdown into ReportLab flowables.

    Supported deterministically:
    - #/##/### headings
    - --- horizontal rules
    - numbered and bulleted lists
    - paragraphs
    """

    import re

    hr_re = re.compile(r"^\s*---+\s*$")
    h_re = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*$")
    bullet_re = re.compile(r"^\s*[-*]\s+(?P<text>.+?)\s*$")
    numbered_re = re.compile(r"^\s*(?P<num>\d+)\.\s+(?P<text>.+?)\s*$")
    table_row_re = re.compile(r"^\s*\|.+\|\s*$")
    table_sep_re = re.compile(r"^\s*\|\s*:?[-]+:?(\s*\|\s*:?[-]+:?)*\s*\|\s*$")

    story: list[object] = []
    # Work on cleaned-but-still-marked-up lines so we can detect patterns
    # like "**Heading**  1. Item" before stripping emphasis markers.
    raw_cleaned = _normalize_unicode_punctuation(_deterministic_cleanup(markdown_text))
    lines = raw_cleaned.splitlines()

    # If the narrative begins with a "# Title" line, ignore it because we
    # render the passed-in `title` separately.
    if lines and lines[0].lstrip().startswith("# "):
        lines = lines[1:]

    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        line = raw.strip()

        if not line:
            i += 1
            continue

        # Table syntax: header row, separator row, then 0+ body rows, all pipe-based.
        if (
            table_row_re.match(line)
            and i + 1 < len(lines)
            and table_sep_re.match(lines[i + 1].strip())
        ):
            header_cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows: list[list[str]] = [header_cells]
            i += 2
            while i < len(lines) and table_row_re.match(lines[i].strip()):
                body_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(body_cells)
                i += 1

            # Build a simple styled ReportLab table
            col_count = max(len(r) for r in rows)
            data: list[list[str]] = []
            for r in rows:
                padded = r + [""] * (col_count - len(r))
                data.append(
                    [
                        _sanitize_text(
                            _normalize_markdown_text(
                                _normalize_unicode_punctuation(cell)
                            )
                        )
                        for cell in padded
                    ]
                )

            col_width = (6.5 * inch) / max(col_count, 1)
            tbl = Table(data, colWidths=[col_width] * col_count)
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                        ("TOPPADDING", (0, 0), (-1, 0), 4),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 0.18 * inch))
            continue

        # Special-case pattern: "**Heading**  1. First item"
        # Treat as a heading followed by a numbered item, instead of
        # leaving "1." on the same line as the heading text.
        heading_item = re.match(r"^\s*\*\*(.+?)\*\*\s+1\.\s+(.+)$", raw)
        if heading_item:
            heading_text = heading_item.group(1).strip()
            item_text = heading_item.group(2).strip()
            story.append(
                Paragraph(
                    _sanitize_text(_normalize_markdown_text(heading_text)),
                    styles["heading"],
                )
            )
            story.append(
                Paragraph(
                    "1. " + _sanitize_text(_normalize_markdown_text(item_text)),
                    styles["numbered"],
                )
            )
            i += 1
            continue

        # General bold-heading heuristic:
        # Lines that start with **Heading** - rest of sentence
        # become a bold heading paragraph followed by a normal body paragraph.
        bold_heading = re.match(r"^\s*\*\*(.+?)\*\*\s*[-–]\s*(.+)$", raw)
        if bold_heading:
            heading_text = bold_heading.group(1).strip()
            tail_text = bold_heading.group(2).strip()
            story.append(
                Paragraph(
                    _sanitize_text(_normalize_markdown_text(heading_text)),
                    styles["heading"],
                )
            )
            if tail_text:
                story.append(
                    Paragraph(
                        _sanitize_text(_normalize_markdown_text(tail_text)),
                        styles["body"],
                    )
                )
            i += 1
            continue

        if hr_re.match(line):
            # Divider line
            t = Table([[""]], colWidths=[6.5 * inch], rowHeights=[0.02 * inch])
            t.setStyle(
                TableStyle(
                    [
                        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.lightgrey),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(t)
            i += 1
            continue

        hm = h_re.match(line)
        if hm:
            level = len(hm.group("level"))
            text = hm.group("text").strip()
            if level <= 2:
                story.append(Paragraph(text, styles["heading"]))
            else:
                story.append(Paragraph(text, styles["subheading"]))
            i += 1
            continue

        bm = bullet_re.match(raw)
        if bm:
            bullet_text = bm.group("text").strip()
            cleaned_text = _sanitize_text(_normalize_markdown_text(bullet_text))

            # Heuristic: if the bullet is very long or looks like multiple
            # sentences, render as a standalone paragraph instead of a list
            # item so it reads more like narrative than a dense list.
            sentence_splits = re.split(r"[.!?]\s+", cleaned_text)
            is_long = len(cleaned_text) > 220
            many_sentences = len([s for s in sentence_splits if s]) > 2

            if is_long or many_sentences:
                story.append(Paragraph(cleaned_text, styles["body"]))
            else:
                story.append(
                    Paragraph(
                        cleaned_text,
                        styles["bullet"],
                        bulletText="•",
                    )
                )
            i += 1
            continue

        nm = numbered_re.match(raw)
        if nm:
            text = f"{nm.group('num')}. {nm.group('text').strip()}"
            story.append(
                Paragraph(
                    _sanitize_text(_normalize_markdown_text(text)),
                    styles["numbered"],
                )
            )
            i += 1
            continue

        # paragraph: accumulate consecutive non-structural lines
        para_lines = [line]
        i += 1
        while i < len(lines):
            peek_raw = lines[i].rstrip()
            peek = peek_raw.strip()
            if not peek:
                break
            if (
                hr_re.match(peek)
                or h_re.match(peek)
                or bullet_re.match(peek_raw)
                or numbered_re.match(peek_raw)
            ):
                break
            para_lines.append(peek)
            i += 1
        body_text = _sanitize_text(_normalize_markdown_text(" ".join(para_lines)))
        story.append(Paragraph(body_text, styles["body"]))
        story.append(Spacer(1, 0.12 * inch))

    return story


def build_narrative_and_charts_pdf(
    output_path: Path,
    title: str,
    narrative_text: str,
    chart_paths: Iterable[Path],
) -> None:
    """
    Build a paginated PDF using ReportLab, mixing narrative and charts.

    - Page 1: title, \"Executive Summary\" heading, some body text, and
      optionally 1-2 key charts if space permits.
    - Subsequent pages: remaining narrative followed by chart grids.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    page_width, page_height = A4
    styles = _build_styles()

    clean_title = _sanitize_text(
        _normalize_markdown_text(
            _normalize_unicode_punctuation(_deterministic_cleanup(title))
        )
    )

    story: list[object] = []
    story.append(Paragraph(clean_title, styles["title"]))

    # Render narrative Markdown deterministically into headings, lists, etc.
    story.extend(_markdown_to_flowables(narrative_text, styles))

    # Charts after narrative (grid layout)
    chart_paths_list = list(chart_paths)
    if chart_paths_list:
        story.append(PageBreak())
        story.extend(
            _build_chart_tables(chart_paths_list, page_width, page_height, styles)
        )

    if story and isinstance(story[-1], PageBreak):
        story = story[:-1]

    doc.build(story)
