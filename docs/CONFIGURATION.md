# Configuration

The ETB-project RAG app reads its primary configuration from YAML and supplements it with environment variables (for secrets like API keys).

This page documents:

- where config is loaded from
- the core settings in `src/config/settings.yaml`
- application LLM prompts in `src/config/prompts.yaml`
- environment variables used by the project

## LLM prompts: `src/config/prompts.yaml`

The main package loads all **application** chat/vision prompts (Orion gate, RAG answer instructions, HyDE, LLM rerank scoring, image captioning) from this file via `etb_project.prompts_config.load_prompts()`.

Resolution:

1. If **`ETB_PROMPTS`** is set, use that path (absolute or relative).
2. Otherwise use **`prompts.yaml`** in the **same directory** as the resolved settings YAML (`ETB_CONFIG` or the default `src/config/settings.yaml`).

Reporting utilities under `tools/data_generation/report_generation/` use **only** `tools/data_generation/report_generation/llm_config.yaml` for narrative/evaluation/rewrite prompts; they do not read `src/config/prompts.yaml`.

## Config file: `src/config/settings.yaml`

### How the app finds the config

`load_config()` (used by `etb_project.main`, the document processor CLI, and the Retriever API settings) resolves the YAML path as follows:

1. If **`ETB_CONFIG`** is set, use that path (absolute or as given).
2. Else if **`./src/config/settings.yaml`** exists relative to the **current working directory**, use it (typical when you run commands from the repo root).
3. Else use **`src/config/settings.yaml`** next to the installed package (works when the working directory differs).

If the resolved file is missing, the loader returns **default** `AppConfig` values (see `etb_project.config`). The Retriever API still requires `vector_store_path` to be set in YAML when you run the HTTP service.

### Core keys

The root README keeps only a minimal subset of these. This page is the full reference.

| Key | Type | Description |
|---|---:|---|
| `pdf` | string/null | Path to a PDF used by CLI workflows and error messages when the local index is missing. |
| `query` | string | If non-empty, `python -m etb_project.main` runs **retrieval-only** for that string and exits (no LangGraph, no LLM). If empty, runs **interactive** LangGraph RAG. |
| `retriever_k` | int | Top-k for each sub-retriever branch before merge (1–100); used by `main`, CLI, and retriever API default `k`. |
| `log_level` | string | DEBUG, INFO, WARNING, ERROR. Used by `main` and passed into Retriever API logging. |
| `vector_store_backend` | string | Currently only **`faiss`** is implemented (`main` exits if set otherwise). |
| `vector_store_path` | string | Directory for persisted dual FAISS indices (`main` local mode, CLI, Retriever API). Resolved under `data/` when relative (see `resolve_artifact_path`). |
| `openrouter_image_caption_model` | string/empty | If set, enables OpenRouter captioning and selects the model name. |
| `openai_image_caption_model` | string/empty | If set (and OpenRouter model is not set), enables OpenAI captioning and selects the model name. |

Notes:

- For **`etb_project.main`**, if the local index is missing, a valid **`pdf`** path is required so the error message can tell you how to rebuild (see [`USAGE.md`](USAGE.md)).
- Captioning model keys control which captioner backend the **document processor CLI** uses (see [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)).

### Example: interactive mode

```yaml
pdf: data/your-document.pdf
query: ""   # leave empty for interactive mode
retriever_k: 10
log_level: INFO
vector_store_path: data/vector_index
```

### Example: single-query mode

```yaml
pdf: data/your-document.pdf
query: "Summarize the key points in section 2."
retriever_k: 10
log_level: INFO
vector_store_path: data/vector_index
```

### Example: enable OpenRouter captioning

```yaml
openrouter_image_caption_model: "google/gemini-2.0-flash"
openai_image_caption_model: ""
```

### Example: enable OpenAI captioning

```yaml
openrouter_image_caption_model: ""
openai_image_caption_model: "gpt-4.1-mini"
```

## Environment variables

This project uses environment variables for:

- **Service wiring** (UI → Orchestrator → Retriever)
- **Secrets** (API keys)
- **Operational limits** (rate limiting, upload limits, async indexing)

### Config selection

- `ETB_CONFIG`
  - Path to a YAML file to use instead of the default `src/config/settings.yaml` resolution.
- `ETB_PROMPTS`
  - Optional. Path to `prompts.yaml` for application LLM strings. If unset, `prompts.yaml` next to the resolved `ETB_CONFIG` / default settings file is used.

### CLI (`python -m etb_project.main`)

Local vs remote retrieval (overrides default **local** dual-FAISS load):

