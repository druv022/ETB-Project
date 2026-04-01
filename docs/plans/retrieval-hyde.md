# Plan: HyDE (Hypothetical Document Embeddings) — ensemble dense heads

HyDE improves dense retrieval when the user query is short or vocabulary-mismatched vs the corpus. Implementation is **only in the Retriever Docker** (`etb_project.api`). The orchestrator **does not** run HyDE; it only sends `query` and optional `hyde_mode` on `POST /v1/retrieve`.

## Goals

- Generate a short **hypothetical passage** `H` via **chat LLM** inside the retriever.
- Use `embed_query(H)` (and optionally `embed_query(query)`) against existing **dual FAISS** stores to produce **additional ranked lists** for the global ensemble.
- Single HTTP round-trip from orchestrator for the full retrieve pipeline.

## Non-goals

- HyDE as a LangGraph node in `graph_rag.py`.
- Separate vector store for HyDE (reuse text + caption FAISS).

## Global retrieve pipeline (verbatim)

1. **Resolve query:** Read `query` from request; apply HyDE LLM when enabled to obtain `H` (hypothetical passage) as needed for heads.
2. **Candidate generation (parallel where practical):** Each enabled **head** runs with an oversample `k_fetch` (env e.g. `ETB_RETRIEVAL_K_FETCH`, default `max(k * 5, 30)` cap ~100). Each head returns an **ordered** list of `Document` (same metadata keys as today). Tag internally with `head_id` for logging/tracing (optional metadata key `ensemble_head`, stripped before response if undesirable).
   - **Dense–query:** `embed_query(query)` → similarity search on text FAISS + caption FAISS → **two** lists.
   - **Dense–HyDE:** If `hyde_mode` is `replace`, only HyDE dense lists participate for the HyDE slots (query dense lists may be omitted). If `fuse`, both query- and `H`-embedded searches run → up to **four** dense lists (text+caption × query+HyDE).
   - **BM25:** If hybrid/strategy includes sparse: `bm25_text`, `bm25_caption` lists.
   - **Hierarchical child:** If hierarchy index present: child FAISS search (default **query embedding** for child head).
3. **Ensemble:** Apply **Reciprocal Rank Fusion** across all lists that returned at least one doc. Stable dedupe key: `DualRetriever._doc_key` `(page_content, source, page, path)` or extended key if hierarchy adds `child_id`. RRF constant `ETB_RRF_K` (default 60). Output: candidate pool `C` capped by `ETB_ENSEMBLE_CAP`.
4. **Rerank (final ordering):** Score each candidate in `C` with the active **reranker** using the **user query string** (not `H` unless explicitly documented and implemented). Sort descending; take top `k_return` = request `k`.
5. **Hierarchical expansion (post-rerank):** If `expand=true` and hierarchy exists: map top child hits to parents per hierarchical plan.

**Failure isolation:** If reranker fails → fall back to ensemble order truncated to `k`. If ensemble receives zero lists → 503 or empty chunks per existing API behavior.

## Modes

| `hyde_mode` | Dense heads registered |
|-------------|-------------------------|
| `off` | Query embedding only: text FAISS + caption FAISS (two lists), same as pre-HyDE baseline for dense. |
| `replace` | HyDE embedding only: `embed_query(H)` → text FAISS + caption FAISS (two lists). Query-embedding dense lists **omitted** for the HyDE “slot” (BM25 and hier_child still use `query` string / query embedding per their plans). |
| `fuse` | Four lists: text+caption × (`embed_query(query)`, `embed_query(H)`). |

**Recommendation:** In `fuse`, pass **four separate ranked lists** into RRF for maximum signal (symmetric with four-list BM25+dense scenarios).

## LLM client in retriever

- Reuse `get_chat_llm()` (or equivalent) from `src/etb_project/models.py`, initialized **inside retriever process only**.
- **Lazy initialization:** First HyDE request (or first request with `hyde_mode != off`) constructs the client; if credentials missing, log error and fall back to `off` behavior for that request.
- **Docker Compose:** Mirror orchestrator chat LLM env vars on the `retriever` service (`ETB_LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, model ids, etc.).

## Prompting

New module (retriever-owned, **not** `orchestrator/prompts.py`):

- Suggested path: `src/etb_project/retrieval/hyde_prompts.py` or `src/etb_project/api/hyde_prompts.py`.

Prompt requirements:

- Output **one paragraph** of hypothetical document text that could plausibly appear in the indexed corpus.
- **Not** a direct answer to the user; no markdown headings; no bullet lists.
- Soft cap: `ETB_HYDE_MAX_TOKENS` (e.g. 256–512 completion tokens).

## Failure handling

- LLM timeout/error/empty → skip HyDE for this request: behave as `hyde_mode=off` for dense-HyDE lists (still run query dense lists). Log warning with request id if available.

## HTTP / schema

Extend `RetrieveRequest`:

```python
hyde_mode: Literal["off", "replace", "fuse"] | None = None  # None → ETB_HYDE_MODE env
```

Env defaults:

- `ETB_HYDE_MODE=off` default for backward compatibility.

## Interaction with Orion

- Orion (orchestrator) may refine the user message; client sends the **refined query** as `query`. HyDE always consumes that **final `query`** string. No second Orion inside retriever.

## Lexical BM25 and `H`

- **Default:** BM25 uses **`query` only**, not `H`, so lexical signal stays aligned with user intent.

## Code touchpoints

| Area | Change |
|------|--------|
| `src/etb_project/api/schemas.py` | `hyde_mode` on `RetrieveRequest`. |
| `src/etb_project/api/state.py` / `pipeline.py` | Call HyDE generator before head collection; pass `H` to dense head builder. |
| `docker-compose.yml` | Retriever service env for chat LLM. |
| `src/etb_project/retrieval/remote_retriever.py` | Optional JSON field forward from orchestrator. |

## Testing

- Unit: mock LLM returns fixed `H`; assert four similarity searches in `fuse`, two in `replace`, two in `off`.
- Integration: retriever test client with `httpx` + mocked LLM.

## Risks

- **Latency:** Extra LLM call per retrieve when HyDE on—document in ops runbooks.
- **Cost:** Chat tokens on retriever hot path—consider caching `H` per normalized query hash (optional future).

## References

- `src/etb_project/api/state.py`
- `src/etb_project/models.py`
- [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md)
