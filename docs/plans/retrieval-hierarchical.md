# Plan: Hierarchical retrieval (child FAISS + parent SQLite)

Hierarchical retrieval keeps **small child chunks** in FAISS for precise vector hits, and **parent units** (full page text) in **SQLite** for wide context. **Child-level** hits participate in the **global ensemble + rerank**; **parent expansion** runs **after rerank** as pipeline step 5.

## Goals

- Reduce “fragmented context” in the generator by expanding top reranked children to parent text.
- Use **free**, **local** storage: stdlib SQLite + existing FAISS (no hosted vector DB).
- Retriever Docker only.

## Non-goals (MVP)

- Multi-level trees (section → subsection → chunk) beyond page→child.
- Parent-level vector index (summary FAISS) — optional future extension.

## Global retrieve pipeline (verbatim)

1. **Resolve query:** Read `query` from request; apply HyDE LLM when enabled to obtain `H` (hypothetical passage) as needed for heads.
2. **Candidate generation (parallel where practical):** Each enabled **head** runs with an oversample `k_fetch` (env e.g. `ETB_RETRIEVAL_K_FETCH`, default `max(k * 5, 30)` cap ~100). Each head returns an **ordered** list of `Document` (same metadata keys as today). Tag internally with `head_id` for logging/tracing (optional metadata key `ensemble_head`, stripped before response if undesirable).
   - **Dense–query:** `embed_query(query)` → similarity search on text FAISS + caption FAISS → **two** lists.
   - **Dense–HyDE:** If `hyde_mode` is `replace`, only HyDE dense lists participate for the HyDE slots (query dense lists may be omitted). If `fuse`, both query- and `H`-embedded searches run → up to **four** dense lists (text+caption × query+HyDE).
   - **BM25:** If hybrid/strategy includes sparse: `bm25_text`, `bm25_caption` lists.
   - **Hierarchical child:** If hierarchy index present: child FAISS search (default **query embedding** for child head).
3. **Ensemble:** Apply **Reciprocal Rank Fusion** across all lists that returned at least one doc. Stable dedupe key: `DualRetriever._doc_key` **extended** to include `child_id` when two chunks share the same `page_content` hash but differ by child split—see **Dedupe key** below. RRF constant `ETB_RRF_K` (default 60). Output: candidate pool `C` capped by `ETB_ENSEMBLE_CAP`.
4. **Rerank (final ordering):** Score each candidate in `C` with the active **reranker** using the **user query string**. Sort descending; take top `k_return` = request `k`.
5. **Hierarchical expansion (post-rerank):** If `expand=true` and hierarchy exists: map each of the top `k_return` **child** hits to `parent_id`, fetch parent `full_text` from SQLite, **collapse** to unique parents while **preserving rerank order** (first occurrence wins), apply `ETB_PARENT_CONTEXT_CHARS` / `ETB_MAX_PARENTS` caps. Returned `page_content` is parent body. If `expand=false`, return reranked **child** chunks unchanged.

**Failure isolation:** If reranker fails → fall back to ensemble order truncated to `k`. If ensemble receives zero lists → 503 or empty chunks per existing API behavior.

## Dedupe key alignment

When hierarchy is enabled, the same underlying text might appear as both:

- a **child** row (FAISS + SQLite `child` table), and
- documents from **legacy** flat indices.

Define a stable **`child_id`** in `Document.metadata` at index time (e.g. UUID or `f"{source}::p{page}::c{chunk_index}"`). Ensemble RRF dedupe key becomes:

- `(child_id,)` if `child_id` present, else fall back to `(page_content, source, page, path)` from `DualRetriever._doc_key`.

Document this contract in [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md) as normative.

## SQLite schema

Path: `vector_store_path / hierarchy.sqlite`

```sql
CREATE TABLE parent (
  parent_id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  page_start INTEGER NOT NULL,
  page_end INTEGER NOT NULL,
  full_text TEXT NOT NULL,
  metadata_json TEXT NOT NULL
);

CREATE TABLE child (
  child_id TEXT PRIMARY KEY,
  parent_id TEXT NOT NULL REFERENCES parent(parent_id),
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  faiss_text_id TEXT,
  UNIQUE(parent_id, chunk_index)
);

CREATE INDEX idx_child_parent ON child(parent_id);
```

- `metadata_json`: serialized dict for debugging and asset paths; keep in sync with chunk `Document.metadata` subset.

## Chunking policy

- **Parent:** one row per **PDF page** (align with `pymupdf_extractor` page boundaries). `parent_id = f"{normalized_source}::page::{page_number}"`.
- **Child:** `RecursiveCharacterTextSplitter` with existing defaults (`chunk_size=1000`, `chunk_overlap=200`) **applied within** `parent.full_text` only.
- **FAISS text index:** embed **child** `text` only (not parent full_text), same embedding model as today.

## Captions

- Keep **separate** caption FAISS as today. Optional: store caption-derived docs with `parent_id` in metadata for expansion merges—when a **caption** chunk is in top reranked results, expansion step can attach related parent text if `parent_id` is present. MVP: **no** caption→parent join unless metadata already links them.

## Index build

Touchpoints:

- `src/etb_project/document_processing/processor.py` (or successor): emit page parents, then child splits.
- `src/etb_project/vectorstore/indexing_service.py`: after building child `Document` list, `INSERT` parents and children into SQLite; build FAISS from children only.
- `append_to_and_persist_index_for_pdfs`: append rows and vectors; validate manifest `hierarchy_schema_version` matches.

## Manifest

Add optional fields:

- `hierarchy_backend: str | None` — e.g. `"sqlite_v1"`.
- `hierarchy_schema_version: int | None` — e.g. `1`.

If hierarchy fields absent, hierarchical head and expansion are **disabled** (legacy indices).

## Runtime

- `HierarchyStore` class: `get_parents_ordered(parent_ids: list[str]) -> list[tuple[parent_id, full_text, metadata]]`.
- Expansion runs **after** rerank on the top-`k` **child** `Document` list; replace each child with parent `full_text` while collapsing duplicates by `parent_id` preserving order.

## HTTP / schema

- `expand: bool | None = None` — `None` → `ETB_HIER_EXPAND_DEFAULT` (default `true` when hierarchy index present).

## Config (env)

- `ETB_PARENT_CONTEXT_CHARS` — max total characters of parent text after merge (default e.g. 12000).
- `ETB_MAX_PARENTS` — max distinct parents in response (default e.g. 20).

## Testing

- Fixture SQLite + tiny FAISS with 2 parents, 4 children; verify ensemble key, rerank order preserved through expansion, caps applied.

## Risks

- **Token blowup:** parent bodies large—caps mandatory.
- **Migration:** existing flat indices have no SQLite—feature flag off until rebuild.

## References

- `src/etb_project/document_processing/pymupdf_extractor.py`
- `src/etb_project/retrieval/process.py` (splitter defaults)
- [retrieval-ensemble-rerank.md](retrieval-ensemble-rerank.md)
