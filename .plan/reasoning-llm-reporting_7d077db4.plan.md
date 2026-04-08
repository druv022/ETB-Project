---
name: reasoning-llm-reporting
overview: Introduce a reasoning LLM-backed narrative generator into the existing reporting framework while keeping the current deterministic pipeline as a fallback.
todos:
  - id: analyze-current-narrative-flow
    content: Confirm and document how stats and deterministic narratives are currently produced and wired into PDFs for each category and period.
    status: completed
  - id: design-llm-config-and-entrypoints
    content: Design configuration options and CLI flags for selecting narrative backend and model, and thread them through workflow state.
    status: completed
  - id: implement-llm-client-and-prompts
    content: Create llm_client module with provider-agnostic interface and well-structured prompts using stats and context.
    status: completed
  - id: integrate-llm-into-tools-narrative
    content: Update tools_narrative.generate_narrative to support deterministic and LLM-backed modes with safe fallback behavior.
    status: completed
  - id: update-tests-and-docs
    content: Add unit tests for LLM and deterministic paths and extend the report_generation README with configuration and usage instructions.
    status: completed
isProject: false
---

# Reasoning LLM Integration for Report Narratives

### Goals

- **Primary**: Use a reasoning-capable LLM to generate richer, insight-focused narratives for each report (category × period) based on computed statistics and context.
- **Secondary**: Keep the existing deterministic narratives as a safe fallback and allow easy switching between backends without disrupting the current workflow or tests.

### 1. Understand the current reporting & narrative architecture

- **Review core flow**:
  - `BaseReport.generate_for_period()` in `[tools/data_generation/report_generation/report_base.py](tools/data_generation/report_generation/report_base.py)` orchestrates stats → narrative → figures → PDF.
  - The workflow pipeline in `[tools/data_generation/report_generation/workflow_graph.py](tools/data_generation/report_generation/workflow_graph.py)` uses helper tools:
    - `compute_period_stats` → `[tools_analytics.py](tools/data_generation/report_generation/tools_analytics.py)`
    - `build_charts` → `[tools_charts.py](tools/data_generation/report_generation/tools_charts.py)`
    - `generate_narrative` → `[tools_narrative.py](tools/data_generation/report_generation/tools_narrative.py)`
    - `render_pdf` → `[tools_pdf.py](tools/data_generation/report_generation/tools_pdf.py)`
- **Current narrative behavior**:
  - `tools_narrative.generate_narrative(category, period_label, period_start, period_end, stats, target_words=1000)` delegates to the report class’s `build_period_narrative` then uses `BaseReport._ensure_target_word_count` to pad to ~1000 words.
  - Each concrete report (e.g. `[customer_analytics_report.py](tools/data_generation/report_generation/customer_analytics_report.py)`) implements domain-specific `compute_period_stats`, `build_period_figures`, and `build_period_narrative` using deterministic logic.

### 2. Define LLM integration strategy & configuration

- **Integration point**:
  - Keep report classes deterministic; introduce the reasoning LLM in `tools_narrative.generate_narrative`, which already sits between stats and narrative text in the workflow.
  - Preserve the existing behavior as the **default** or fallback path.
- **Backend abstraction**:
  - Add a new module `[tools/data_generation/report_generation/llm_client.py](tools/data_generation/report_generation/llm_client.py)` that exposes a small interface, for example:
    - `generate_report_narrative(category, ctx, stats, target_words, style, model, backend) -> str`
  - Inside `llm_client`, support a pluggable provider (e.g. OpenAI, Anthropic, or local) selected via environment variables or simple config (e.g. `REPORT_LLM_BACKEND`, `REPORT_LLM_MODEL`, and API keys).
- **Config surface**:
  - Extend the workflow entrypoints `[run_report_graph.py](tools/data_generation/report_generation/run_report_graph.py)` and `run_reports.py` to accept optional flags, such as:
    - `--narrative-backend {deterministic,llm,llm_with_fallback}`
    - `--llm-model MODEL_NAME` (overrides default model if provided)
  - Thread these options into the workflow state (e.g. add `narrative_backend`/`llm_model` to `ReportState` in `workflow_graph.py`) and into `tools_narrative.generate_narrative`.

### 3. Design prompts and data shaping for the reasoning LLM

- **Input content**:
  - Construct a compact JSON-serializable summary from `stats` for each report category:
    - Extract scalar KPIs (e.g. totals, counts, averages) directly.
    - For DataFrames/Series (e.g. revenue by customer type, spend distributions in `[customer_analytics_report.py](tools/data_generation/report_generation/customer_analytics_report.py)`), aggregate into:
      - Top-N categories/segments with values and shares.
      - Basic distribution descriptors (min/median/percentiles) to avoid dumping entire tables.
  - Optionally include the **existing deterministic narrative** (from `report.build_period_narrative`) as a baseline reference that the LLM can refine and expand.
- **Prompt structure**:
  - Create a reusable prompt template in `llm_client.py` with:
    - System message: role and style (e.g. retail analytics consultant, clear, non-technical, action-oriented).
    - Context section: category, date range, granularity, and data dictionary.
    - Instructions: ask for an executive summary, key drivers of change, anomalies/outliers, and 2–4 concrete recommendations.
    - Constraints: approximate target word count, neutral tone, avoid hallucinating unseen data, call out uncertainty.
  - Tailor small category-specific guidance (e.g. for risk/fraud emphasise thresholds/outliers; for forecasting emphasise trend vs baseline).
