---
name: improve-pdf-pagination
overview: Replace character-count based Matplotlib pagination with a robust layout-engine-based approach for narrative pages while keeping chart rendering straightforward.
todos:
  - id: dep-setup-reportlab
    content: Add reportlab to requirements and update README with PDF dependency notes.
    status: completed
  - id: impl-reportlab-builder
    content: Implement a ReportLab-based builder that takes title, narrative_text, and chart_paths and writes a paginated PDF.
    status: completed
  - id: integrate-render-pdf
    content: Refactor tools_pdf.render_pdf to delegate PDF creation to the ReportLab builder while keeping its public API intact.
    status: completed
  - id: verify-workflow-integration
    content: Confirm report_tools.render_pdf_tool_node and workflow_graph still work end-to-end with the new pagination.
    status: completed
  - id: add-tests-pdf-pagination
    content: Add or update tests to validate multi-page narrative behavior and chart page placement in the generated PDFs.
    status: completed
isProject: false
---

# Improve PDF Pagination With ReportLab

## Goals

- **Replace** the current character-count based narrative pagination with **layout-aware pagination** using ReportLab Platypus.
- **Keep** the existing chart-generation pipeline (Matplotlib PNGs) and append them as pages in the same PDF.
- **Minimize impact** on the rest of the reporting workflow (`workflow_graph`, `report_tools`, LangGraph wiring).

## Current State

- Narrative pagination happens in `[tools/data_generation/report_generation/pdf_utils.py](tools/data_generation/report_generation/pdf_utils.py)`:
  - `_split_narrative_into_pages` uses `max_chars_per_page` and paragraph lengths.
  - `create_narrative_pages` builds one Matplotlib `Figure` per narrative chunk.
  - `save_pdf` iterates `figures` and writes each as a new page via `PdfPages`.
- PDF assembly happens in `[tools/data_generation/report_generation/tools_pdf.py](tools/data_generation/report_generation/tools_pdf.py)`:
  - `render_pdf(...)` builds `narrative_figs` + one `Figure` per chart image, then calls `save_pdf`.
  - `render_pdf` is used by `render_pdf_tool_node` in `[tools/data_generation/report_generation/report_tools.py](tools/data_generation/report_generation/report_tools.py)` and the LangGraph in `[tools/data_generation/report_generation/workflow_graph.py](tools/data_generation/report_generation/workflow_graph.py)`.

## High-Level Approach

1. **Introduce ReportLab** as a dependency (community edition).
2. **Refactor narrative pagination** to use ReportLab Platypus `Paragraph`, `Spacer`, and `PageBreak` instead of character-count splitting.
3. **Embed chart PNGs** into the same ReportLab document as `Image` flowables, one per page.
4. **Keep the `render_pdf(...)` interface** stable so callers don’t need changes (category, granularity, dates, narrative text, chart paths, output dir).
5. **Retain the Markdown companion file** generation behavior from `render_pdf`.

## Detailed Steps

### 1. Add and document ReportLab dependency

- **Update** `requirements.txt` to include `reportlab`.
- **Update** root `README.md` with a short note under setup explaining that PDF report generation uses ReportLab and any environment notes (e.g., `pip install -r requirements.txt`).

### 2. Design a new PDF builder using Platypus

- In a new helper module (e.g., `[tools/data_generation/report_generation/pdf_reportlab_utils.py](tools/data_generation/report_generation/pdf_reportlab_utils.py)`) or by refactoring `pdf_utils`:
  - **Create a function** like `build_narrative_and_charts_pdf(path, title, narrative_text, chart_paths)` that:
    - Uses `SimpleDocTemplate` with A4 page size (matching current `(8.27, 11.69)` inches) and margins.
    - Defines a base `ParagraphStyle` for body text and a style for the main title and section headings.
    - Normalizes Markdown-style emphasis similarly to `_normalize_markdown_text` and escapes `$` like `_sanitize_text` did.
    - Converts the narrative into a sequence of **Paragraph** and **Spacer** flowables, preserving paragraphs and headings.
    - Optionally treats the first page specially (e.g., title + "Executive Summary" heading at the top) by:
      - Adding a large title Paragraph.
      - Adding an "Executive Summary" heading Paragraph.
      - Then adding narrative paragraphs; Platypus handles page breaks automatically as content overflows.
    - After narrative flowables, appends one **Image** flowable per chart path, each sized to fit the page and followed by `PageBreak` where appropriate.
  - Let Platypus handle **pagination automatically** based on available space instead of manually counting characters.

### 3. Wire ReportLab builder into `render_pdf`

- In `[tools/data_generation/report_generation/tools_pdf.py](tools/data_generation/report_generation/tools_pdf.py)`:
  - **Preserve** the current `render_pdf(...)` signature and behavior from the caller’s perspective (same arguments, same return type).
  - Replace the Matplotlib narrative/figure stack with a call to the new ReportLab builder:
    - Construct `title` exactly as now (`"{category.title()} report – {granularity} – {period_label} (...)"`).
    - Resolve `output_dir` and `filename_base` as before.
    - Call `build_narrative_and_charts_pdf(pdf_path, title, narrative_text, chart_paths)` instead of generating Matplotlib figures and calling `save_pdf`.
  - **Keep** the Markdown companion file generation as-is, so downstream tooling and tests relying on the `.md` files remain unchanged.

### 4. Gradually retire or repurpose existing Matplotlib pagination helpers

- In `[pdf_utils.py](tools/data_generation/report_generation/pdf_utils.py)`:
  - Leave existing helpers in place initially to avoid breaking other usages (if any). If they are only used by `tools_pdf`, they can be deprecated or simplified.
  - Optionally:
    - Keep `save_pdf` (still useful if other parts of the project want Matplotlib-only PDFs).
    - Mark `_split_narrative_into_pages` and `create_narrative_pages` as legacy in docstrings or comments, steering new code toward the ReportLab flow.

### 5. Align layout & styling with existing reports

- Choose page size and basic margins to roughly match current A4 layout.
- Set fonts and styles to be clear and readable (e.g., using default ReportLab fonts):
  - Title: larger, bold, centered at top.
  - "Executive Summary" heading: medium size, bold, left-aligned.
  - Body: 10–11 pt, left-aligned with comfortable leading.
- Ensure each chart image scales to fit inside margins while preserving aspect ratio.

### 6. Testing strategy

- Add or extend tests under `tests/` to validate behavior:
  - Ensure `render_pdf(...)` still returns a valid path and writes a PDF file.
  - For a long `narrative_text`, confirm that the resulting PDF has **multiple pages** (using a PDF inspection library or checking the file size against a known baseline).
  - For multiple chart paths, ensure each chart appears on its own page after narrative pages (e.g., by counting page images or by a heuristic test).
  - Verify that the Markdown companion file is still generated and contains expected sections and chart references.
- Run existing tests involving `report_tools.render_pdf_tool_node` and `workflow_graph` to ensure the higher-level workflow is unchanged.

### 7. Optional enhancements (future work)

- Add basic **table-of-contents** or page headers/footers via ReportLab page templates.
- Implement simple **keep-with-next** behavior for certain heading levels (e.g., avoid orphaned headings) using Paragraph styles and custom flowables.
- Allow per-report customization of page size or margins via configuration if needed.
