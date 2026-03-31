# Configuration

The ETB-project RAG app reads its primary configuration from YAML and supplements it with environment variables (for secrets like API keys).

This page documents:

- where config is loaded from
- the core settings in `src/config/settings.yaml`
- environment variables used by the project

## Config file: `src/config/settings.yaml`

### How the app finds the config

The main app reads configuration from `src/config/settings.yaml`.

Resolution behavior:

- It looks for this file relative to the **current working directory** first (so running from the repo root works).
- It also supports locating the file relative to the installed package location (so running from inside `src/` works).
- You can override the config path with `ETB_CONFIG` (absolute path to another YAML file).

### Core keys

The root README keeps only a minimal subset of these. This page is the full reference.

| Key | Type | Description |
|---|---:|---|
| `pdf` | string/null | Path to the PDF to index and query (absolute or relative to current working directory). |
| `query` | string | Single query to run; leave empty for interactive mode. |
| `retriever_k` | int | Number of chunks to retrieve per query (typically 1–100). |
| `log_level` | string | Logging level: DEBUG, INFO, WARNING, ERROR. |
| `vector_store_path` | string | Directory path where persisted vector indices live (used by `etb_project.main` for load-only retrieval). |
| `openrouter_image_caption_model` | string/empty | If set, enables OpenRouter captioning and selects the model name. |
| `openai_image_caption_model` | string/empty | If set (and OpenRouter model is not set), enables OpenAI captioning and selects the model name. |

Notes:

- `pdf` must point to an existing file. The app exits with an error if it is missing or not found.
- Captioning model keys control which captioner backend is used (see [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)).

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
  - Absolute path to a YAML file to use instead of `src/config/settings.yaml`.

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
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
