## Report Generation Framework

This directory contains a self-contained reporting framework that builds rich PDF reports from the synthetic retail transaction database. It is **completely separate from the main `src/` application** and can be run independently.

The framework supports:

- Multiple **report categories** (sales, product/category, customer, promotions, inventory/operations, financial, risk, forecasting)
- Multiple **time granularities** (weekly, biweekly, monthly, quarterly, semiannual, yearly)
- **Charts** built with Seaborn/Matplotlib
- **Narratives** of roughly 1000 words per category × period
- **PDF output** per period and per category

---

## Data sources

All reports are built on top of the synthetic transaction data generated under:

- `tools/data_generation/Transaction_data/`
  - `transaction_database_5yrs_full.sql` – large SQL file with `INSERT` statements
  - `walmart_retail_sales_database.csv` and related CSVs in `Ed_Data/`

The reporting framework expects a **SQLite** database created from `transaction_database_5yrs_full.sql`. The first time you run a report, the framework will:

1. Look for `transaction_database_5yrs_full.db` in `tools/data_generation/Transaction_data/`
2. If it does not exist, read `transaction_database_5yrs_full.sql`
3. Execute the SQL script to create and populate the SQLite DB

---

## Module overview

All modules below live in `tools/data_generation/report_generation/`.

### Core utilities

- `data_access.py`
  - Locates and connects to the SQLite DB built from `transaction_database_5yrs_full.sql`
  - Key functions:
    - `default_db_config()` – returns a `DBConfig` with the expected DB path
    - `ensure_sqlite_db()` – builds the DB from the SQL file if needed
    - `connect()` – returns a `sqlite3.Connection`
    - `load_transactions(start_date, end_date, filters=None)` – returns a pandas `DataFrame` of rows matching the criteria
    - `aggregate_transactions(df, group_by_cols, metrics)` – computes revenue/units/transactions by the given dimensions

- `time_windows.py`
  - Defines reusable date-range generators for reporting periods:
    - `get_weeks(start, end)`
    - `get_biweeks(start, end)`
    - `get_months(start, end)`
    - `get_quarters(start, end)`
    - `get_semiannual(start, end)`
    - `get_years(start, end)`
  - Each returns a list of `Period` objects with `label`, `start`, `end`

- `pdf_utils.py`
  - Lightweight PDF helpers built on Matplotlib:
    - `create_text_page(title, narrative)` – a text-only page
    - `save_pdf(path, figures)` – writes a list of Matplotlib figures to a multi-page PDF

### Reporting base class

- `report_base.py`
  - Defines the common abstraction shared by all reports:
    - `ReportContext` – carries `label`, `start`, `end` for a single period
    - `BaseReport` – base class with:
      - `get_periods(granularity, start, end)` – uses `time_windows` to enumerate periods
      - `load_transactions_for_period(ctx, extra_filters=None)` – wraps `data_access.load_transactions`
      - Abstract hooks:
        - `compute_period_stats(ctx) -> dict`
        - `build_period_figures(ctx, stats) -> Sequence[plt.Figure]`
        - `build_period_narrative(ctx, stats) -> str`
      - `generate_for_period(ctx, granularity, output_dir)` – orchestrates stats → charts → narrative → PDF
      - `_ensure_target_word_count(text, target_words)` – expands a narrative to ~N words using an explanatory appendix

---

## Category-specific reports

Each report module subclasses `BaseReport` and implements category-specific KPIs, charts, and narrative logic.

- `sales_performance_report.py` – **Sales performance**
  - KPIs: revenue, units, transactions, average ticket, average items/basket
  - Dimensions: time, store, region, channel
  - Charts: top stores by revenue, revenue by channel

- `product_category_report.py` – **Product & category performance**
  - KPIs: revenue/units by product and category, contribution percentages
  - Charts: revenue by category, top products by revenue

- `customer_analytics_report.py` – **Customer analytics**
  - KPIs: active customers, total revenue, spend/customer, revenue by customer type
  - Charts: revenue by customer type, distribution of spend per customer

- `promotions_pricing_report.py` – **Promotions & pricing**
  - KPIs: promo unit share, promo revenue share (based on `Discount_%`)
  - Charts: revenue by category split by discounted vs non-discounted

- `inventory_operations_report.py` – **Inventory & operations**
  - KPIs: transaction density by hour-of-day and day-of-week
  - Charts: heatmap of transactions by (day-of-week, hour)

