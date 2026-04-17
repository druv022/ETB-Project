# Plan: Global ensemble (RRF) + reranker — final retrieval pipeline

This document is the **single source of truth** for how `POST /v1/retrieve` orders and truncates chunks **after** all retrieval heads run. It lives entirely in the **Retriever Docker** (`etb_project.api`).

## Goals

- Combine **all enabled heads** into one candidate pool via **Reciprocal Rank Fusion (RRF)**.
- Apply a **reranker** to the pool for final relevance ordering.
- Return top-`k` chunks to the client; then apply **hierarchical parent expansion** when configured (step 5).

## Inputs from other plans

| Head id (conceptual) | Source plan |
|---------------------|-------------|
| `dense_text_q`, `dense_caption_q` | Dense query embedding |
| `dense_text_h`, `dense_caption_h` | [retrieval-hyde.md](retrieval-hyde.md) when `fuse` or `replace` |
| `bm25_text`, `bm25_caption` | [retrieval-keyword-bm25.md](retrieval-keyword-bm25.md) when `strategy=hybrid` |
| `hier_child` | [retrieval-hierarchical.md](retrieval-hierarchical.md) when hierarchy index present |

Heads that are disabled contribute **no** list (omit from RRF sum).

## Global retrieve pipeline (verbatim)

1. **Resolve query:** Read `query` from request; apply HyDE LLM when enabled to obtain `H` (hypothetical passage) as needed for heads.
2. **Candidate generation (parallel where practical):** Each enabled **head** runs with an oversample `k_fetch` (env e.g. `ETB_RETRIEVAL_K_FETCH`, default `max(k * 5, 30)` cap ~100). Each head returns an **ordered** list of `Document` (same metadata keys as today). Tag internally with `head_id` for logging/tracing (optional metadata key `ensemble_head`, stripped before response if undesirable).
   - **Dense–query:** `embed_query(query)` → similarity search on text FAISS + caption FAISS → **two** lists.
   - **Dense–HyDE:** If `hyde_mode` is `replace`, only HyDE dense lists participate for the HyDE slots (query dense lists may be omitted). If `fuse`, both query- and `H`-embedded searches run → up to **four** dense lists (text+caption × query+HyDE).
   - **BM25:** If hybrid/strategy includes sparse: `bm25_text`, `bm25_caption` lists.
   - **Hierarchical child:** If hierarchy index present: child FAISS search (default **query embedding** for child head).
3. **Ensemble:** Apply **Reciprocal Rank Fusion** across all lists that returned at least one doc. Stable dedupe key: `DualRetriever._doc_key` `(page_content, source, page, path)` **or** `(child_id,)` when `child_id` in metadata (see hierarchical plan). RRF constant `ETB_RRF_K` (default 60). Output: ordered candidate pool `C` of size at most `ETB_ENSEMBLE_CAP` (default 80).
4. **Rerank (final ordering):** Score each candidate in `C` with the active **reranker** using the **user query string** (refined query from client, not `H` unless a future flag documents otherwise). Sort descending; take top `k_return` = request `k` (clamped by server max).
5. **Hierarchical expansion (post-rerank):** If `expand=true` and hierarchy exists: map each of the top `k_return` **child** hits to `parent_id`, fetch parent `full_text` from SQLite, **collapse** to unique parents while **preserving rerank order** (first occurrence wins), apply `ETB_PARENT_CONTEXT_CHARS` / `ETB_MAX_PARENTS` caps. Returned `page_content` is parent body. If `expand=false`, return reranked **child** chunks unchanged.

**Failure isolation:** If reranker fails → fall back to ensemble order truncated to `k`. If ensemble receives zero lists → 503 or empty chunks per existing API behavior.

## Module layout

Suggested new module: `src/etb_project/retrieval/pipeline.py`

Public entry:

```python
def run_retrieval(
    *,
    request: RetrieveRequest,
    state: RetrieverServiceState,
    settings: RetrieverAPISettings,
) -> list[Document]:
    ...
```

Responsibilities:

1. Build `list[tuple[str, list[Document]]]` — `(head_id, ranked_docs)`.
2. Call `ensemble_rrf(heads, k_rrf: int, cap: int) -> list[Document]`.
3. Call `rerank(candidates, query: str, mode: str, ...) -> list[Document]`.
4. Truncate to `k`.
5. Delegate `expand_hierarchy_if_needed(...)` to hierarchical helper.

`RetrieverServiceState.retrieve` becomes a thin wrapper that acquires lock, loads stores, and calls `run_retrieval`.

## RRF algorithm (normative)

For each head `i` with ranked list `L_i`, for each document `d` at **1-based** rank `rank(d, L_i)`:

\[
\text{RRF}(d) = \sum_i \frac{1}{k_{\text{rrf}} + \text{rank}(d, L_i)}
\]

