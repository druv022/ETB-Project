---
name: dual retriever integration
overview: Add a single-query meta-retriever that merges results from text and caption FAISS stores, wire it into the main app pipeline, and cover behavior with tests and README updates.
todos:
  - id: add-dual-retriever
    content: Create DualRetriever adapter with invoke(query), merge, dedupe, and k cap behavior.
    status: completed
  - id: export-retriever-api
    content: Expose DualRetriever from retrieval package exports for clean imports.
    status: completed
  - id: wire-main-dual-flow
    content: Update etb_project.main to build text/caption stores and pass DualRetriever into build_rag_graph.
    status: completed
  - id: test-dual-retriever
    content: Add unit tests for combine/dedupe/order/empty/cap scenarios.
    status: completed
  - id: test-main-integration
    content: Add or update tests verifying main uses dual-store pipeline and remains compatible with graph flow.
    status: completed
  - id: update-readme
    content: Revise README workflow docs to describe single-query dual-vector retrieval behavior.
    status: completed
  - id: validate-quality
    content: Run targeted tests and lint checks for edited files and address any regressions.
    status: completed
isProject: false
---

# Dual Retriever Main Pipeline Plan

## Goal

Enable `etb_project.main` to issue one query across both text and caption vector stores while preserving compatibility with `build_rag_graph(...)` (which expects a single retriever object exposing `invoke(query) -> list[Document]`).

## Implementation Approach

- Add a retrieval adapter in `src/etb_project/retrieval/` (for example `dual_retriever.py`) that:
  - Accepts two retrievers (`text_retriever`, `caption_retriever`).
  - Exposes a single `invoke(query: str)` method.
  - Merges results from both retrievers.
  - De-duplicates documents using stable keys (`page_content` + selected metadata fields like `source`, `page`, and optional image path) to avoid repeated context.
  - Applies a deterministic ordering strategy (e.g., keep text results first then unseen caption results, or weighted interleave) and truncates to a configured `k_total`.
- Export the new adapter through `src/etb_project/retrieval/__init__.py` so main can import it cleanly.

## Main Pipeline Wiring

- Update `src/etb_project/main.py` to switch from the single-store path (`load_pdf` + `process_documents`) to the dual-store pipeline using `process_pdf_to_vectorstores(...)`.
- Build per-store retrievers with compatible `k` values.
- Instantiate `DualRetriever` and pass it as the `retriever` argument to `build_rag_graph(...)`.
- Keep existing behavior for both modes:
  - configured one-shot query (`config.query`)
  - interactive loop
- Ensure logging clearly states that dual vector retrieval is active and how many docs are returned after merge.

## Test Plan

- Add focused unit tests for `DualRetriever` (new test module under `tests/`):
  - returns combined docs from both retrievers for one query.
  - removes duplicates correctly.
  - preserves deterministic order.
  - handles empty result sets from one or both retrievers.
  - respects global cap (`k_total`).
- Extend `tests/test_retrieval_process.py` only where necessary for integration boundaries (if any new helper wiring is added).
- Add/update tests around main wiring (new or existing main tests) to assert:
  - dual vectorstore builder function is called.
  - graph receives a retriever that supports `invoke` and returns merged docs.
  - both one-shot and interactive paths still execute correctly.

## Documentation Updates

- Update `README.md` run-flow sections to reflect that the default app path now uses dual retrieval (text + captions) via one query.
- Document how merge behavior works at a high level (dedupe + ordering + cap), and mention that caption index may be empty when no captions are generated.
- Keep examples consistent with current command usage (`python -m etb_project.main`).

## Validation

- Run targeted tests first (`tests/test_retrieval_process.py`, new dual retriever tests, and any main/graph tests impacted).
- Run the broader test suite if time permits.
- Confirm lint diagnostics for changed files and resolve newly introduced issues.
