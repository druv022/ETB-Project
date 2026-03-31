## Standalone Retriever API (v1)

This service is the **standalone retriever unit** for ETB-project.

- **In scope**: dual FAISS retrieval (text + caption indices), PDF upload + append/rebuild indexing
- **Out of scope**: LangGraph RAG graph and LLM answer generation (kept in the orchestrator, e.g. `etb_project.main`)

### Run (Docker)

```bash
docker compose up --build
```

The API listens on `:8000` (see `docker-compose.yml`).

The **Ollama** service starts, **pulls the default embedding model** (`qwen3-embedding:0.6b`, overridable via `OLLAMA_EMBEDDING_MODEL`), and becomes healthy before the retriever starts. The retriever container sets **`OLLAMA_HOST=http://ollama:11434`** (the `ollama` Python client reads `OLLAMA_HOST`, not `OLLAMA_BASE_URL`).

### Endpoints

#### `GET /v1/health`

Liveness check.

#### `GET /v1/ready`

Readiness check. Returns:

- `index_ready`: whether the persisted index exists at `vector_store_path`
- `embeddings_ok`: whether the embeddings backend responds

#### `POST /v1/retrieve`

Request body:

```json
{ "query": "string", "k": 10 }
```

Response body:

```json
{
  "chunks": [
    { "content": "string", "metadata": { "source": "file.pdf", "page": 1 } }
  ]
}
```

Notes:

- `k` is optional; when omitted it defaults to `retriever_k` from `settings.yaml`.
- `k` is bounded by configuration (`ETB_MAX_RETRIEVE_K`, max 100).
- Requests may be rate limited (429) based on `ETB_RATE_LIMIT_PER_MINUTE`.

#### `POST /v1/index/documents`

Multipart form upload of one or more `.pdf` files. Query params:

- `reset=true|false`: when true, deletes the existing persisted VDB and rebuilds.
- `async_mode=true|false` (optional): override server default for async job mode (default comes from `ETB_INDEX_ASYNC`).

Async mode returns `202` with a `job_id`. Poll:

- `GET /v1/jobs/{job_id}`

### Auth (optional)

If `RETRIEVER_API_KEY` is set on the service, requests must include:

- `Authorization: Bearer <RETRIEVER_API_KEY>`

### Indexing behavior (important)

- The API **writes uploaded PDFs** to `ETB_UPLOAD_DIR` (default `data/uploads/`).
- It writes extracted artifacts to `ETB_DOCUMENT_OUTPUT_DIR` (default `data/document_output/`).
- Chunking uses `ETB_CHUNK_SIZE` (default 1000) and `ETB_CHUNK_OVERLAP` (default 200).
- Vector store persistence location comes from `vector_store_path` in `src/config/settings.yaml` (or `ETB_CONFIG` override).

### Error codes

Errors return JSON:

```json
{ "code": "STRING", "message": "human readable", "detail": "optional" }
```

Common codes:

- `INDEX_NOT_READY` (503): index not built yet
- `INDEX_BUSY` (423): indexing already in progress
- `OLLAMA_UNAVAILABLE` (503): embeddings backend failed/unreachable
- `RATE_LIMITED` (429): request rate exceeded
- `UNAUTHORIZED` (401): missing/invalid bearer token
- `PAYLOAD_TOO_LARGE` (413): request body exceeded `ETB_MAX_RETRIEVE_BODY_BYTES`
- `FILE_TOO_LARGE` (413): uploaded PDF exceeds `ETB_MAX_UPLOAD_BYTES`
- `TOO_MANY_FILES` (400): too many PDFs in one request (see `ETB_MAX_UPLOAD_FILES`)
- `UNSUPPORTED_MEDIA_TYPE` (415): only PDFs are accepted

### Orchestrator (RAG) usage

To run the RAG orchestrator against the retriever service:

```bash
export ETB_RETRIEVER_MODE=remote
export RETRIEVER_BASE_URL=http://localhost:8000
python -m etb_project.main
```
