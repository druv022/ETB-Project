# Plan: BM25 keyword retrieval (ensemble heads)

This document specifies **lexical (sparse) retrieval** for ETB-project. BM25 does **not** produce the final user-facing ordering. It contributes **two ranked lists** (`bm25_text`, `bm25_caption`) into the **global ensemble** defined in [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md).

## Goals

- Improve recall for exact terminology, acronyms, and rare tokens that dense embeddings may miss.
- Stay **free** and **in-process** (no Elasticsearch/OpenSearch required for MVP).
- Persist sparse corpora alongside existing dual FAISS indices under `vector_store_path`.
- Run **only inside the Retriever Docker** service (`etb_project.api`).

## Implementation prerequisite

BM25 heads plug into the **global ensemble pipeline** (multi-head `k_fetch` → RRF → rerank). That pipeline is specified in [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md) (`run_retrieval`, `RetrieverServiceState.retrieve` as a thin wrapper). **Ship BM25 together with that pipeline** (or after it); do not land `Bm25DualSparseRetriever` in isolation—there is no multi-head merge in the retriever API today.

## Non-goals (MVP)

- Multilingual stemming or stopword lists (optional later).
- Incremental BM25 without rebuild (rebuild on each persist is acceptable).
- Running BM25 in the orchestrator container.
- **Local CLI** (`ETB_RETRIEVER_MODE=local`, `main.py` + `DualRetriever`): hybrid / BM25 stays **retriever-HTTP-only** unless a future phase duplicates the pipeline locally.

## Global retrieve pipeline (verbatim)

Repeat this block in every retrieval plan doc for consistency.

1. **Resolve query:** Read `query` from request; apply HyDE LLM when enabled to obtain `H` (hypothetical passage) as needed for heads.
2. **Candidate generation (parallel where practical):** Each enabled **head** runs with an oversample `k_fetch` (env e.g. `ETB_RETRIEVAL_K_FETCH`, default `max(k * 5, 30)` cap ~100). Each head returns an **ordered** list of `Document` (same metadata keys as today). Tag internally with `head_id` for logging/tracing (optional metadata key `ensemble_head`, stripped before response if undesirable).
   - **Dense–query:** `embed_query(query)` → similarity search on text FAISS + caption FAISS → **two** lists.
   - **Dense–HyDE:** If `hyde_mode` is `replace`, only HyDE dense lists participate for the HyDE slots (query dense lists may be omitted). If `fuse`, both query- and `H`-embedded searches run → up to **four** dense lists (text+caption × query+HyDE).
   - **BM25:** If hybrid/strategy includes sparse: `bm25_text`, `bm25_caption` lists.
   - **Hierarchical child:** If hierarchy index present: child FAISS search (default **query embedding** for child head).
3. **Ensemble:** Apply **Reciprocal Rank Fusion** across all lists that returned at least one doc. Stable dedupe key: `DualRetriever._doc_key` `(page_content, source, page, path)` or extended key if hierarchy adds `child_id` (normative detail and **RRF head order / tie-break** → see [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md), e.g. `HEAD_ORDER`). RRF constant `ETB_RRF_K` (default 60). Output: candidate pool `C` capped by `ETB_ENSEMBLE_CAP`.
4. **Rerank (final ordering):** Score each candidate in `C` with the active **reranker** using the **user query string**. Sort descending; take top `k_return` = request `k`.
5. **Hierarchical expansion (post-rerank):** If `expand=true` and hierarchy exists: map top child hits to parents per hierarchical plan.

**Failure isolation:** If reranker fails → fall back to ensemble order truncated to `k`. If ensemble receives zero lists → 503 or empty chunks per existing API behavior.

## Technology

