---
name: langgraph-report-generation
overview: Design a LangGraph-based workflow that orchestrates multi-period retail reports as graph nodes, using tools for SQL access, analytics, charting, LLM narrative generation, and PDF assembly.
todos:
  - id: define-report-tools
    content: Define Python tool interfaces for SQL, aggregation, charting, narrative generation, and PDF assembly used by the report LangGraph
    status: completed
  - id: design-report-graph-structure
    content: Design the LangGraph node and edge structure implementing the multi-stage reporting flow
    status: completed
  - id: implement-report-graph
    content: Implement the report LangGraph, wiring nodes to the concrete tools and existing reporting modules
    status: completed
  - id: add-tests-report-graph
    content: Add unit and integration tests for the report tools and LangGraph flow
    status: completed
  - id: docs-report-graph
    content: Document how to configure and invoke the report-generation LangGraph, with examples
    status: completed
isProject: false
---

## Overview

This plan describes how to convert the existing batch-style report generation into a LangGraph workflow. The graph will orchestrate: determining the reporting stage and granularity, gathering data via SQL tools, generating analytics and charts via Python tools, producing descriptive text via LLM tools, and finally assembling multi-page PDFs. The design reuses the transaction database and reporting code under `tools/data_generation/report_generation/` while exposing each step as composable LangGraph nodes.

## High-level LangGraph design

- **Graph entrypoint**
  - Node: `start` – receives a request payload specifying:
    - `category` (sales, product_category, etc.)
    - `preferred_granularity` (optional; if missing, system starts at weekly)
    - `date_range` (start_date, end_date)
    - `stage` (optional state marker: weekly, biweekly, monthly, quarterly, semiannual, yearly, done)
  - Edge: `start -> determine_stage`.
- **Stage determination**
  - Node: `determine_stage` – decides which granularity to run next based on:
    - If `stage` is `None`, set `stage = weekly`.
    - If `stage` is set and more granularities remain, advance (weekly → biweekly → monthly → quarterly → semiannual → yearly).
    - If all stages have run or user only requested one granularity, mark as `done`.
  - Edges:
    - If `stage == done` → `end`.
    - Else → `generate_periods`.
- **Period enumeration**
  - Node: `generate_periods` – uses time window utilities to create period ranges for the current stage:
    - Calls a `time_window` tool (Python) that wraps the functions in `time_windows.py`: `get_weeks`, `get_biweeks`, `get_months`, etc.
    - Produces a list of period objects `{label, start_date, end_date}`.
  - Edge: `generate_periods -> for_each_period` (subgraph/loop).
- **Per-period subgraph**
  - Subgraph: `for_each_period` – iterates over each period and runs a mini-pipeline:
    - Nodes (per period):
      1. `build_sql_query`
      2. `read_transactions`
      3. `compute_analytics`
      4. `generate_charts`
      5. `generate_narrative`
      6. `assemble_pdf`
    - The subgraph aggregates outputs (paths to PDFs, summary metadata) and returns to the main graph.
- **Stage advancement**
  - Node: `advance_stage` – updates the `stage` in graph state based on what was just completed and user configuration.
  - Edge: `advance_stage -> determine_stage` for the next loop, or `advance_stage -> end` when all required stages have been run.

## Tools to define

### 1. SQL and data access tools

- `**sql_query_generator` tool**
  - Purpose: Given a report category, period, and optional focus (store, category, customer), generate a parameterized SQL query string targeting the `transactions` table.
  - Inputs:
    - `category`, `period_start`, `period_end`, `dimensions`, `metrics`.
  - Output:
    - `sql` string plus a structured description of selected columns.
  - Implementation: Python function that builds safe, templated queries leveraging existing schema (no free-form LLM SQL to keep it deterministic).
- `**sql_execute` / `read_database` tool**
  - Purpose: Execute a SQL query against the SQLite DB built from `transaction_database_5yrs_full.sql`.
  - Inputs:
    - `sql` string, `params` (optional).
  - Output:
    - Tabular result as JSON or data frame-like structure.
  - Implementation: Wraps `sqlite3` with connection logic reused from `data_access.default_db_config()` and `connect()`.
- `**aggregate_metrics` tool**
  - Purpose: Convert raw rows to aggregated KPIs for a period.
  - Inputs:
    - `rows` (or a table name in a local temp schema), `group_by`, `metrics` (revenue, units, transactions, discounts, etc.).
  - Output:
    - Aggregated metrics ready for charting and narrative.
  - Implementation: Uses the logic from `aggregate_transactions()` in `data_access.py`, plus any category-specific groupings.

### 2. Analytics and charting tools

- `**build_charts` tool**
  - Purpose: Given a report category, period, and aggregated metrics, generate Seaborn/Matplotlib figures and persist them to disk.
  - Inputs:
    - `category`, `period_label`, `metrics_payload`, `output_dir`.
  - Output:
    - Paths to one or more `.png` files or in-memory figures.
  - Implementation:
    - Wrap the plotting logic from:
      - `sales_performance_report.py`
      - `product_category_report.py`
      - `customer_analytics_report.py`
      - `promotions_pricing_report.py`
      - `inventory_operations_report.py`
      - `financial_margin_report.py`
      - `risk_fraud_report.py`
      - `forecasting_planning_report.py`
    - Normalize function signatures so LangGraph can call a single `build_charts` tool with a `category` switch.
