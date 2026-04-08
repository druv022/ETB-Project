---
name: retail-report-generation-suite
overview: Design a reporting suite that generates PDF reports (with charts and ~1000-word narratives) for 8 industry-standard retail analytics categories, across multiple time granularities, using the existing transaction database.
todos:
  - id: setup-report-folder
    content: Define folder structure and shared modules for report generation under tools/data_generation/report_generation
    status: completed
  - id: implement-data-access
    content: Design and implement data_access.py to load and aggregate transaction data
    status: completed
  - id: implement-time-windows
    content: Design and implement time_windows.py to generate weekly, bi-weekly, monthly, quarterly, semi-annual, and yearly ranges
    status: completed
  - id: implement-report-base
    content: Design BaseReport and PDF rendering utilities with Seaborn/Matplotlib integration
    status: completed
  - id: sales-performance-report
    content: Plan and implement sales performance report module for all requested time granularities
    status: completed
  - id: product-category-report
    content: Plan and implement product & category performance report module
    status: completed
  - id: customer-analytics-report
    content: Plan and implement customer analytics report module
    status: completed
  - id: promotions-pricing-report
    content: Plan and implement promotions & pricing report module
    status: completed
  - id: inventory-operations-report
    content: Plan and implement inventory & operations report module
    status: completed
  - id: financial-margin-report
    content: Plan and implement financial & margin report module
    status: completed
  - id: risk-fraud-report
    content: Plan and implement risk, fraud & controls report module
    status: completed
  - id: forecasting-planning-report
    content: Plan and implement forecasting & planning report module
    status: completed
  - id: cli-runner
    content: Implement run_reports.py CLI for orchestrating report generation
    status: completed
  - id: report-docs
    content: Document installation, configuration, and usage of the report generation suite
    status: completed
isProject: false
---

## Overview

We will design a modular Python-based reporting framework under `tools/data_generation/report_generation` that reads from the existing transaction database (and related CSVs), computes aggregates for different time granularities (weekly, bi-weekly, monthly, quarterly, semi-annual, annual), and generates **PDF reports** with **Seaborn/Matplotlib** charts and ~1000-word narratives for each **category × period**.

## High-level architecture

- **Data source layer**
  - Reuse the existing generated transaction data (`transaction_database_5yrs_full.sql` → SQLite DB) as the primary fact table.
  - Optionally join to product catalog and any dimension data (product category, store region, channel).
  - Provide a shared `data_access.py` module that:
    - Connects to SQLite (or reads from CSV extract, if preferred).
    - Exposes helper functions: `get_transactions(start_date, end_date)`, `get_aggregates(group_by, metrics, date_range)`, etc.
- **Time window utilities**
  - A `time_windows.py` utility to:
    - Define calendar logic for weekly, bi-weekly, monthly, quarterly, semi-annual, annual periods.
    - Generate ranges given a date span (e.g., full 5 years) or a requested period.
- **Reporting engine**
  - A base module `report_base.py` that:
    - Defines a `BaseReport` class with methods:
      - `prepare_data(period_range)` – fetch & aggregate.
      - `build_charts(period_range)` – return Matplotlib/Seaborn figure objects.
      - `build_narrative(period_range, stats)` – generate ~1000-word text based on metrics.
      - `render_pdf(output_path, content)` – layout text + charts into PDF.
    - Encapsulates PDF generation (e.g., Matplotlib PDF backend + ReportLab or `matplotlib.backends.backend_pdf.PdfPages`).
- **Category-specific report modules**
  - For each of the 8 categories, create a separate script/module that subclasses `BaseReport` and defines category-specific metrics, visuals, and narrative logic.
- **CLI entrypoints**
  - A top-level CLI script (e.g., `run_reports.py`) that allows:
    - Running all reports for a given time granularity.
    - Running a single category × period.
    - Choosing date ranges (default to full data span).

## Folder structure

- `tools/data_generation/report_generation/`
  - `__init__.py`
  - `data_access.py`
  - `time_windows.py`
  - `report_base.py`
  - `pdf_utils.py` (optional, if PDF layout becomes complex)
  - `sales_performance_report.py`
  - `product_category_report.py`
  - `customer_analytics_report.py`
  - `promotions_pricing_report.py`
  - `inventory_operations_report.py`
  - `financial_margin_report.py`
  - `risk_fraud_report.py`
  - `forecasting_planning_report.py`
  - `run_reports.py`

## Shared components design