- `financial_margin_report.py` – **Financial & margin**
  - KPIs: `Gross_Sales_Value`, `Discount_Amount`, `Net_Sales_Value`, `Tax_amount`
  - Charts: simple waterfall of gross → discounts → net → tax

- `risk_fraud_report.py` – **Risk, fraud & controls**
  - KPIs: top 1% transactions by `Total_Value` (threshold & list)
  - Charts: histogram of highest-value transactions

- `forecasting_planning_report.py` – **Forecasting & planning**
  - KPIs: daily revenue history, 7-day moving average baseline
  - Charts: actual revenue vs 7-day moving average

---

## Workflow-style orchestration

Beyond single-report scripts, the framework includes a workflow-style orchestrator that behaves like a LangGraph graph but is implemented as plain Python functions.

### Orchestrator: `workflow_graph.py`

- **Data structures**
  - `Period` – `label`, `start`, `end`
  - `ReportState` – holds:
    - `category`
    - `date_start`, `date_end`
    - `requested_granularities` (optional list)
    - `current_stage` (current granularity or `None`)
    - `periods` – list of `Period` objects for current stage
    - `current_period_index`
    - `generated_reports` – list of `{stage, period_label, start, end, pdf_path}`
    - `output_dir` – where PDFs and charts will be written
    - `narrative_backend` – narrative engine (`deterministic`, `llm`, or `llm_with_fallback`)
    - `llm_model` – optional model name for the LLM backend

- **Node-like functions**
  - `determine_stage(state)` – set or advance the current granularity (`weekly → biweekly → monthly → quarterly → semiannual → yearly`)
  - `generate_periods(state)` – fills `state.periods` with `Period` objects for the chosen stage, using `time_windows`
  - `has_more_periods(state)` – `True` if unprocessed periods remain
  - `build_sql_for_current_period(state)` – constructs a parametrised SQL query for the current period
  - `process_current_period(state)` – executes the full pipeline:
    1. Execute SQL and load a DataFrame
    2. Compute category-specific stats
    3. Generate charts and save PNGs
    4. Generate a ~1000-word narrative
    5. Assemble a multi-page PDF
    6. Append entry to `state.generated_reports`
  - `run_workflow(category, start_date, end_date, requested_granularities=None, output_dir=None) -> ReportState`
    - High-level entrypoint that loops over all stages and periods, calling the functions above.

### Low-level workflow tools

To keep orchestration modular and reusable, the workflow uses dedicated helper modules:

- `tools_sql.py`
  - `SQLQuery(text, params)` – dataclass for parametrised SQL
  - `generate_sql_query(category, period_start, period_end, dimensions=None, metrics=None)` – builds a safe `SELECT * FROM transactions WHERE Transaction_Date BETWEEN :start_date AND :end_date`
  - `execute_sql(query: SQLQuery) -> pd.DataFrame` – runs the query using the reporting SQLite DB

- `tools_analytics.py`
  - `aggregate_metrics(df, group_by_cols, metrics)` – thin wrapper over `data_access.aggregate_transactions`
  - `compute_period_stats(category, period_label, period_start, period_end)` – delegates to the matching report implementation (`SalesPerformanceReport`, etc.)

- `tools_charts.py`
  - `build_charts(category, period_label, period_start, period_end, stats, output_dir) -> list[Path]`
    - Calls the report’s `build_period_figures`
    - Saves each figure as a PNG under `output_dir`

- `tools_narrative.py`
  - `generate_narrative(category, period_label, period_start, period_end, stats, target_words=1000, backend="deterministic", llm_model=None, granularity=None) -> str`
    - Uses the report’s `build_period_narrative` by default
    - Optionally calls an LLM via `llm_client.generate_report_narrative` when `backend` is `llm` / `llm_with_fallback`, with automatic fallback to the deterministic narrative

- `llm_client.py`
  - `LLMConfig` – configuration for the narrative LLM backend, driven by `llm_config.yaml` under this directory, with environment overrides (`REPORT_LLM_BACKEND`, `REPORT_LLM_MODEL`, `REPORT_LLM_API_BASE`, `REPORT_LLM_API_KEY_ENV`)
  - `summarise_stats_for_llm(stats, max_rows=5)` – converts mixed stats (scalars, dicts, DataFrames, Series) into a compact JSON-serialisable structure
  - `generate_report_narrative(...)` – calls a reasoning-capable chat model to produce an insight-focused narrative; supports:
    - `openai` (default) – standard OpenAI API
    - `openrouter` – OpenRouter via OpenAI-compatible HTTP API
    - `ollama` – local Ollama server for on-device models

