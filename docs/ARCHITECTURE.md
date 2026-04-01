# Architecture Documentation

## Overview

ETB-project separates **index building** (document processing + persisted vector stores) from **runtime querying** (RAG orchestration). Runtime querying can run either:

- **Local mode**: load persisted indices and retrieve in-process (developer workflow)
- **Remote mode**: call a **standalone retriever HTTP API** for retrieval and indexing (deployment workflow)

This keeps the RAG layer flexible while the retriever can be deployed/scaled as a separate unit.

For operational “how-to” instructions, see the guides in [`docs/README.md`](README.md).

## Project structure

Repository layout (paths relative to repo root):

```
ETB-Project/
├── app.py                      # Streamlit UI → Orchestrator `POST /v1/chat`
├── docker-compose.yml          # UI + orchestrator + retriever + Ollama
├── Dockerfile
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── src/
│   ├── config/
│   │   └── settings.yaml       # Primary YAML (override with ETB_CONFIG)
│   └── etb_project/            # Installed package (`pip install -e .`)
│       ├── config.py           # AppConfig, load_config
│       ├── main.py             # CLI RAG (local or remote retriever)
│       ├── models.py           # LLM + embedding helpers
│       ├── api/                # Retriever FastAPI (retrieve, index, assets)
│       ├── orchestrator/       # Agentic LangGraph + FastAPI (chat, asset proxy)
│       ├── ui/                 # Shared UI helpers (asset paths, headers)
│       ├── document_processing/
│       ├── document_processor_cli.py
│       ├── retrieval/          # Dual retriever + RemoteRetriever client
│       └── vectorstore/        # FAISS backends + indexing service
├── tools/                      # Not installed with the package
│   └── data_generation/
├── tests/
├── docs/
└── data/                       # Uploads, document_output, vector indices (typical)
```

Code under `tools/` is **not** part of the installed package. See [`TOOLS.md`](TOOLS.md).

## Design principles

### 1. Modularity
- Code is organized into logical modules
- Each module has a single responsibility
- Clear separation of concerns

### 2. Type safety
- Type hints throughout the codebase
- Static type checking with MyPy
- Runtime type validation where needed

### 3. Testability
- Dependency injection for testability
- Mock-friendly design
- Comprehensive test coverage

### 4. Scalability
- Designed for horizontal scaling
- Stateless services where possible
- Efficient resource usage

## Core components

### Main application (`etb_project.main`)

- Loads configuration from `src/config/settings.yaml` (or `ETB_CONFIG`)
- Uses **local** or **remote** retrieval via `ETB_RETRIEVER_MODE` and `RETRIEVER_BASE_URL`
- If **`query`** is set: **retrieval only** (logs document snippets; no LangGraph, no LLM)
- If **`query`** is empty: **interactive agent** LangGraph ([`build_agent_orchestrator_graph`](../src/etb_project/orchestrator/agent_graph.py)) with either **local** `DualRetriever` (persisted FAISS) or **remote** [`RemoteRetriever`](../src/etb_project/retrieval/remote_retriever.py). Same tools and guardrails as the HTTP orchestrator; prior turns are kept in-process via `messages` (session id `cli`, new `request_id` per line). Chat LLM is **Ollama** via `get_ollama_llm()`.

### Runtime services (Docker / production-style)

```mermaid
flowchart TB
  UI[Streamlit app.py]
  Orch[Orchestrator API :8001]
  Ret[Retriever API :8000]
  Ollama[Ollama embeddings]
  RAG[LangGraph RAG in orchestrator]
  LLM[Chat LLM]

  UI -->|POST /v1/chat| Orch
  UI -->|GET /v1/assets/... proxy| Orch
  Orch --> RAG
  RAG -->|POST /v1/retrieve| Ret
  RAG --> LLM
  Ret --> Ollama
  Orch -->|GET /v1/assets/... forward| Ret
```

- **Orchestrator** (`etb_project.orchestrator`): session chat, **agentic** LangGraph ([`agent_graph.py`](../src/etb_project/orchestrator/agent_graph.py)), calls the **Retriever HTTP API** via [`RemoteRetriever`](../src/etb_project/retrieval/remote_retriever.py) only (`POST /v1/retrieve`), proxies `GET /v1/assets/{path}` to the retriever for UI image/artifact bytes.

#### Agentic orchestrator (`POST /v1/chat`)

The orchestrator runs a **hand-rolled LangGraph** (`invoke_agent` → `execute_tools` → conditional loop). LangGraph’s `create_react_agent` / generic `ToolNode` were not used so we keep full control over **`accumulated_docs`**, merge/dedupe, clarify/finalize short-circuits, and step limits. The chat LLM uses **tool calls** (`retrieve`, `ask_clarify`, `finalize_answer`) with guardrails from [`load_orchestrator_settings()`](../src/etb_project/orchestrator/settings.py): `ETB_AGENT_MAX_RETRIEVE`, `ETB_AGENT_MAX_STEPS`, `ETB_AGENT_MAX_CONTEXT_CHARS`. Retrieved chunks are **merged and deduped in state by content** (SHA-256 of stripped text; substring containment; optional consecutive boundary overlap), not by metadata `source` alone—so multiple chunks from the same PDF (e.g. text vs image captions) are not collapsed. Grounded generation uses [`llm_messages.py`](../src/etb_project/orchestrator/llm_messages.py) (delimiter-wrapped context). The graph runs under **`asyncio.to_thread(graph.invoke, ...)`** in the FastAPI handler.