- **Reasoning emphasis**:
  - Explicitly instruct the model to “think step-by-step” and reason from the provided KPIs and distributions before drafting text (for reasoning-style models, this can be hidden internal reasoning if supported by the API).

### 4. Implement LLM-backed narrative path in `tools_narrative`

- **Extend `generate_narrative` signature/behavior**:
  - Preserve the existing function signature for backward compatibility and add optional kwargs or a small config object (e.g. `backend="deterministic"`, `llm_model=None`).
  - Inside `generate_narrative`:
    1. Resolve the report class (`CATEGORY_REPORT_MAP`) and build a `ReportContext`.
    2. Compute the **baseline narrative** via `report.build_period_narrative(ctx, stats)`.
    3. If `backend == "deterministic"`, keep current behavior (baseline narrative → `_ensure_target_word_count`).
    4. If `backend` is an LLM mode:
      - Pre-process `stats` into the compact summary structure.
      - Call `llm_client.generate_report_narrative(...)` with:
        - category, period label, start/end dates, granularity (if available), processed stats, baseline narrative (optional), style hints, target word count.
      - Optionally run `_ensure_target_word_count` as a soft guard if the LLM output is far from the target length.
    5. If the LLM call fails (exception, timeout, validation error), log/print a warning and fall back to the deterministic path so reports always succeed.

### 5. Thread configuration through the workflow & CLIs

- **Workflow state changes**:
  - In `ReportState` (in `[workflow_graph.py](tools/data_generation/report_generation/workflow_graph.py)`), add optional keys like `narrative_backend` and `llm_model`.
  - Update `run_workflow(...)` to accept these parameters and store them in the initial `state`.
  - Pass them down to `process_current_period` so that the call to `generate_narrative` includes the chosen backend/model.
- **CLI surfaces**:
  - In `[run_report_graph.py](tools/data_generation/report_generation/run_report_graph.py)` and the single-report script (`run_reports.py`):
    - Add argparse options for selecting the narrative backend and model.
    - Document defaults (e.g. `deterministic` if no flags, `llm_with_fallback` once stable).
  - Ensure both entrypoints behave consistently so you can test the LLM path in either mode.

### 6. Implement LLM client & provider abstraction

- **Core client** (`llm_client.py`):
  - Define a small `LLMConfig` dataclass (backend, model, api_base, api_key_env_var, timeout, max_tokens).
  - Implement a high-level function `generate_report_narrative(...)` that:
    - Builds the prompt messages from the structured stats and context.
    - Calls the selected provider’s API (OpenAI, Anthropic, etc.) using the config.
    - Performs basic safety checks: non-empty response, reasonable length, plain-text.
  - Abstract provider-specific details into internal helper functions so future backends can be added without touching the narrative logic.
- **Configuration & secrets**:
  - Expect API keys via environment variables (e.g. `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`), not hard-coded.
  - Optionally allow a simple `.env` or config file if that fits the rest of the project.

### 7. Testing strategy for deterministic & LLM modes

- **Unit tests (mocked LLM)**:
  - Add tests under `tests/` (e.g. `tests/test_report_workflow_tools.py` already exists) to cover:
    - `tools_narrative.generate_narrative` in deterministic mode (regression for current behavior).
    - LLM mode with the LLM client mocked to return a fixed narrative:
      - Verify that the function routes through `llm_client` when backend is set.
      - Verify fallback to deterministic narrative when the LLM client raises an exception.
    - Workflow-level test: `run_workflow` using an injected backend config to ensure it calls the LLM path without changing the shape of `generated_reports`.
- **Prompt/data shaping tests**:
  - Add lightweight tests for the helper that converts `stats` (with DataFrames/Series) into compact summaries to ensure stable, predictable structures across categories.

### 8. Documentation & usage examples

- **Update report framework README**:
  - In `[tools/data_generation/report_generation/README.md](tools/data_generation/report_generation/README.md)`, add a section describing:
    - The new LLM narrative backend.
    - Required environment variables and config options.
    - Example commands for running with LLM-based narratives, e.g.:
      - `PYTHONPATH=. REPORT_LLM_BACKEND=llm REPORT_LLM_MODEL=o1 PYTHONWARNINGS=ignore python tools/data_generation/report_generation/run_report_graph.py ...`
    - Notes on data privacy (synthetic data vs real data) and cost/latency trade-offs.
- **Explain fallback behavior**:
  - Clearly state that if the LLM is misconfigured or unreachable, the system automatically falls back to deterministic narratives so batch jobs still complete.

### 9. Optional future enhancements

- **Richer multi-period reasoning**:
  - Extend the pipeline so that the LLM can see multiple periods at once (e.g. month-over-month trends within a single PDF, or a separate “Year-in-review” narrative that reasons across all months).
- **LangGraph/agentic orchestration**:
  - Wrap the existing workflow nodes (`determine_stage`, `generate_periods`, `process_current_period`) in an actual LangGraph graph, letting a reasoning LLM decide which periods or categories to prioritise, or which follow-up reports to generate.
- **Structured outputs**:
  - Move from free-text output to structured JSON (e.g. `{"executive_summary": "...", "drivers": [...], "risks": [...], "actions": [...]}`), then render those sections separately in PDFs for more consistent layouts.
