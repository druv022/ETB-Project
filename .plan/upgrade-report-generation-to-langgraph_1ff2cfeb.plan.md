---
name: upgrade-report-generation-to-langgraph
overview: Convert the existing reporting workflow under tools/data_generation/report_generation from a hand-rolled Python orchestrator into a first-class LangGraph graph, fully integrated with Studio, while preserving the current CLI entrypoints.
todos:
  - id: define-state-model
    content: Finalize a LangGraph/Studio-friendly ReportState representation (serializable fields, normalized dates/paths).
    status: completed
  - id: build-report-graph
    content: Implement a StateGraph[ReportState] wiring determine_stage, generate_periods, process_current_period, and check_more_periods with loops for stages and periods.
    status: in_progress
  - id: studio-entry-report
    content: Create a Studio entry function (report_app) and register it in langgraph.json so the report graph is visible in LangGraph Studio.
    status: completed
  - id: cli-adapt-langgraph
    content: Update run_report_graph.py to invoke the compiled LangGraph report graph, preserving the current CLI interface.
    status: completed
  - id: tests-parity
    content: Add tests to compare outputs between legacy run_workflow and the new LangGraph report graph for identical inputs.
    status: pending
  - id: docs-update-report-langgraph
    content: Update reporting and project documentation to explain the new LangGraph-based report generation and how to visualize it in Studio.
    status: pending
isProject: false
---

# Upgrade Report Generation to LangGraph

## Goals

- **Replace the manual workflow loop** in `workflow_graph.py` with a proper LangGraph graph (or graphs) while keeping behavior identical.
- **Expose the reporting graph(s) to LangGraph Studio** so you can visualize and debug runs.
- **Preserve existing CLIs** such as `run_report_graph.py`, adapting them to call the new compiled graph instead of the manual orchestration.
- **Keep the tools package self-contained** under `tools/data_generation/report_generation` and avoid coupling it to the main `src/` app.

## High-level design

- **State model**: Treat the existing `ReportState` in `workflow_graph.py` as the LangGraph state, using a TypedDict or Pydantic model that is serializable for Studio.
- **Graph types**:
  - Implement a primary `**StateGraph[ReportState]`** that captures the multi-granularity pipeline (stage loop + period loop).
  - Optionally provide **simpler sub-graphs** for a single granularity or single period, if useful for debugging.
- **Nodes**: Reuse existing pure functions as graph nodes wherever possible:
  - `determine_stage(state) -> state`
  - `generate_periods(state) -> state`
  - `process_current_period(state) -> state`
  - A small wrapper node around `has_more_periods(state) -> bool` for conditional routing.
- **Control flow in LangGraph**: Express the nested loops using LangGraph conditional edges and loops instead of Python `while` loops.
- **Entry surfaces**:
  - A **Studio entry function** (e.g. `report_app()`) that constructs and compiles the graph.
  - A **CLI wrapper** that instantiates inputs and calls `graph.invoke` or `graph.stream`.

## Detailed steps

### 1. Refine the state model for LangGraph

- **1.1 Extract a canonical state type**
  - In `workflow_graph.py`, pull `ReportState` into a dedicated model that is easy for LangGraph and Studio to work with (TypedDict is already present; verify it is JSON-serializable).
  - Ensure nested values like `Path`, `date`, and `DataFrame` are not stored directly in the persisted state; prefer primitives and strings for anything that will be logged to Studio.
- **1.2 Normalize non-serializable fields**
  - Convert `Path` values (e.g. `output_dir`) to strings inside the state where necessary, or keep them as `Path` but ensure they are not deeply nested in custom objects.
  - Ensure dates (`date_start`, `date_end`, `periods`) are stored as ISO strings or simple primitives when written to the state (or provide small helper conversions in nodes).

### 2. Define LangGraph nodes around existing functions

- **2.1 Wrap `determine_stage` and `generate_periods`**
  - Keep their signatures as `fn(state: ReportState) -> ReportState` so they can be used directly as state-update nodes.
  - Add lightweight logging/metadata fields in state if helpful for Studio (e.g. `last_node` string) while keeping behavior identical.
- **2.2 Wrap the period-processing logic**
  - Use `process_current_period(state) -> ReportState` as a node that:
    - Runs SQL (`execute_sql`)
    - Computes stats (`compute_period_stats`)
    - Builds charts and writes PNGs
    - Generates the narrative
    - Renders the PDF and appends to `generated_reports`.
  - Keep side-effects (file writes) as they are, documenting that this is an I/O-heavy node.
- **2.3 Represent `has_more_periods` as a condition node**
  - Create a small wrapper node, e.g. `check_more_periods(state) -> {"has_more": bool}` or just `bool` with a LangGraph conditional edge.
  - Use this in the graph to decide whether to loop back to `process_current_period` or advance the stage.

### 3. Construct the LangGraph topology

- **3.1 Choose graph flavor**
  - Use `StateGraph[ReportState]` from `langgraph.graph` so the state is a single typed dict.