- `ETB_RETRIEVER_MODE`
  - `local` (default): load persisted indices from `vector_store_path`.
  - `remote`: use `RemoteRetriever` to call the Retriever HTTP API (no local FAISS files required on this machine).
- `RETRIEVER_BASE_URL`
  - Required when `ETB_RETRIEVER_MODE=remote` (e.g. `http://localhost:8000`). Same variable name as the orchestrator uses to find the retriever.
- `RETRIEVER_TIMEOUT_S`
  - Optional; HTTP timeout in seconds for remote retrieval (default `60`).

### UI (Streamlit)

- `ORCHESTRATOR_BASE_URL`
  - Base URL for the orchestrator (default: `http://localhost:8001`).
- `RETRIEVER_API_KEY` or `ORCHESTRATOR_ASSET_BEARER_TOKEN`
  - Optional. If the retriever requires a bearer token (`RETRIEVER_API_KEY` on the retriever service), the UI must send the same token when fetching images from `GET /v1/assets/...` (via the orchestrator proxy). Set one of these in the UI container environment to match the retriever.

### Orchestrator API (FastAPI)

- `RETRIEVER_BASE_URL`
  - Base URL for the retriever API (required for orchestrator; in Compose it’s `http://retriever:8000`).
- `ORCH_RETRIEVER_K`
  - Default `k` used by `POST /v1/chat` when the request body doesn’t specify `k`.
- `ORCH_SESSION_TTL_SECONDS`
  - Session TTL for in-memory chat history.
- `ORCH_CORS_ALLOW_ORIGINS`
  - Optional comma-separated origins for CORS (e.g. `http://localhost:8501`).
- `ETB_ORCH_HOST`
  - Bind address for `python -m etb_project.orchestrator` (default `0.0.0.0`).
- `ETB_ORCH_PORT` or `PORT`
  - Listen port (default `8001`). `PORT` is accepted for hosted environments.

LLM provider selection:

- `ETB_LLM_PROVIDER`
  - `openai_compat` (default) or `ollama`.

OpenAI-compatible chat backend (also used for OpenRouter):

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_TEMPERATURE`

Ollama chat backend:

- `OLLAMA_HOST` (or `OLLAMA_BASE_URL`)
- `OLLAMA_CHAT_MODEL`
- `OLLAMA_TEMPERATURE`

### Retriever API (FastAPI)

Process binding (local `uvicorn` via `python -m etb_project.api`):

- `ETB_API_HOST`
  - Bind address (default `0.0.0.0`).
- `ETB_API_PORT` or `PORT`
  - Listen port (default `8000`).

Wiring / auth:

- `RETRIEVER_API_KEY`
  - If set, clients must send `Authorization: Bearer <token>`.

Artifact directories:

- `ETB_DOCUMENT_OUTPUT_DIR` (default: `data/document_output`)
- `ETB_UPLOAD_DIR` (default: `data/uploads`)

Indexing behavior:

- `ETB_CHUNK_SIZE` (default: 1000)
- `ETB_CHUNK_OVERLAP` (default: 200)
- `ETB_INDEX_ASYNC`
  - When true (default), `POST /v1/index/documents` runs in background and returns a `job_id` unless `async_mode=false`.
- `ETB_INDEX_SHUTDOWN_TIMEOUT_S`
  - Grace period for in-flight indexing on shutdown (default `120` seconds).

Limits:

- `ETB_MAX_RETRIEVE_K` (default: 100; max 100)
- `ETB_MAX_QUERY_CHARS` (default: 10000)
- `ETB_MAX_UPLOAD_BYTES` (default: 50MB per PDF)
- `ETB_MAX_UPLOAD_FILES` (default: 20 files per request)
- `ETB_MAX_RETRIEVE_BODY_BYTES` (default: 65536)
- `ETB_RATE_LIMIT_PER_MINUTE` (default: 120)

### Captioning secrets

- `OPENROUTER_API_KEY`
  - Required for `OpenRouterImageCaptioner`.
- `OPENAI_API_KEY`
  - Required for `OpenAIImageCaptioner` and OpenAI-compatible endpoints (when not using OpenRouter).

Common workflow:

```bash
cp .env.example .env
```

Then set the keys in `.env` (do not commit secrets).

## Related docs

- [`USAGE.md`](USAGE.md)
- [`APP_RUN_MODES.md`](APP_RUN_MODES.md)
- [`RETRIEVER_API.md`](RETRIEVER_API.md)
- [`ORCHESTRATOR_API.md`](ORCHESTRATOR_API.md)
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