- `**compute_period_stats` tool**
  - Purpose: Category-specific computation of KPIs and summary statistics, separated from charting.
  - Inputs:
    - `category`, `period`, `rows` or `aggregated_table`.
  - Output:
    - A JSON-serializable dictionary of stats (what `compute_period_stats` currently returns in each report module).

### 3. LLM narrative generation tools

- `**generate_narrative` tool (LLM-backed)**
  - Purpose: Draft a ~1000-word narrative per category × period, referencing metrics and chart descriptions.
  - Inputs:
    - `category`, `period_label`, `period_range`, `kpi_summary`, `highlights`, `anomalies`, `chart_captions`.
  - Output:
    - `narrative_text` string.
  - Prompt structure:
    - Provide a fixed outline (executive summary, KPIs & trends, drivers, comparisons, risks & opportunities, recommendations).
    - Include numeric KPIs and a brief description of each chart.
    - Ask the LLM to hit roughly 1000 words and maintain business-appropriate tone.
- `**expand_narrative_to_word_target` helper**
  - Purpose: Ensure the narrative reaches the target length using deterministic padding (background and methodology) if the LLM output is shorter than desired.
  - Reuses ideas from `_ensure_target_word_count()` in `report_base.py`.

### 4. PDF assembly tools

- `**render_pdf` tool**
  - Purpose: Assemble narrative text and chart images into a multi-page PDF for a single period.
  - Inputs:
    - `category`, `granularity`, `period_label`, `period_start`, `period_end`, `narrative_text`, `chart_image_paths`, `output_dir`.
  - Output:
    - `pdf_path` string.
  - Implementation:
    - Wrap `pdf_utils.create_text_page()` and `pdf_utils.save_pdf()` – first page is narrative; subsequent pages embed charts.
- `**bundle_stage_pdfs` tool (optional)**
  - Purpose: Combine multiple period PDFs for a stage (e.g., all weekly PDFs for Q1) into a single bundle per category.
  - Inputs:
    - List of `pdf_paths`, bundle name.
  - Output:
    - Path to a merged PDF.

## Node-by-node flow for one period

For each period in a stage, LangGraph will orchestrate nodes roughly as follows:

1. `**build_sql_query` node**
  - Calls `sql_query_generator` with category and period range.
  - Outputs `sql`.
2. `**read_transactions` node**
  - Calls `sql_execute` to fetch rows.
  - If result set is empty, emits a minimal narrative and skips to `assemble_pdf` with an informative “no data” message.
3. `**compute_analytics` node**
  - Calls `aggregate_metrics` and `compute_period_stats` to transform raw rows into KPIs and tables.
  - Output is a structured dict used by both charting and narrative nodes.
4. `**generate_charts` node**
  - Calls `build_charts` with category, period_label, and stats.
  - Returns list of saved chart paths and any recommended captions.
5. `**generate_narrative` node**
  - Calls `generate_narrative` (LLM) with category, period meta, KPIs, and chart descriptions.
  - Optionally runs through `expand_narrative_to_word_target` to hit ~1000 words.
6. `**assemble_pdf` node**
  - Calls `render_pdf` with narrative + charts + metadata.
  - Emits `pdf_path` and summary metadata (e.g., key KPIs) to the graph state.

## Graph state and transitions

- **State contents** (per run):
  - `category`
  - `requested_granularities` (list) or `all_granularities=True`
  - `current_stage` (one of the granularities or `done`)
  - `date_range` (global)
  - `periods` (list of remaining periods for the stage)
  - `generated_reports` (list of `{stage, period_label, pdf_path, kpis}`)
- **Stage flow**:
  - `start` initializes `state.current_stage` and `state.date_range`.
  - `determine_stage` sets or advances `current_stage`.
  - `generate_periods` populates `state.periods`.
  - `for_each_period` processes each period and appends outputs to `generated_reports`.
  - `advance_stage` either loops back or ends.

## Integration with existing code

- Use the logic in:
  - `[tools/data_generation/report_generation/data_access.py](tools/data_generation/report_generation/data_access.py)`
  - `[tools/data_generation/report_generation/time_windows.py](tools/data_generation/report_generation/time_windows.py)`
  - `[tools/data_generation/report_generation/report_base.py](tools/data_generation/report_generation/report_base.py)`
  - Category-specific modules under `tools/data_generation/report_generation/`
- Wrap these as internal Python tools that LangGraph nodes call rather than rewriting logic in LLM tools.
- Keep SQL queries parameterized and schema-aware to avoid brittle free-form SQL from the LLM.

## Validation and observability

- Before rolling out end-to-end, validate nodes independently:
  - Unit tests for each tool function (SQL generator, aggregator, chart builder, narrative length enforcement, PDF assembler).
  - A small LangGraph integration test that runs a single category for a narrow date range and verifies that:
    - All expected nodes execute.
    - A PDF file is created for each period.
- Add minimal logging at node boundaries (e.g., which periods were generated, how many rows of data, where PDFs were written).

## Next steps

1. Define the concrete tool interfaces (Python functions, input/output schemas) matching the above descriptions.
2. Extend your existing LangGraph configuration (parallel to the RAG graph) with a new `report_graph` implementing the node/edge structure.
3. Add configuration options to choose between RAG QA mode and reporting mode in your main entrypoint.
4. Add documentation explaining how to trigger report generation via LangGraph, including example JSON payloads and expected outputs.