- `**data_access.py`**
  - Configure DB connection to a SQLite database (importing `transaction_database_5yrs_full.sql` beforehand) or to a large CSV using pandas.
  - Functions:
    - `load_transactions(start_date, end_date, filters=None)` → `DataFrame`.
    - `aggregate_transactions(df, group_by_cols, metrics)` → aggregated `DataFrame`.
    - Optional helpers:
      - `get_store_dim()`, `get_product_dim()` from `PRODUCT_CATALOG.csv` or others to enrich data.
- `**time_windows.py`**
  - Define utilities to generate period ranges:
    - `get_weeks(start, end)`
    - `get_biweeks(start, end)`
    - `get_months(start, end)`
    - `get_quarters(start, end)`
    - `get_semiannual(start, end)`
    - `get_years(start, end)`
  - Return list of `(period_label, start_date, end_date)` tuples.
- `**report_base.py` & PDF generation**
  - `BaseReport` attributes:
    - `name`, `category`, `time_granularity`.
  - Core methods:
    - `get_periods(time_granularity, full_range)` → uses `time_windows.py`.
    - `prepare_period_stats(period)` → returns dict of KPIs for that period.
    - `generate_period_figures(period, stats)` → returns list of Matplotlib Figure objects.
    - `compose_narrative(period, stats, comparisons)` → ~1000-word narrative per period, including:
      - Overview of performance.
      - Key drivers (top stores, products, channels).
      - Comparisons vs prior periods and YoY where applicable.
    - `render_pdf_for_period(period, stats, figs, narrative, output_path)`.
  - Implement a simple PDF layout strategy:
    - Use `PdfPages` or ReportLab to:
      - First page: title, period, summary KPIs.
      - Subsequent pages: charts and narrative; tables where useful.

## Category-specific report plans

For **each category**, we will:

### 1. Sales performance report (`sales_performance_report.py`)

- **Purpose**: Show overall sales health and trends.
- **Metrics**:
  - Revenue, units sold, number of transactions, average basket value, average items per transaction.
- **Dimensions**:
  - Time (by period), store, region, channel.
- **Time granularities**:
  - Weekly, bi-weekly, monthly, quarterly, semi-annual, yearly.
- **Charts (Seaborn/Matplotlib)**:
  - Time-series line plots of revenue and units.
  - Bar charts of revenue by region/channel.
  - Histogram or KDE of basket sizes.
- **Narrative (~1000 words per period)**:
  - Describe trends vs previous period and vs same period last year.
  - Highlight top/bottom stores and channels.
  - Explain seasonality, spikes, and dips.

### 2. Product & category performance report (`product_category_report.py`)

- **Purpose**: Analyze which products/categories drive performance.
- **Metrics**:
  - Revenue, units, margin proxy (if derivable), contribution percentage.
- **Dimensions**:
  - Product, category, subcategory, region.
- **Time granularities**:
  - Weekly, monthly, quarterly, yearly (bi-weekly & semi-annual optional based on data density).
- **Charts**:
  - Pareto charts: cumulative contribution by product/category.
  - Heatmaps: category vs region performance.
  - Bar charts of top N products.
- **Narrative**:
  - Discuss top/bottom performers and concentration risk.
  - Talk about category mix shifts and new product traction.

### 3. Customer analytics report (`customer_analytics_report.py`)

- **Assumption**: `Customer_ID` in transactions is stable enough to approximate customer behavior.
- **Metrics**:
  - Number of active customers, new vs returning.
  - Purchase frequency, recency, average revenue per customer.
- **Dimensions**:
  - Customer segment (`Customer_Type`), region, channel.
- **Time granularities**:
  - Monthly, quarterly, yearly (weekly/bi-weekly may be too noisy but can be included if desired).
- **Charts**:
  - Cohort-style retention curves (approximate by first-seen month).
  - Distribution plots of spend per customer.
  - Stacked bar charts of new vs returning customers.
- **Narrative**:
  - Describe growth/decline of customer base.
  - Analyze engagement and loyalty across segments and channels.

### 4. Promotions & pricing report (`promotions_pricing_report.py`)

- **Assumption**: Use `Discount_%` to infer promotions and pricing effects.
- **Metrics**:
  - Promotional penetration (share of units/revenue sold with discount > 0).
  - Uplift in volume and impact on margin proxy during promo vs non-promo periods.
- **Dimensions**:
  - Product, category, channel, store.
- **Time granularities**:
  - Weekly, monthly, quarterly.
- **Charts**:
  - Box plots of discount levels by category.
  - Volume vs discount scatter plots.
  - Time-series of promo vs non-promo revenue.
