---
name: fix-langgraph-blocking-error
overview: Refactor the RAG pipeline to avoid synchronous Ollama embedding calls on the ASGI event loop and add tests to verify the LangGraph entrypoint works without blocking errors.
todos:
  - id: analyze-current-rag-embedding-flow
    content: Analyze current RAG entrypoint, retrieval pipeline, and embedding model usage to locate all blocking embedding calls on the LangGraph path.
    status: completed
  - id: design-async-embedding-strategy
    content: Design an async embedding and retrieval strategy that avoids blocking the ASGI event loop while retaining existing RAG behavior.
    status: completed
  - id: implement-async-embedding-model
    content: Implement AsyncOllamaEmbeddingModel (or equivalent) using ollama.AsyncClient with async embed_documents and embed_query.
    status: completed
  - id: refactor-graph-to-async-retrieval
    content: Refactor graph_rag to use async nodes that perform embedding and FAISS retrieval, removing embedding work from the factory.
    status: completed
  - id: simplify-rag-app-factory
    content: Update rag_app in studio_entry.py to be a pure graph wiring function that does not call embeddings or process_documents.
    status: completed
  - id: separate-sync-retrieval-utilities
    content: Ensure sync process_documents/store_documents remain only for offline or CLI usage and are not used in the LangGraph pathway.
    status: completed
  - id: add-tests-for-rag-app-and-graph
    content: Add tests that construct rag_app, execute the graph with stubbed async embeddings, and verify no blocking errors and correct behavior.
    status: completed
  - id: manual-validation-and-docs
    content: Run langgraph dev without allow-blocking, do manual E2E validation, and update README with the new async embedding behavior and requirements.
    status: completed
isProject: false
---

# Fix LangGraph blocking error and validate RAG entrypoint

### Goal

Eliminate the `blockbuster.BlockingError` and `asyncio.run()` issues by ensuring all embedding calls used by the LangGraph graph are non-blocking with respect to the ASGI event loop, while preserving current functionality and adding tests.

### 1. Analyze current RAG and embedding flow

- **Inspect** `[src/etb_project/studio_entry.py](src/etb_project/studio_entry.py)` to confirm how `rag_app` builds the graph, loads the PDF, and calls `process_documents`.
- **Review** `[src/etb_project/retrieval/process.py](src/etb_project/retrieval/process.py)` to understand how `store_documents` and `process_documents` call `get_ollama_embedding_model` and FAISS.
- **Check** `[src/etb_project/graph_rag.py](src/etb_project/graph_rag.py)` to see how the graph is structured and where retrieval/embedding is logically expected to happen.
- **Verify** `[src/etb_project/models.py](src/etb_project/models.py)` to see the definition of `get_ollama_embedding_model` and whether it uses the sync LangChain Ollama integration.

### 2. Design an async-friendly embedding and retrieval strategy

- **Decide** to keep Ollama for embeddings but switch to an async usage pattern to avoid blocking the event loop.
- **Introduce** a new async embedding abstraction (e.g., `AsyncOllamaEmbeddingModel`) that wraps `ollama.AsyncClient` and exposes `embed_documents` and `embed_query` as `async` methods.
- **Plan** to move embedding calls out of the graph factory (`rag_app`) and into async LangGraph nodes so that all network I/O is awaited within the graph execution, not during factory construction.

### 3. Implement async embedding model

- **Create** a new module (e.g., `src/etb_project/models_async.py`) that defines `AsyncOllamaEmbeddingModel`, internally using `ollama.AsyncClient` and returning embeddings in the shapes expected by downstream code.
- **Ensure** that the async model does not perform any blocking I/O; all network calls should be awaited and rely only on async methods from the Ollama client.
- **Optionally** expose a helper like `get_async_embedding_model()` for consistent usage across the graph.

### 4. Refactor the RAG graph to use async embeddings

- **Update** `[src/etb_project/graph_rag.py](src/etb_project/graph_rag.py)` to:
  - Add one or more async nodes that:
    - Take the loaded documents (`docs`) and configuration (e.g., `retriever_k`),
    - Call `await async_embeddings.embed_documents(...)` to compute vectors,
    - Build or update a FAISS index using CPU-only operations,
    - Perform retrieval by calling `await async_embeddings.embed_query(query)` followed by FAISS similarity search.
  - Ensure the graph entry and edges are wired so that retrieval happens via these async nodes instead of precomputing a `vectorstore` inside `rag_app`.
- **Avoid** any calls to `asyncio.run()` from within the graph or factory; rely solely on async node functions that LangGraph will schedule.

### 5. Simplify `rag_app` to pure wiring

- **Modify** `[src/etb_project/studio_entry.py](src/etb_project/studio_entry.py)` so that `rag_app`:
  - Loads configuration and PDFs (file I/O only),
  - Constructs the graph via `build_rag_graph`, passing the LLM, docs, and config values,
  - Returns the compiled graph without running embeddings or building FAISS inside the factory.
- **Confirm** that `rag_app` no longer calls `process_documents`, `store_documents`, or any embedding APIs directly.

### 6. Adapt or deprecate the old sync retrieval utilities

- **Retain** the existing sync `process_documents` and `store_documents` in `[src/etb_project/retrieval/process.py](src/etb_project/retrieval/process.py)` for CLI or offline batch usage, but clearly separate them from the async graph path.
- **Ensure** that the LangGraph path uses the new async embedding nodes rather than these sync helpers, so that production traffic never hits blocking network code on the event loop.

### 7. Add automated tests for the LangGraph entrypoint

- **Create** tests in `tests/` (e.g., `tests/test_studio_entry.py` and/or extend existing RAG tests) that:
  - Instantiate `rag_app()` to obtain the graph without raising errors.
  - Run a minimal end-to-end query through the graph with a small in-memory document or a stubbed embedding model.
- **Use** dependency injection or monkeypatching to replace the real async embedding model with a fast, deterministic fake or stub in tests (so tests do not require a running Ollama instance).
- **Verify** that running the graph does not raise `BlockingError` and that the overall RAG flow returns a plausible answer structure.

### 8. Manual validation and documentation

- **Manually** run `langgraph dev` (without `--allow-blocking`) and exercise the assistant UI with a test query to confirm no `blockbuster.BlockingError` or `asyncio.run` errors appear.
- **Document** the new async embedding behavior and production requirements in `[README.md](README.md)`, including any environment variables, embedding model name, and the need for an async-capable Ollama server.
- **Summarize** in comments (only where non-obvious) where async vs sync boundaries are and why embedding calls must remain async in the graph.
