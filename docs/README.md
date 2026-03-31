# Documentation index

This folder contains the detailed documentation for ETB-project. If you are new to the repo, start with the root [`README.md`](../README.md) for quickstart instructions, then use the pages below for deeper guidance.

## System overview (current)

At runtime (recommended), ETB runs as three services:

- **UI** (`app.py`, Streamlit) → **Orchestrator API** (`POST /v1/chat`, `GET /v1/assets/...` for images)
- **Orchestrator API** (`src/etb_project/orchestrator/`, FastAPI) → LangGraph RAG, `POST /v1/retrieve` to the retriever, proxies assets from the retriever
- **Retriever API** (`src/etb_project/api/`, FastAPI) → dual FAISS retrieval, PDF indexing, static files under `/v1/assets/...` (no LLM answer generation)

Docker Compose starts all three (plus **Ollama** for embeddings).

## Guides (how to use the project)

- [`APP_RUN_MODES.md`](APP_RUN_MODES.md): updated ways to run the UI + orchestrator + retriever (Docker) and CLI modes.
- [`USAGE.md`](USAGE.md): how to run the RAG app (single-query vs interactive) and what it does at runtime.
- [`CONFIGURATION.md`](CONFIGURATION.md): all configuration knobs (YAML + environment variables) and common setups.
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md): how to preprocess PDFs, generate artifacts, and build/update persisted vector stores.
- [`CLI_REFERENCE.md`](CLI_REFERENCE.md): complete CLI flag reference for `python -m etb_project.document_processor_cli`.
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md): image captioning backends (OpenRouter/OpenAI/mock), config precedence, metadata flow.
- [`RETRIEVER_API.md`](RETRIEVER_API.md): retriever service endpoints (health/ready/retrieve/index/jobs), auth, and error codes.
- [`ORCHESTRATOR_API.md`](ORCHESTRATOR_API.md): orchestrator endpoints (health/ready/chat/assets), `get_chat_llm()` providers (`ETB_LLM_PROVIDER`), sessions, CORS.

## Developer documentation

- [`DEVELOPMENT.md`](DEVELOPMENT.md): development setup, tests, lint/type-check, pre-commit, and Docker.
- [`TOOLS.md`](TOOLS.md): utilities under `tools/` (not installed with the package), including data generation and standalone captioning.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system boundaries and data flows (high-level; links out to the guides above).

## Contributing

- [`CONTRIBUTING.md`](CONTRIBUTING.md): contribution guidelines and PR process.