- **Narrative**:
  - Evaluate effectiveness of discounts.
  - Identify products over-discounted or under-supported.

### 5. Inventory & operations report (`inventory_operations_report.py`)

- **Assumption**: Limited explicit inventory data, but can infer operational aspects from sales patterns.
- **Metrics**:
  - Approximate demand volatility per product/store.
  - Peak load times (transactions per hour) for staffing insights.
- **Dimensions**:
  - Store, hour-of-day, day-of-week, product category.
- **Time granularities**:
  - Weekly, monthly, quarterly.
- **Charts**:
  - Heatmaps: hour-of-day × day-of-week transaction density.
  - Line charts: store-level traffic trends.
- **Narrative**:
  - Recommend staffing and replenishment cadence based on demand patterns.

### 6. Financial & margin report (`financial_margin_report.py`)

- **Assumption**: Use `Gross_Sales_Value`, `Discount_Amount`, `Net_Sales_Value`, `Tax_amount` as financial components.
- **Metrics**:
  - Gross sales, net sales, discounts given, average discount %, tax collected.
  - A simple margin proxy: net sales minus an assumed cost (if available; otherwise focus on discount vs net).
- **Dimensions**:
  - Product, category, store, channel.
- **Time granularities**:
  - Monthly, quarterly, yearly.
- **Charts**:
  - Waterfall chart: gross → discount → net → tax.
  - Bar charts of discount % by category or store.
- **Narrative**:
  - Discuss profitability trends, discount exposure, and tax implications.

### 7. Risk, fraud & controls report (`risk_fraud_report.py`)

- **Assumption**: Use outliers/anomalies in transaction patterns as a proxy for risk.
- **Metrics**:
  - High-value transaction counts & sums.
  - Unusual refund-like patterns (if modeled) or repeated high-frequency purchases.
  - Channel- or store-level anomaly scores (simple z-score or IQR-based).
- **Dimensions**:
  - Payment method, store, channel, customer.
- **Time granularities**:
  - Weekly, monthly, quarterly.
- **Charts**:
  - Boxplots of transaction values by store/channel.
  - Time-series of high-value transaction counts.
- **Narrative**:
  - Highlight potential fraud hotspots and control considerations.

### 8. Forecasting & planning report (`forecasting_planning_report.py`)

- **Assumption**: Start with simple statistical forecasts (e.g., moving averages) rather than complex ML.
- **Metrics**:
  - Forecasted revenue/units per category/store for upcoming periods.
  - Forecast error backtests for recent periods.
- **Dimensions**:
  - Store, category, channel, time.
- **Time granularities**:
  - Monthly and quarterly forecasts primarily; yearly summaries.
- **Charts**:
  - Forecast vs actual line charts.
  - Confidence bands (e.g., ±1 standard deviation) around forecasts.
- **Narrative**:
  - Summarize expected trends and planning implications for inventory and staffing.

## Narrative & word-count strategy

- For each **category × period**:
  - Use a structured narrative template:
    1. **Executive summary** (1–2 paragraphs).
    2. **Key KPIs and trends** (2–3 paragraphs referencing charts).
    3. **Drivers and drill-downs** (2–4 paragraphs on regions, products, channels, customer segments).
    4. **Comparisons** vs previous period and previous year where data allows.
    5. **Risks & opportunities** (1–2 paragraphs).
    6. **Recommendations** (actionable next steps).
  - Automatically generate text using parameterized templates fed by computed stats, aiming for ~1000 words per report; tune wording and detail level to hit target length.

## Reporting cadence & orchestration

- `run_reports.py` will:
  - Accept CLI arguments: `--category`, `--granularity`, `--start-date`, `--end-date`, `--output-dir`.
  - For each selected period in the date range:
    - Instantiate the appropriate report class.
    - Compute stats, build charts, assemble narrative.
    - Save a PDF named like: `sales_performance_weekly_2020-W05.pdf`.
  - Provide presets to generate:
    - Full weekly suite, full monthly suite, etc.

## Validation & alignment with reconciliation

- Before finalizing production usage:
  - Use existing `reconciliation_report.csv` to validate that aggregates (units, net sales) match the reconciled transaction data.
  - Add a simple consistency check function in `data_access.py` to compare sample aggregates against reconciliation outputs.

## Documentation

- Add a `README.md` in `report_generation/` describing:
  - How to import/load the transaction DB.
  - How to install dependencies (pandas, seaborn, matplotlib, reportlab or similar).
  - Example commands to run different report suites.
  - Example screenshots of generated PDFs.