- **3.2 Define nodes and edges**
  - In a new module (e.g. `tools/data_generation/report_generation/report_langgraph.py`):
    - Instantiate `builder = StateGraph(ReportState)`.
    - `builder.add_node("determine_stage", determine_stage)`.
    - `builder.add_node("generate_periods", generate_periods)`.
    - `builder.add_node("process_current_period", process_current_period)`.
    - `builder.add_node("check_more_periods", check_more_periods)` (wrapper for `has_more_periods`).
  - **Stage loop**:
    - Entry → `determine_stage`.
    - If `current_stage` is `None`, exit; otherwise, go to `generate_periods`.
  - **Period loop**:
    - From `generate_periods` → `check_more_periods`.
    - If `has_more` is `True`, go to `process_current_period`, then back to `check_more_periods`.
    - If `has_more` is `False`, go back to `determine_stage`.
  - Use `add_conditional_edges` or equivalent control-flow utilities to encode these branches.
- **3.3 Compile and export the graph**
  - Provide a factory function:
    - `def build_report_graph() -> CompiledGraph: ...` that sets up the graph and returns `builder.compile()`.

### 4. Integrate with LangGraph Studio

- **4.1 Create a Studio entry function**
  - In a Studio-facing file (e.g. `tools/data_generation/report_generation/studio_report_entry.py`), define:
    - `def report_app():` that prepares any environment/config (db paths, defaults) and returns `build_report_graph()`.
  - Ensure this entry has no required side effects beyond what is needed to compile the graph.
- **4.2 Register the graph in `langgraph.json`**
  - Add a new entry under `graphs`, for example:
    - `"report_app": "./tools/data_generation/report_generation/studio_report_entry.py:report_app"`.
  - Keep the existing `rag_app` entry untouched.
- **4.3 Define Studio input schema and defaults**
  - Decide how Studio users will provide initial state:
    - A simple dict with keys: `category`, `date_start`, `date_end`, `requested_granularities`, `output_dir`, `narrative_backend`, `llm_model`.
  - Document default values (e.g. default output directory, default narrative backend) in docstrings so Studio users know what to pass.

### 5. Adapt CLI entrypoints to use the LangGraph graph

- **5.1 Update `run_report_graph.py` to call the compiled graph**
  - Instead of calling `run_workflow(...)` directly, have it:
    - Build an initial `ReportState` from CLI args.
    - Invoke `build_report_graph()` and call `graph.invoke(initial_state)`.
    - Read `generated_reports` from the returned state and print the summary.
  - Optionally keep `run_workflow` as a thin wrapper that internally uses `graph.invoke` for backwards compatibility.
- **5.2 Keep `run_reports.py` unchanged initially**
  - Decide whether `run_reports.py` should also be LangGraph-based; if so, later wrap its single-granularity loop with a smaller graph using the same node set.

### 6. Testing and validation

- **6.1 Snapshot existing behavior**
  - Add or reuse tests (e.g. in `tests/test_report_workflow_tools.py`) that:
    - Call the old `run_workflow(...)` directly with a narrow date range and a specific category.
    - Assert on:
      - Number of generated reports.
      - Structure of entries in `generated_reports` (stage, period_label, paths).
- **6.2 Add parallel tests for the LangGraph path**
  - Add tests that:
    - Build the LangGraph via `build_report_graph()`.
    - Invoke it with the same initial state.
    - Assert that the resulting `generated_reports` matches the `run_workflow` behavior.
- **6.3 Exercise Studio-style runs**
  - (Locally, outside of tests) run `langgraph dev`, select `report_app` in Studio, and run a short workflow (e.g. a single month) to confirm the graph visualization and node sequencing match expectations.

### 7. Documentation and cleanup

- **7.1 Update the reporting README**
  - In `tools/data_generation/report_generation/README.md`, add a section:
    - Explaining that the workflow is now implemented as a LangGraph graph.
    - Showing how to:
      - Run via CLI (unchanged UX).
      - Visualize and debug via LangGraph Studio.
- **7.2 Update root README if needed**
  - Briefly mention that there is now a second Studio graph (`report_app`) for report-generation workflows.
- **7.3 Deprecate or simplify legacy APIs**
  - If appropriate, mark the direct loop-based `run_workflow` implementation as deprecated or convert it into a thin compatibility wrapper around the LangGraph graph.

## Todos

- **define-state-model**: Revisit and finalize the `ReportState` representation to be LangGraph/Studio-friendly (serializable, minimal non-primitive types).
- **build-report-graph**: Implement the `StateGraph[ReportState]` that wires `determine_stage`, `generate_periods`, `process_current_period`, and the period/stage loops.
- **studio-entry-report**: Add a Studio entry function (e.g. `report_app`) and register it in `langgraph.json`.
- **cli-adapt-langgraph**: Update `run_report_graph.py` to call the compiled LangGraph graph instead of the manual `run_workflow` loop.
- **tests-parity**: Add tests to ensure the new LangGraph-based execution path produces the same `generated_reports` as the legacy `run_workflow` implementation.
- **docs-update-report-langgraph**: Update documentation (tools README and, if needed, root README) to describe the LangGraph-based report generation and Studio visualization.
