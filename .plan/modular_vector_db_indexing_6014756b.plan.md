---
name: Modular vector DB indexing
overview: Introduce an abstract vector-index layer that builds and persists dual (text + caption) stores via CLI (and optionally a small FastAPI app), then change `main` to only load persisted indices and exit with clear instructions if missing.
todos:
  - id: vectorstore-package
    content: Add `vectorstore/` with ABC, manifest model, and `FAISSDualBackend` (save/load/is_ready).
    status: completed
  - id: config-settings
    content: Extend `AppConfig` + `settings.yaml` with `vector_store_path` and `vector_store_backend`.
    status: completed
  - id: indexing-service-cli
    content: Add shared `build_and_persist_index` + CLI flags (new module or extend `document_processor_cli`).
    status: completed
  - id: main-load-only
    content: Refactor `main.py` to load persisted index or exit with build instructions.
    status: completed
  - id: tests-readme
    content: Update tests (especially `test_main.py`) and README two-step workflow.
    status: completed
  - id: optional-fastapi
    content: "If desired: optional FastAPI + uvicorn extras and thin POST /index/build wrapping the service."
    status: cancelled
isProject: false
---

# Modular vector DB: build/store vs RAG load

## Current state

- `[src/etb_project/main.py](src/etb_project/main.py)` always calls `process_pdf_to_vectorstores(...)` (in-memory FAISS) before retrieval.
- `[src/etb_project/retrieval/process.py](src/etb_project/retrieval/process.py)` builds LangChain `FAISS` with `InMemoryDocstore` and never calls `save_local`.
- `[src/etb_project/document_processor_cli.py](src/etb_project/document_processor_cli.py)` builds in-memory stores when `--build-faiss` is set; no persistence.
- No HTTP API module exists today (only a Cursor rule for FastAPI).

## Design

### 1. Abstract “dual index” provider

Add a small package, e.g. `[src/etb_project/vectorstore/](src/etb_project/vectorstore/)` (name can be `indexing` if you prefer):

- `**base.py**`: `abc.ABC` class, e.g. `DualVectorStoreBackend`, with methods such as:
  - `persist(root: Path, text_store, caption_store, manifest: IndexManifest) -> None`
  - `load(root: Path, embeddings: Embeddings) -> tuple[FAISS, FAISS]` (concrete return type can stay LangChain `FAISS` for now, or use a thin `NamedTuple`/dataclass wrapping both stores)
  - `is_ready(root: Path) -> bool` (checks expected files + optional manifest)
- `**manifest.py**`: dataclass / Pydantic model written as JSON at `root / "manifest.json"` with at least: `backend` (`"faiss"`), paths to text/caption subdirs, **embedding model id** (or a stable tag your app uses), chunking params, source `pdf` path, and optionally a **content hash** of the PDF so stale indices are detectable.

**Important**: FAISS `load_local` must use the **same embedding implementation** as at index time (same model + dimensions). The manifest should record enough to validate or warn on mismatch.

### 2. FAISS implementation

- `**faiss_backend.py`**: implements `DualVectorStoreBackend` using existing pipeline:
  - Reuse `[process_pdf_to_text_and_caption_docs](src/etb_project/document_processing/processor.py)` + `[build_two_vectorstores](src/etb_project/retrieval/process.py)` (or move `build_two_vectorstores` next to the backend to keep `retrieval/` focused on query-time behavior).
  - **Save**: `text_vectorstore.save_local(str(root / "text"))`, `caption_vectorstore.save_local(str(root / "captions"))` (LangChain community API).
  - **Load**: `FAISS.load_local(..., embeddings, allow_dangerous_deserialization=True)` only if you accept that tradeoff for local dev; document the security note in README.

### 3. Configuration

Extend `[AppConfig](src/etb_project/config.py)` + `[src/config/settings.yaml](src/config/settings.yaml)`:

- `vector_store_backend: str` (default `"faiss"`).
- `vector_store_path: str | None` — root directory for the dual index (e.g. `./vector_index`).

`main` resolves path relative to cwd or project root consistently (document in README).

### 4. Indexing entry points (outside RAG)

**CLI (primary)**

- Extend `[document_processor_cli.py](src/etb_project/document_processor_cli.py)` **or** add `python -m etb_project.build_index` to avoid overloading the PDF artifact CLI:
  - Flags: `--pdf`, `--output-dir` (existing artifacts), `--vector-store-dir`, `--backend faiss`, chunk options, optional caption model (same as today).
  - Flow: build `text_docs`/`caption_docs` → `build_two_vectorstores` → `DualVectorStoreBackend.persist(...)`.
  - Log success and manifest path.

**API (optional, if you want HTTP)**

- Add minimal FastAPI app under e.g. `[src/etb_project/api/index_app.py](src/etb_project/api/index_app.py)` with one route `POST /index/build` (body: pdf path, vector_store_dir, options) that runs the same service function the CLI calls. Add `fastapi`/`uvicorn` under `[project.optional-dependencies]` in `[pyproject.toml](pyproject.toml)` so core install stays light.

Extract shared logic into `**indexing_service.py`**: `build_and_persist_index(...)` used by CLI and API.

### 5. Change `main` to load-only

In `[src/etb_project/main.py](src/etb_project/main.py)`:

1. Load config; require `vector_store_path` set and `DualVectorStoreBackend.is_ready(...)`.
2. If not ready: **do not** build from PDF. Log clear instructions, e.g.
  `python -m etb_project.document_processor_cli --pdf <path> --output-dir ... --build-faiss --persist-index --vector-store-dir ...`
   (exact flags per your CLI choice), then `raise SystemExit(1)`.
3. If ready: `load(...)` → `as_retriever` on each → existing `[DualRetriever](src/etb_project/retrieval/dual_retriever.py)` + LangGraph path unchanged.

Optional: if manifest PDF path differs from `config.pdf`, log a **warning** (still load) or treat as error—pick one behavior and document it.

### 6. Tests and docs

- Unit tests: mock filesystem + LangChain `FAISS.save_local`/`load_local` where heavy; test `is_ready`, manifest write/read, and `main` branches (missing index vs loaded).
- Update `[tests/test_main.py](tests/test_main.py)` to expect **load** instead of `process_pdf_to_vectorstores` when index exists, and exit-with-message when missing.
- Update `[README.md](README.md)`: two-step workflow—(1) build index via CLI/API, (2) run `main` for RAG.

## Dependency / layering

```
document_processing (PDF → docs)
        ↓
retrieval/process.py (embed + FAISS in memory)  ← keep or slim to “embedding helpers”
        ↓
vectorstore/* (persist/load + manifest + backend registry)
        ↓
main.py (load only)  |  CLI / API (build+persist)
```

## Out of scope (later)

- Second backend (e.g. Chroma): add `chroma_backend.py` implementing the same ABC once FAISS path is stable.
- Automatic rebuild when PDF changes: compare manifest hash vs file hash and prompt/rebuild.
