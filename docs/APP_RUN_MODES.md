# Running the app (updated)

This project has multiple runnable entrypoints depending on whether you want the **UI**, the **orchestrator API**, the **retriever API**, or the **CLI**.

## Recommended: Docker Compose (UI + Orchestrator + Retriever)

This is the simplest path for most users.

1) Create a `.env` at the repo root:

```bash
OPENROUTER_API_KEY=...
```

2) Run:

```bash
docker compose up --build
```

3) Open:

- UI: `http://localhost:8501`
- Orchestrator health: `http://localhost:8001/v1/health`
- Retriever health: `http://localhost:8000/v1/health`

### What’s running

- **Streamlit UI** (`app.py`) calls **Orchestrator API** `POST /v1/chat`
- **Orchestrator API** runs LangGraph RAG (`ingest_query → retrieve_rag → generate_answer`)
- **Retriever API** serves retrieval (`POST /v1/retrieve`) and indexing (`POST /v1/index/documents`)
- **Ollama** provides embeddings to the Retriever API

## LLM configuration (Orchestrator)

The orchestrator picks a chat provider via `ETB_LLM_PROVIDER` (defaults to `openai_compat`) in [`src/etb_project/models.py`](../src/etb_project/models.py).

### OpenRouter (free models) via `openai_compat` (default)

Set:

- `OPENAI_BASE_URL=https://openrouter.ai/api/v1`
- `OPENAI_API_KEY=$OPENROUTER_API_KEY`
- `OPENAI_MODEL=stepfun/step-3.5-flash` (default)

### Ollama chat via `ollama`

Set:

- `ETB_LLM_PROVIDER=ollama`
- `OLLAMA_HOST=http://ollama:11434`
- `OLLAMA_CHAT_MODEL=qwen3.5:9b` (default)

## CLI (no UI)

You can run the interactive CLI RAG loop locally:

```bash
python -m etb_project.main
```

To use the **remote retriever API** from the CLI orchestrator:

```bash
export ETB_RETRIEVER_MODE=remote
export RETRIEVER_BASE_URL=http://localhost:8000
python -m etb_project.main
```

## Notes on `tools/`

Everything under `tools/` is intentionally **separate** from the main app under `src/`.

Reporting utilities use their own configuration (`tools/data_generation/report_generation/llm_config.yaml` and `REPORT_LLM_*`).
