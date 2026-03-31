## Orchestrator API (v1)

The Orchestrator API is the **chat/RAG** service for ETB-project.

- **In scope**: session-aware chat endpoint, LangGraph RAG orchestration, LLM answer generation, calling the Retriever API for context
- **Out of scope**: PDF indexing and vector-store persistence (handled by the Retriever API)

### Run (Docker)

```bash
docker compose up --build
```

The API listens on `:8001` (see `docker-compose.yml`).

### Endpoints

#### `GET /v1/health`

Liveness check.

#### `GET /v1/ready`

Readiness check. Returns:

- `ready`: true when `RETRIEVER_BASE_URL` is set and the chat LLM can be constructed
- `retriever_base_url`: current retriever base URL (or null)
- `llm_configured`: whether `get_chat_llm()` succeeded at readiness check time

#### `GET /v1/assets/{asset_path}`

Proxies to the Retriever API’s `GET /v1/assets/{asset_path}` so the Streamlit UI only needs the orchestrator base URL. Forwards the incoming `Authorization` header when present (use the same bearer token as for the retriever when `RETRIEVER_API_KEY` is enabled).

Typical errors:

- `CONFIG_ERROR` (500): `RETRIEVER_BASE_URL` missing
- `UNAUTHORIZED` (401): retriever rejected the token
- `ASSET_NOT_FOUND` (404)
- `RETRIEVER_UNREACHABLE` (502): HTTP client error reaching the retriever
- `ASSET_PROXY_FAILED` (502): other retriever error responses

#### `POST /v1/chat`

Request body:

```json
{
  "session_id": "string",
  "message": "string",
  "return_sources": true,
  "k": 10
}
```

Notes:

- `k` is optional; when omitted it defaults to `ORCH_RETRIEVER_K` (default 10).
- If `return_sources=true`, the response includes the retrieved chunks used as context.

Response body:

```json
{
  "answer": "string",
  "sources": [
    { "content": "string", "metadata": { "source": "file.pdf", "page": 1 } }
  ],
  "request_id": "string",
  "phase": "clarify"
}
```

(`phase` is `"answer"` after a normal retrieve-and-answer turn.)

- **`phase`**: `"clarify"` when Orion returned a clarification only (no retrieval); `"answer"` when retrieval and grounded answering ran. Omitted or `null` in older clients; always set by the current server.

When Orion clarification is active (`ETB_ORION_CLARIFY=1`, default), a **clarify** turn returns **`sources: []`** because the retriever was not called.

### Configuration (environment variables)

**Orion (pre-retrieval clarification)**:

- `ETB_ORION_CLARIFY`
  - `1` (default): run the Orion `orion_gate` node before retrieval in the orchestrator LangGraph.
  - `0`, `false`, `no`, or `off`: skip Orion and go straight to retrieve + answer (same as the CLI default for `build_rag_graph(..., enable_orion_gate=False)`).

Service wiring:

- `RETRIEVER_BASE_URL` (required)
  - Base URL for the Retriever API, e.g. `http://retriever:8000` in Docker Compose.
- `ORCH_RETRIEVER_K`
  - Default top-k for retrieval (used when the request body does not specify `k`).
- `ETB_ORCH_HOST`
  - Bind address for `python -m etb_project.orchestrator` (default `0.0.0.0`).
- `ETB_ORCH_PORT` or `PORT`
  - Listen port (default `8001`).

LLM provider selection:

- `ETB_LLM_PROVIDER`: `openai_compat` (default) or `ollama`

OpenAI-compatible provider (includes OpenRouter via `OPENAI_BASE_URL`):

- `OPENAI_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (default: `stepfun/step-3.5-flash`)
- `OPENAI_TEMPERATURE` (default: `0`)

Ollama provider:

- `OLLAMA_HOST` (or `OLLAMA_BASE_URL`)
- `OLLAMA_CHAT_MODEL` (default: `qwen3.5:9b`)
- `OLLAMA_TEMPERATURE` (default: `0`)

Sessions and CORS:

- `ORCH_SESSION_TTL_SECONDS` (default: 7200)
- `ORCH_CORS_ALLOW_ORIGINS` (comma-separated; optional)

### Error envelope

Errors return JSON:

```json
{ "code": "STRING", "message": "human readable", "detail": "optional" }
```

Common codes:

- `VALIDATION_ERROR` (422)
- `CONFIG_ERROR` (500): missing `RETRIEVER_BASE_URL`
- `EMPTY_ANSWER` (502)

## Related docs

- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`RETRIEVER_API.md`](RETRIEVER_API.md)
- [`APP_RUN_MODES.md`](APP_RUN_MODES.md)
