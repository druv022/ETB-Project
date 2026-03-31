# Usage

This page explains how to run the ETB-project **CLI** (`python -m etb_project.main`), what modes it supports, and what happens at runtime. For the Streamlit UI and HTTP services, see [`APP_RUN_MODES.md`](APP_RUN_MODES.md).

## What you run

The primary CLI entry point is:

```bash
python -m etb_project.main
```

You can also run the same command via:

```bash
make run
```

Run from the repo root (or any directory) with the package installed (`pip install -e .`) so `etb_project` imports resolve. Use `PYTHONPATH=src` only if you skip editable install (see [`DEVELOPMENT.md`](DEVELOPMENT.md)).

## Runtime modes

Behavior is controlled by `query` in `src/config/settings.yaml` (or `ETB_CONFIG`) and by `ETB_RETRIEVER_MODE` for retrieval wiring (see [`CONFIGURATION.md`](CONFIGURATION.md)).

### 1) Single-query mode (`query` non-empty)

If `query` is set in config, the app:

- Builds a retriever (**local** dual FAISS or **remote** `RemoteRetriever`, per `ETB_RETRIEVER_MODE`)
- Calls **`retriever.invoke(config.query)`** once
- Logs each returned document (content snippet only)
- Exits

There is **no LangGraph** invocation and **no LLM** in this path. It is useful to debug retrieval, CI smoke tests, and quick chunk inspection.

### 2) Interactive mode (`query` empty)

If `query` is empty, the app:

- Builds the same retriever as above
- Enters a **read–eval loop**: you type a question on stdin
- Each line is passed through the **LangGraph** RAG graph: `ingest_query → retrieve_rag → generate_answer`
- The **chat model** is **`get_ollama_llm()`** from [`models.py`](../src/etb_project/models.py) (Ollama `ChatOllama`), honoring `OLLAMA_HOST` / `OLLAMA_BASE_URL`, `OLLAMA_CHAT_MODEL`, `OLLAMA_TEMPERATURE`

**Important:** The interactive CLI does **not** use `ETB_LLM_PROVIDER` or OpenAI-compatible / OpenRouter settings. Those apply to the **Orchestrator API** (`get_chat_llm()`), not to `etb_project.main`. To use OpenRouter in a chat UI, run Docker Compose and talk to the **orchestrator**, or extend `main.py` to call `get_chat_llm()` instead of `get_ollama_llm()`.

Empty input line or Ctrl+D / Ctrl+C ends the loop.

## Local vs remote retrieval (`ETB_RETRIEVER_MODE`)

- **`local`** (default): loads persisted dual FAISS from `vector_store_path` on disk (requires prior indexing).
- **`remote`**: sends `POST /v1/retrieve` to `RETRIEVER_BASE_URL` (no local FAISS on this machine).

Both modes can be combined with either single-query or interactive behavior above.

## What the app loads vs what builds indices

- **Index building**: document processor CLI, Retriever `POST /v1/index/documents`, or programmatic APIs — see [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md).
- **Runtime querying** (`etb_project.main`): loads existing indices (**local**) or delegates to the retriever service (**remote**); it does **not** build indices from PDFs during normal runs.

If you change PDFs or chunking, rebuild or re-index first.

## Dual retrieval (text + image captions)

When both indices exist (local mode) or the retriever returns merged chunks (remote mode), you get text chunks plus caption chunks merged and de-duplicated before the graph consumes them (interactive mode only).

## Common “happy path”

1. Build or update persisted indices (CLI or retriever API).
2. Set `vector_store_path`, empty `query`, and optional `pdf` in `settings.yaml`.
3. Ensure **Ollama** is reachable if you use interactive CLI (or switch to remote retriever + orchestrator for OpenRouter chat).
4. Run:

```bash
python -m etb_project.main
```

## Related docs

- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`APP_RUN_MODES.md`](APP_RUN_MODES.md)
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
