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

- `ready`: whether required dependencies are configured
- `retriever_base_url`: current retriever base URL
- `llm_configured`: whether the chat LLM can be constructed from environment

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
  "request_id": "string"
}
```

### Configuration (environment variables)

Service wiring:

- `RETRIEVER_BASE_URL` (required)
  - Base URL for the Retriever API, e.g. `http://retriever:8000` in Docker Compose.
- `ORCH_RETRIEVER_K`
  - Default top-k for retrieval (used when the request body does not specify `k`).

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