- `llm_config.yaml`
  - YAML configuration file that selects the LLM provider and model for reporting narratives, for example:
    - `backend: openai`, `model: gpt-4o-mini`
    - `backend: openrouter`, `model: openrouter/your-model`, `api_base: https://openrouter.ai/api/v1`, `api_key_env: OPENROUTER_API_KEY`
    - `backend: ollama`, `model: llama3`, `api_base: http://localhost:11434`

- `tools_pdf.py`
  - `render_pdf(category, granularity, period_label, period_start, period_end, narrative_text, chart_image_paths, output_dir) -> Path`
    - First page: narrative (via `create_text_page`)
    - Subsequent pages: each chart image embedded on its own page
    - Writes a single PDF to `output_dir`

---

## Execution entrypoints

The recommended way to run reports is via the workflow-style entrypoint:

### 1. Workflow-style multi-granularity entrypoint

File: `run_report_graph.py`

This uses `workflow_graph.run_workflow()` to run the entire multi-stage pipeline. It behaves like a LangGraph graph but is implemented as plain Python for simplicity.

**Example: run monthly and quarterly sales reports for full year 2020**

```bash
PYTHONPATH=. python tools/data_generation/report_generation/run_report_graph.py \
  --category sales \
  --granularities monthly quarterly \
  --start-date 2020-01-01 \
  --end-date 2020-12-31 \
  --output-dir tools/data_generation/report_generation/output
```

This will:

- Use **monthly** as the first stage:
  - Build periods (Jan–Dec 2020)
  - Generate PDFs for each month
- Then use **quarterly** as the second stage:
  - Build Q1–Q4 2020 periods
  - Generate PDFs for each quarter
- Print a summary of generated reports to stdout

If you omit `--category`, the workflow will run **all supported categories** for the selected date range (and granularities, if provided).

If you omit `--granularities`, the workflow will run all supported stages in order (`weekly → biweekly → monthly → quarterly → semiannual → yearly`).

### 2. LLM-backed narratives (optional)

The workflow entrypoint supports a reasoning LLM for narrative generation:

```bash
PYTHONPATH=. REPORT_LLM_BACKEND=llm REPORT_LLM_MODEL=gpt-4o \
python tools/data_generation/report_generation/run_report_graph.py \
  --category sales \
  --granularities monthly \
  --start-date 2020-01-01 \
  --end-date 2020-03-31 \
  --narrative-backend llm_with_fallback \
  --output-dir tools/data_generation/report_generation/output
```

- `--narrative-backend`:
  - `deterministic` (default) – uses the built-in report narrative logic only.
  - `llm` / `llm_with_fallback` – calls an LLM via `llm_client.generate_report_narrative` and falls back to deterministic narratives on error.
- `--llm-model` (optional) – override the default model name from `REPORT_LLM_MODEL` / `OPENAI_MODEL`.

Because the reporting data is synthetic, these LLM calls are safe to run locally as long as you configure the appropriate API key (for example, `OPENAI_API_KEY`) in your environment.

---

## Environment and dependencies

From the project root:

1. Create and activate a virtual environment.
2. Install core dependencies:

```bash
pip install -r requirements.txt
```

Make sure the environment includes at least:

- `pandas`
- `matplotlib`
- `seaborn`

If you want to run tests related to reporting:

```bash
PYTHONPATH=. pytest tests/test_report_*.py tests/test_report_workflow_tools.py
```

---

## Extending the framework

To add a new report category:

1. **Create a new report module**
   - Add `my_new_report.py` that subclasses `BaseReport` and implements:
     - `compute_period_stats`
     - `build_period_figures`
     - `build_period_narrative`

2. **Register the report with the tools**
   - Update the `CATEGORY_REPORT_MAP` in:
     - `tools_analytics.py`
     - `tools_charts.py`
     - `tools_narrative.py`

3. **Update entrypoints**
   - Add the new category choice to `run_report_graph.py`.

4. **Add tests**
   - Mirror the patterns in:
     - `tests/test_report_base_and_sales.py`
     - `tests/test_report_workflow_tools.py`

With these steps, the new report type will automatically participate in both the batch-style and workflow-style reporting flows.