- Documents not in list `L_i` contribute `0` for that list.
- **Dedupe:** Before scoring, map each `Document` to `key(d)`:
  - If `metadata.get("child_id")`: `key = ("child", child_id)` — same normative contract as [retrieval-hierarchical.md](retrieval-hierarchical.md) so two chunks with identical `page_content` but different `child_id` remain distinct in RRF.
  - Else: `key = ("flat", page_content, source, page, path)` matching `DualRetriever._doc_key` (which prefers `(child_id,)` when present).
- Multiple `Document` objects with same `key` in one list: keep **best** (minimum) rank only.
- Sort by `RRF` descending; tie-break by **earlier first appearance** in the concatenation of heads in fixed order (document the head order in code constant `HEAD_ORDER`).

Constants:

- `ETB_RRF_K` default `60`.
- `ETB_ENSEMBLE_CAP` default `80` — after RRF sort, keep top `cap` before rerank to bound cost.

## Reranker backends

Env: `ETB_RERANKER`

| Value | Behavior |
|-------|----------|
| `off` | Skip reranking; after RRF, take first `k` documents. |
| `cosine` | Re-score with cosine similarity between `embed_query(query)` and `embed_documents([chunk])` or per-chunk `embed_query` if batch unsupported—use **existing Ollama embedding model**; normalize vectors. |
| `cross_encoder` | Optional dependency: `sentence-transformers` `CrossEncoder` (e.g. `cross-encoder/ms-marco-MiniLM-L-6-v2`); lazy load; CPU by default. |
| `llm` | Batched prompt: chat LLM assigns relevance score 0–10 per chunk; parse structured output; **high latency**—use small `ETB_ENSEMBLE_CAP` and chunk batch size. Reuse retriever chat LLM client (same as HyDE). |

Per-request override:

- `RetrieveRequest.reranker: Literal["off","cosine","cross_encoder","llm"] | None` — `None` → env.

**Failure:** On rerank exception, log and fall back to ensemble ordering truncated to `k`.

## Debug / observability

- If `ETB_RETRIEVAL_DEBUG=1`, attach optional `scores` or `head_id` trace in logs only (not response body by default) to avoid leaking internal structure; optional future `?debug=1` query param **discouraged** in production.

## Parallelism

- Run independent heads with `concurrent.futures.ThreadPoolExecutor` (embeddings/LLM may block)—cap max workers (e.g. 4). BM25 + FAISS are in-process; avoid nested locks (build candidate lists outside `RLock` if possible, then merge under lock).

## API summary

Fields on `RetrieveRequest` (accumulated across plans):

| Field | Purpose |
|-------|---------|
| `query` | Required user/refined query string. |
| `k` | Final top-k after rerank (before expansion count semantics—document whether expansion changes count). |
| `strategy` | `dense` \| `hybrid` — BM25 heads. |
| `hyde_mode` | `off` \| `replace` \| `fuse`. |
| `expand` | Hierarchical parent expansion. |
| `reranker` | Override reranker backend. |

**Expansion and `k`:** Recommended semantics: `k` is the number of **child-level** items entering expansion; after expansion, **number of returned chunks may be &lt; k** because of parent collapse. Document in OpenAPI.

## Configuration reference (env)

| Variable | Default | Meaning |
|----------|---------|---------|
| `ETB_RETRIEVAL_K_FETCH` | derived | Oversample per head: `min(max(k*5, 30), 100)` unless overridden. |
| `ETB_RRF_K` | `60` | RRF smoothing constant. |
| `ETB_ENSEMBLE_CAP` | `80` | Max candidates passed to reranker. |
| `ETB_RERANKER` | `cosine` | Default MVP reranker (or `off` if embeddings too slow—product choice). |
| `ETB_RETRIEVAL_DEBUG` | `0` | Verbose logging. |

## Testing

- **Unit:** `ensemble_rrf` with 3+ synthetic lists and known scores; tie-break assertion.
- **Unit:** reranker `cosine` reordering with mocked embeddings.
- **Integration:** `TestClient` against retrieve route with patched heads returning fixed ranks.

## Performance expectations

- RRF: negligible vs embedding.
- `cosine` rerank: one batch embed for all candidates + one query embed — O(n) embedding calls if no batch API; prefer batch `embed_documents` on `C`.
- `cross_encoder`: ~10–50ms per pair on CPU for small models — keep `ETB_ENSEMBLE_CAP` low.
- `llm`: dominant cost; batch chunks in single prompt with strict max tokens.

## Suggested implementation order

1. Implement `pipeline.py` with **dense-only** heads (current dual FAISS behavior) + `reranker=off` + RRF with two lists — regression-test against legacy ordering if needed.
2. Add BM25 heads behind `strategy`.
3. Add HyDE heads behind `hyde_mode`.
4. Add `hier_child` + post-rerank expansion.

## References

- `src/etb_project/retrieval/dual_retriever.py` — baseline dedupe key.
- `src/etb_project/api/state.py` — `RetrieverServiceState`.
- `src/etb_project/api/schemas.py` — `RetrieveRequest` / `ChunkOut`.
- `src/etb_project/api/app.py` — `POST /v1/retrieve`.
