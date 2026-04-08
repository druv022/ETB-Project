---
name: BM25 plan gap review
overview: The BM25 keyword plan is directionally sound and aligned with the ensemble doc, but it omits several implementation prerequisites, readiness/manifest edge cases, and atomicity details that will matter once you implement against the current codebase.
todos:
  - id: doc-prereq
    content: Add explicit dependency on ensemble+rerrank pipeline + implementation order to BM25 plan
    status: pending
  - id: doc-readiness-manifest
    content: Document hybrid readiness rules, manifest merge on append, and atomic persist scope
    status: pending
  - id: doc-api-contract
    content: Note RetrieveRequest.k / OpenAPI migration and orchestrator default for strategy
    status: pending
isProject: false
---

# Gap analysis: [retrieval-keyword-bm25.md](docs/plans/retrieval-keyword-bm25.md)

## What is already solid

- Clear **non-goals** (no ES, in-process, MVP tokenization).
- **Artifact layout** (`sparse/*.jsonl`, `version.txt`) and **manifest fields** (`sparse_backend`, `sparse_version`) are actionable.
- **Query for BM25** = user query (not HyDE) matches the ensemble doc’s rerank rule and avoids subtle bugs.
- **Strict hybrid** vs silent degrade is an explicit product choice (good to lock before coding).
- **Transactional JSONL** (temp + rename) is called out under risks.

## Gaps and mismatches

### 1. Prerequisite: global pipeline does not exist yet

The plan assumes steps 2–4 of the “global retrieve pipeline” (multi-head fetch → RRF → rerank). Today, `[RetrieverServiceState.retrieve](src/etb_project/api/state.py)` only builds two FAISS retrievers and `[DualRetriever](src/etb_project/retrieval/dual_retriever.py)` merges with `k_total=k`—no `k_fetch`, no RRF, no rerank.

**Gap:** The doc should state explicitly that BM25 heads are **blocked on** (or shipped in the same change set as) `[retrieval-ensemble-rerank.md](docs/plans/retrieval-ensemble-rerank.md)` + `[run_retrieval](docs/plans/retrieval-ensemble-rerank.md)` wiring; otherwise implementers may add `Bm25DualSparseRetriever` with nowhere to plug it in.

### 2. `RetrieveRequest.k` semantics vs current API

`[RetrieveRequest](src/etb_project/api/schemas.py)` still describes `k` as *per sub-retriever* with merged total up to `2*k`. The BM25 plan (and ensemble plan) redefine `k` as **final** top-k after ensemble + rerank.

**Gap:** The plan should call out a **contract migration**: update field description, tests (e.g. `[tests/test_api_retriever.py](tests/test_api_retriever.py)`), and any operator docs when the pipeline lands—otherwise the BM25 section’s HTTP notes are easy to miss.

### 3. Readiness and `/v1/ready` vs strict hybrid

`[FaissDualVectorStoreBackend.is_ready](src/etb_project/vectorstore/faiss_backend.py)` only checks manifest + `text/` + `captions/`. Under **strict hybrid**, you could report **ready** while `sparse/` is missing and then **503** on retrieve.

**Gap:** Decide and document: extend `is_ready` when `ETB_RETRIEVE_STRATEGY=hybrid` (or when manifest says `sparse_backend`), vs keep liveness separate from “hybrid-complete”. Today there is no `ETB_RETRIEVE_STRATEGY` in `[RetrieverAPISettings](src/etb_project/api/settings.py)`—that’s another missing touchpoint in the plan.

### 4. Manifest preservation on append

`[append_to_and_persist_index_for_pdfs](src/etb_project/vectorstore/indexing_service.py)` rebuilds the manifest via `IndexManifest.create(...)` **without** copying hypothetical future fields (`sparse_backend`, `sparse_version`) from `existing_manifest`.

**Gap:** The plan should require: on append, **merge** sparse metadata from the old manifest and re-export JSONL from the **full** merged corpus (as the plan already suggests), so hybrid indices don’t silently lose sparse flags after an incremental index job.

### 5. Atomicity scope (FAISS + sparse)

Sparse export is scoped to `indexing_service.py` after FAISS persist; `backend.persist` only writes FAISS + manifest.

**Gap:** Clarify desired behavior if export fails after FAISS wrote to disk (partial index). Options: wrap in a higher-level “publish” that writes sparse to temp then commits manifest last, or document acceptable window + recovery (re-run index).

### 6. Empty or tiny caption corpus

The codebase already has “empty caption store” behavior in comments in `[indexing_service.py](src/etb_project/vectorstore/indexing_service.py)`. For BM25, an empty `captions_corpus.jsonl` (or all empty strings) may break or no-op `BM25Okapi`.

**Gap:** Specify: **omit** `bm25_caption` head when corpus has zero tokenizable docs vs build degenerate index; and how RRF behaves when only one sparse head exists (ensemble doc allows omitting heads).

### 7. `doc_id` vs RRF dedupe key

JSONL `doc_id` is specified for stability; RRF dedupe in the ensemble plan uses `(page_content, source, page, path)` (or `child_id`).

**Gap:** Clarify that `doc_id` is primarily for **traceability / rebuild**, not the fusion key, unless you intentionally align them—avoids confusion during debugging when ids and keys diverge.

### 8. Local CLI / `ETB_RETRIEVER_MODE=local`

`[main.py](src/etb_project/main.py)` uses local `DualRetriever` and never calls the HTTP retriever pipeline.

**Gap:** Either state **explicit non-goal** (hybrid only via Retriever API) or note that local mode stays dense-only until duplicated—so expectations match the “only inside Retriever Docker” line.

### 9. Orchestrator payload

The plan says extend `[RemoteRetriever](src/etb_project/retrieval/remote_retriever.py)` to pass `strategy`. Also decide defaults: if orchestrator omits `strategy`, server uses `ETB_RETRIEVE_STRATEGY`; document that **omission ≠ hybrid** (safe default).

### 10. Minor cross-references

- **RRF head order** for tie-breaks lives only in the ensemble doc (`HEAD_ORDER`); BM25 plan could one-line point to it.
- **Hierarchical `child_id` dedupe** in the ensemble doc is stricter than BM25’s reference to `_doc_key` only—worth a footnote “see ensemble doc when hierarchy is enabled.”

---

## Summary


| Area              | Issue                                                                   |
| ----------------- | ----------------------------------------------------------------------- |
| Sequencing        | BM25 assumes ensemble/rerank pipeline that is not implemented yet       |
| API contract      | `k` and OpenAPI text need updating when pipeline changes                |
| Readiness         | `is_ready` vs strict hybrid completeness not specified                  |
| Append path       | New manifest fields must survive `append_to_and_persist_index_for_pdfs` |
| Persist atomicity | FAISS vs sparse failure ordering unclear                                |
| Edge cases        | Empty caption BM25 corpus / head omission                               |
| Identity          | `doc_id` role vs RRF key                                                |
| Scope             | Local CLI vs Docker-only hybrid                                         |


No code changes were made; this is a review-only assessment.
