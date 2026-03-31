# Running the app (updated)

This project has multiple runnable entrypoints depending on whether you want the **UI**, the **orchestrator API**, the **retriever API**, or the **CLI**.

## Recommended: Docker Compose (UI + Orchestrator + Retriever)

This is the simplest path for most users who want **chat with OpenRouter (or other OpenAI-compatible APIs)** and dual retrieval.

1. Create a `.env` at the repo root (at minimum set `OPENROUTER_API_KEY` or `OPENAI_API_KEY` so Compose can pass `OPENAI_API_KEY` to the orchestrator — see `docker-compose.yml`).

2. Run:

```bash
docker compose up --build
```

3. Open:

- UI: `http://localhost:8501`
- Orchestrator health: `http://localhost:8001/v1/health`
- Retriever health: `http://localhost:8000/v1/health`

### What’s running

- **Streamlit UI** (`app.py`) calls **Orchestrator API** `POST /v1/chat` and loads images through **Orchestrator** `GET /v1/assets/{path}` (proxied to the retriever).
- **Orchestrator API** runs LangGraph RAG (`ingest_query → retrieve_rag → generate_answer`) and uses **`get_chat_llm()`** — `ETB_LLM_PROVIDER` + `OPENAI_*` / `OLLAMA_*` (see [`CONFIGURATION.md`](CONFIGURATION.md)).
- **Retriever API** serves `POST /v1/retrieve`, `POST /v1/index/documents`, and `GET /v1/assets/...`.
- **Ollama** provides **embeddings** to the Retriever API (chat LLM may be OpenRouter or Ollama depending on orchestrator env).

### Makefile vs Docker Compose v2

The **Makefile** uses `docker-compose` (legacy binary) for `make docker-up`. If you only have `docker compose` (plugin), run `docker compose up` directly or install the Compose V1 CLI.

## LLM configuration (Orchestrator)

The orchestrator picks a chat provider via `ETB_LLM_PROVIDER` (defaults to `openai_compat`) in [`src/etb_project/models.py`](../src/etb_project/models.py).

### OpenRouter (or any OpenAI-compatible API) via `openai_compat` (default)

Typical Docker setup:

- `OPENAI_BASE_URL=https://openrouter.ai/api/v1` (Compose default)
- `OPENAI_API_KEY` from your `.env` (often mapped from `OPENROUTER_API_KEY`)
- `OPENAI_MODEL=stepfun/step-3.5-flash` (or another model id)

### Ollama chat via `ollama`

Set:

- `ETB_LLM_PROVIDER=ollama`
- `OLLAMA_HOST=http://ollama:11434` (inside Compose network)
- `OLLAMA_CHAT_MODEL=qwen3.5:9b` (default)

## CLI (`python -m etb_project.main`) — no UI

The **interactive** CLI uses **Ollama only** for the answer-generation step (`get_ollama_llm()`), not `ETB_LLM_PROVIDER`. For OpenRouter-backed chat, use the **orchestrator + UI** (or change `main.py` to call `get_chat_llm()`).

```bash
python -m etb_project.main
```

To use the **remote retriever API** from the CLI (same machine or elsewhere):

```bash
export ETB_RETRIEVER_MODE=remote
export RETRIEVER_BASE_URL=http://localhost:8000
python -m etb_project.main
```

See [`USAGE.md`](USAGE.md) for single-query vs interactive behavior and retrieval-only mode.

## Notes on `tools/`

Everything under `tools/` is intentionally **separate** from the main app under `src/`.

Reporting utilities use their own configuration (`tools/data_generation/report_generation/llm_config.yaml` and `REPORT_LLM_*`).
