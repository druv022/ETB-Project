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

#### `POST /v1/transactions/query`

Bounded, parameterized reads from the local synthetic SQLite **`transactions`** table (same schema as the reporting tools under `tools/data_generation/`). Intended for **subagents** and internal automation; there is **no separate API key** on this route—expose the orchestrator only on a trusted network.

Request body:

```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "filters": { "Store_Region": ["West", "East"] },
  "limit": 500,
  "include_catalog": true
}
```

- `start_date` / `end_date`: optional, ISO `YYYY-MM-DD`, applied to `Transaction_Date`.
- `filters`: optional map of **allowlisted** column names to string lists (`IN` query). Allowed keys: `Transaction_ID`, `Transaction_Date`, `Transaction_Time`, `Store_ID`, `Store_Region`, `Order_Channel`, `Customer_ID`, `Customer_Type`, `Product_ID`, `SKU`.
- `limit`: default `500`, maximum `2000`. The response sets `truncated: true` when more rows matched than returned.
- `include_catalog`: when `true` (default), merges `Category` from `PRODUCT_CATALOG.csv` when that file exists at the configured path.

Response:

```json
{
  "rows": [{ "Transaction_ID": "...", "Net_Sales_Value": 1.0 }],
  "row_count": 1,
  "truncated": false,
  "detail": null
}
```

`detail` may explain empty data (e.g. missing seed DB/SQL) or append a truncation note.

**Operational note:** Importing from a large seed `.sql` on first access is **slow** and blocks the worker. Prefer a **pre-built `.db`**. Auto-import from SQL only runs when `ETB_TRANSACTION_AUTO_BUILD_DB` is truthy (`1`, `true`, `yes`, `on`).

Example:

```bash
curl -sS -X POST http://localhost:8001/v1/transactions/query \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "include_catalog": false}'
```

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

**Transaction SQLite** (for `POST /v1/transactions/query`):

Paths are resolved from the **repository root** (parent of `src/`) when relative.

- `ETB_TRANSACTION_DB` — SQLite file path (default: `data/transaction_database_5yrs_full.db`).
- `ETB_TRANSACTION_SQL` — optional explicit seed `.sql` path (default: same path as the DB with extension `.sql`).
- `ETB_TRANSACTION_AUTO_BUILD_DB` — when set, allows one-time creation of the DB by running the seed SQL script (expensive for large files).
- `ETB_PRODUCT_CATALOG` — optional CSV path for category join (default: `tools/data_generation/Transaction_data/Ed_Data/PRODUCT_CATALOG.csv`).

In Docker, **mount** the host folder that contains the `.db` (and optional `.sql`/CSV) so these paths exist inside the orchestrator container.

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