- **Package:** [`rank-bm25`](https://pypi.org/project/rank-bm25/) (`BM25Okapi`).
- **Tokenization:** Whitespace split + lowercasing (no extra NLP dependencies). Optional future: regex word tokens.

## On-disk artifacts

Under `vector_store_path` (e.g. `data/vector_index/`):

| Path | Content |
|------|---------|
| `sparse/text_corpus.jsonl` | One JSON object per line: `doc_id` (stable string), `text` (chunk plain text), `metadata` (dict mirroring LangChain `Document.metadata`: `source`, `page`, `path`, `start_index`, …). |
| `sparse/captions_corpus.jsonl` | Same structure for caption chunks. |
| `sparse/version.txt` | Literal `bm25_v1` (or similar) for format evolution. |

`doc_id` stability: prefer deterministic id, e.g. SHA256 of `(source, page, start_index, first_64_chars)` or explicit uuid stored at index time—useful for **export round-trips, debugging, and rebuild idempotence**. **RRF dedupe does not use `doc_id`:** fusion uses the ensemble key `(page_content, source, page, path)` or `child_id` per [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md). Keep metadata aligned so the same logical chunk fuses correctly across dense and sparse heads.

## Manifest extensions

Extend `IndexManifest` (`src/etb_project/vectorstore/manifest.py`) with optional fields:

- `sparse_backend: str | None` — e.g. `"bm25"`.
- `sparse_version: str | None` — e.g. `"bm25_v1"`.

`load()` must use `.get()` with defaults for backward compatibility.

**Append jobs:** `append_to_and_persist_index_for_pdfs` rebuilds the manifest via `IndexManifest.create(...)`. **Preserve** `sparse_backend` / `sparse_version` from `existing_manifest` when re-saving so incremental indexing does not drop hybrid metadata. Re-export full `sparse/*.jsonl` from the merged corpus on every persist.

## Readiness policy

- **`ETB_RETRIEVE_STRATEGY=dense`:** BM25 heads are **not** registered; sparse files may be absent.
- **`ETB_RETRIEVE_STRATEGY=hybrid`:** If `sparse/` is missing or corrupt → **fail retrieve with clear 503/400** (strict mode) rather than silent dense-only, so operators know the index is incomplete. Alternative (document in code comment): degrade to dense-only with `WARNING` log—pick **strict** for predictable behavior.

**Corrupt sparse:** Treat as unreadable JSONL, missing `version.txt`, or tokenization/build exceptions at load time—same strict failure as missing `sparse/`.

**`/v1/ready` vs hybrid:** Today `FaissDualVectorStoreBackend.is_ready` only checks manifest + `text/` + `captions/`. Decide explicitly: when serving hybrid (env or manifest `sparse_backend`), extend readiness to require `sparse/version.txt` + both corpus files (or equivalent), **or** document that **ready** means “FAISS loadable” and hybrid may still 503 until sparse is fixed—avoid ambiguous “ready but always failing” for operators.

**Settings:** Add `ETB_RETRIEVE_STRATEGY` to retriever settings (e.g. `RetrieverAPISettings` in `src/etb_project/api/settings.py`) alongside request override.

## Index build integration

Touchpoints:

- `src/etb_project/vectorstore/indexing_service.py` — after `build_two_vectorstores` or after `append_documents_to_faiss`, export the **same** `Document` lists written to FAISS into `sparse/*.jsonl`.
- On **append:** rebuild **full** JSONL from the merged corpus (simplest): either re-walk both FAISS docstores or maintain JSONL as authoritative and rewrite on each persist.

**Atomicity:** FAISS `save_local` and manifest write happen in `backend.persist`; sparse JSONL is separate. Prefer a **publish order** that minimizes torn state: e.g. write sparse to temp dirs + rename, then persist FAISS + manifest, **or** document recovery (“re-run index job”) if sparse write fails after FAISS succeeded. At minimum, JSONL alone must stay transactional (temp + rename).

**Empty caption corpus:** If there are zero caption chunks (or nothing tokenizable), **omit** the `bm25_caption` head from RRF (same as other disabled heads in the ensemble doc). Do not build a degenerate `BM25Okapi` on an empty corpus.

Implementation sketch:

1. `export_sparse_corpus(text_docs: list[Document], captions_docs: list[Document], root: Path) -> None`
2. `Bm25IndexBundle.load(root: Path) -> Bm25DualSparseRetriever` — reads JSONL, tokenizes, builds two `BM25Okapi` instances.

## Runtime API surface (Python)

New module `src/etb_project/retrieval/sparse_retriever.py`:

```python
class Bm25DualSparseRetriever:
    def search_text(self, query: str, k_fetch: int) -> list[Document]: ...
    def search_captions(self, query: str, k_fetch: int) -> list[Document]: ...
```

- Always use the **request `query`** string for BM25 (not HyDE `H`), unless a future flag explicitly changes this.
- Return `Document(page_content=..., metadata=...)` matching dense retrieval shape.

## Wiring in `RetrieverServiceState`

- Lazy-load `Bm25DualSparseRetriever` when strategy is hybrid and index has `sparse_backend`.
- Hold BM25 under the same `threading.RLock` as FAISS reloads, or use immutable snapshot after load (reload BM25 after `reload_after_index()`).

## HTTP / schema

- `RetrieveRequest.strategy: Literal["dense", "hybrid"] | None` — `None` → `ETB_RETRIEVE_STRATEGY` env default (`dense`).
- OpenAPI: document that `k` is the **final** top-k after ensemble+rerank; `k_fetch` is internal oversampling driven by `ETB_RETRIEVAL_K_FETCH`.

**Contract migration:** Today `RetrieveRequest.k` describes per-sub-retriever behavior and “up to 2*k merged.” When the ensemble pipeline lands, **update** the Pydantic field description, OpenAPI text, and tests (e.g. `tests/test_api_retriever.py`) so clients and operators see one definition of `k`.

## Orchestrator

- Extend `RemoteRetriever.invoke` payload to pass `strategy` when needed. **No** BM25 code in orchestrator.
- **Default:** Omitting `strategy` in the JSON body means the retriever uses `ETB_RETRIEVE_STRATEGY` (default **`dense`**)—omission must **not** imply hybrid.

## Dependencies

- Add `rank-bm25` to `requirements.txt` and `pyproject.toml`.

## Testing

- Unit: tokenization + BM25 ordering on a toy corpus.
- Unit: JSONL round-trip export id stability.
- Integration: retriever API with `strategy=hybrid` returns chunks; BM25-only head smoke (mock or small fixture index).

## Risks

- **Memory:** Full corpus in RAM for BM25; mitigate with FTS5 plan later if needed.
- **Consistency:** FAISS and JSONL drift if export fails mid-persist—use transactional write (write temp + rename) for JSONL; align with **Atomicity** under index build integration.
- **`k_fetch` vs limits:** Clamp internal `k_fetch` against server maxima (e.g. `ETB_MAX_RETRIEVE_K`, cap ~100) so oversampling cannot bypass safety limits.

## References

- `src/etb_project/retrieval/dual_retriever.py` — dedupe key.
- `src/etb_project/api/state.py` — `RetrieverServiceState`.
- `src/etb_project/vectorstore/faiss_backend.py` — index layout.