#### Agentic workflow (diagrams)

**Architecture** — main components and dependencies (production-style path: UI → orchestrator → retriever; LLM is configured inside the orchestrator).

```mermaid
flowchart LR
  ui[Streamlit UI]
  orch[Orchestrator API]
  sess[Session messages]
  graph[Agent graph]
  llm[Chat LLM]
  ret[Retriever API]

  ui -->|POST /v1/chat| orch
  orch --> sess
  orch --> graph
  graph --> llm
  graph --> ret
```

**Workflow** — what happens for **one** user message (simplified; the graph may loop on tools until it finishes).

```mermaid
flowchart TD
  a[User message in UI] --> b[Orchestrator loads prior session messages]
  b --> c[Graph ingests query and resets per-turn doc state]
  c --> d[LLM chooses a tool or replies]
  d --> e{Tool?}
  e -->|retrieve| f[Call Retriever HTTP POST /v1/retrieve]
  f --> g[Merge chunks into graph state]
  g --> d
  e -->|ask_clarify| h[Return clarify reply to user]
  e -->|finalize_answer| i[Grounded answer from merged context]
  e -->|no tool| j[Direct text reply if any]
  i --> k[Save messages to session]
  h --> k
  j --> k
  k --> l[HTTP response to UI]
```

Details: `retrieve` may run multiple times per turn (up to `ETB_AGENT_MAX_RETRIEVE`); `finalize_answer` ends grounded answering. Guardrails (`ETB_AGENT_MAX_STEPS`, `ETB_AGENT_MAX_CONTEXT_CHARS`) are enforced inside [`agent_graph.py`](../src/etb_project/orchestrator/agent_graph.py).

When `ETB_GROUNDED_FINALIZE_MODE=subagent`, the finalize path runs the optional **grounded writer** subgraph in [`grounded_subagent/`](../src/etb_project/grounded_subagent/) (inner tools, separate `ETB_WRITER_*` limits, then `submit_final_answer` or a direct fallback). Default `direct` keeps a single non-tool grounded LLM call. See [`ORCHESTRATOR_API.md`](ORCHESTRATOR_API.md).

**LangGraph Studio** ([`studio_entry.py`](../src/etb_project/studio_entry.py)) builds the same graph with **`RemoteRetriever`** only (`RETRIEVER_BASE_URL` required).

- **Retriever** (`etb_project.api`): dual FAISS retrieval, PDF indexing, serves files from `ETB_DOCUMENT_OUTPUT_DIR` under `/v1/assets/...`.
- **UI** (`app.py`): talks only to the orchestrator (chat + assets).

### CLI / developer flow

```mermaid
flowchart LR
  Config[AppConfig] --> Main[main.py]
  Main --> Mode{ETB_RETRIEVER_MODE}
  Mode -->|local| Load[Load FAISS from disk]
  Mode -->|remote| Client[RemoteRetriever HTTP client]
  Load --> Dual[DualRetriever]
  Client --> Ret[Retriever invoke]
  Dual --> Ret
  Main --> Q{query set?}
  Q -->|yes| Snip[Log retrieval snippets only]
  Q -->|no| RAG2[Agent graph plus same retriever]
  Ret --> Snip
  Ret --> RAG2
  RAG2 --> OllamaLLM[Ollama chat LLM]
```

- **Config** (`etb_project.config`): `AppConfig` — `pdf`, `query`, `retriever_k`, `log_level`, `vector_store_path`, captioning keys.
- **Remote retriever client** (`etb_project.retrieval.remote_retriever.RemoteRetriever`): `POST /v1/retrieve` to the retriever service.
- **Agent graph** (`etb_project.orchestrator.agent_graph`): interactive CLI (**local or remote** retriever), LangGraph Studio (**remote** only), HTTP orchestrator; **Ollama** chat in `main` / Studio; orchestrator uses `get_chat_llm()` for OpenAI-compat / OpenRouter.

### Standalone retriever API

Exposes:

- `GET /v1/health`, `GET /v1/ready`
- `POST /v1/retrieve` — chunks with JSON-safe metadata (including nested fields like `image_captions`)
- `POST /v1/index/documents` — multipart PDF upload; optional async job + `GET /v1/jobs/{job_id}`
- `GET /v1/assets/{asset_path}` — files under `ETB_DOCUMENT_OUTPUT_DIR` (optional bearer auth)

The RAG graph does **not** run inside this service. Point the orchestrator or CLI at it with:

- `ETB_RETRIEVER_MODE=remote`
- `RETRIEVER_BASE_URL=http://<host>:8000`

### Index building (offline / batch)

Separate workflow (CLI or API) that extracts text/images, optional captioning, builds/persists vector indices. See:

- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`CLI_REFERENCE.md`](CLI_REFERENCE.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)

## Development and operations

- [`DEVELOPMENT.md`](DEVELOPMENT.md)

## Related docs

- [`README.md`](README.md) (index)
- [`APP_RUN_MODES.md`](APP_RUN_MODES.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`RETRIEVER_API.md`](RETRIEVER_API.md)
- [`ORCHESTRATOR_API.md`](ORCHESTRATOR_API.md)
- [`USAGE.md`](USAGE.md)
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
- [`TOOLS.md`](TOOLS.md)

## References

- [Python Packaging User Guide](https://packaging.python.org/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Pytest Documentation](https://docs.pytest.org/)
