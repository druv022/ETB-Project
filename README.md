# ETB-project

An enterprise chatbot-style RAG project for querying PDF content using persisted vector indices (text + optional image-caption retrieval).

## Features

- Dual retrieval (text chunks + image captions), merged for RAG
- Persisted vector indices (build once, load for runtime querying)
- Optional pluggable image captioning backends (OpenRouter/OpenAI)
- Modern Python tooling: Ruff, Black, MyPy, pytest, pre-commit, Docker

## Requirements

- Python 3.10+
- pip (or poetry)

## Installation

```bash
# Clone the repository
git clone https://github.com/druv022/etb_project.git
cd etb_project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies + dev tools
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install the local package so `python -m etb_project.main` and pytest imports work
pip install -e .
```

## Quickstart

1) Create a `.env` with at least:
1) Configure `src/config/settings.yaml` (or set `ETB_CONFIG` to an alternate YAML).

2) Run the RAG app (local FAISS):

```bash
OPENROUTER_API_KEY=...
```

2) Start everything (UI + orchestrator + retriever + embeddings):
### Standalone retriever API (recommended for Docker deployments)

This repo now includes a **standalone retriever HTTP API** (retrieve chunks + index PDFs). The **LangGraph RAG** graph stays outside of the retriever.

- **Start retriever + embeddings with Docker**:

```bash
docker compose up --build
```

3) Open the UI:

- `http://localhost:8501`

**Docker note (Sources / images):** The retriever stores extracted PDF images under `ETB_DOCUMENT_OUTPUT_DIR` (Compose sets this to `/app/data/document_output` on the shared `etb_data` volume). The Streamlit UI loads them via the orchestrator at `GET /v1/assets/...`. If you set `RETRIEVER_API_KEY` on the retriever, set the same value in the UI environment (e.g. in `.env` used by Compose) as `RETRIEVER_API_KEY` or `ORCHESTRATOR_ASSET_BEARER_TOKEN` so image requests are authorized.

For other run modes (CLI, provider switching, health checks, etc.), see [`docs/APP_RUN_MODES.md`](docs/APP_RUN_MODES.md).
Compose starts **Ollama** (pulls the embedding model automatically), then the **retriever** once Ollama is healthy.

- **Check health**:

```bash
curl http://localhost:8000/v1/health
curl http://localhost:8000/v1/ready
```

- **Use the RAG orchestrator against the retriever**:

```bash
export ETB_RETRIEVER_MODE=remote
export RETRIEVER_BASE_URL=http://localhost:8000
python -m etb_project.main
```

If you need to build/update the persisted indices first (PDF preprocessing, chunking, optional captioning), see the docs below.

## Documentation

- **Start here**: [`docs/README.md`](docs/README.md)
- **Run modes (updated)**: [`docs/APP_RUN_MODES.md`](docs/APP_RUN_MODES.md)
- **Configure the project**: [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- **Preprocess PDFs + build/update indices**: [`docs/DOCUMENT_PROCESSING.md`](docs/DOCUMENT_PROCESSING.md)
- **Document processor CLI flags**: [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md)
- **Image captioning backends**: [`docs/IMAGE_CAPTIONING.md`](docs/IMAGE_CAPTIONING.md)
- **Development workflows**: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- **Tools under `tools/`**: [`docs/TOOLS.md`](docs/TOOLS.md)
- **Architecture overview**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Project Structure

```
ETB-Project/
├── app.py                          # Streamlit UI entrypoint
├── docker-compose.yml              # UI + orchestrator + retriever (+ Ollama) runtime
├── Dockerfile
├── Makefile
etb_project/
├── src/
│   ├── config/                # settings.yaml (and optional config module)
│   │   ├── config.py
│   │   └── settings.yaml
│   └── etb_project/           # Main package (installed with pip install .)
│       ├── __init__.py
│       ├── config.py          # AppConfig and load_config (reads settings.yaml / ETB_CONFIG)
│       ├── main.py            # Entry point: load persisted indices, run single-query or interactive RAG loop
│       ├── models.py          # LLM and embedding helpers
│       ├── graph_rag.py       # LangGraph RAG graph (ingest_query → retrieve_rag → generate_answer)
│       ├── api/               # Standalone retriever HTTP API (no RAG graph)
│       └── retrieval/
│           ├── __init__.py    # Re-exports retrieval helpers and DualRetriever adapter
│           ├── loader.py     # load_pdf (PyPDFLoader)
│           ├── process.py    # split_documents, store_documents (pre-stacked embeddings → FAISS), dual index builders
│           └── dual_retriever.py # Single-query adapter that merges text/caption retrieval results
├── tools/                     # Utilities and side projects (not installed)
│   └── data_generation/
├── tests/
│   ├── test_config.py
│   ├── test_main.py
│   ├── test_models.py
│   └── test_retrieval_process.py
├── docs/
│   ├── README.md
│   ├── CONTRIBUTING.md
│   ├── USAGE.md
│   ├── CONFIGURATION.md
│   ├── DOCUMENT_PROCESSING.md
│   ├── CLI_REFERENCE.md
│   ├── IMAGE_CAPTIONING.md
│   ├── DEVELOPMENT.md
│   ├── TOOLS.md
│   └── ARCHITECTURE.md
├── .github/workflows/
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── docs/                           # Project docs (start with docs/README.md)
├── docker/                         # Container scripts/healthchecks
├── data/                           # Persisted artifacts (uploads, outputs, vector indices)
├── tools/                          # Utilities / side projects (not installed as package)
├── tests/                          # pytest suite
└── src/
    ├── config/
    │   └── settings.yaml           # Primary config file (see docs/CONFIGURATION.md)
    └── etb_project/                # Main package (installed with `pip install -e .`)
        ├── __init__.py
        ├── config.py
        ├── main.py
        ├── models.py
        ├── graph_rag.py
        ├── studio_entry.py
        ├── document_processor_cli.py
        ├── document_processing/
        ├── retrieval/              # Retrieval orchestration + local/remote retrievers
        ├── vectorstore/            # FAISS persistence/indexing services
        ├── api/                    # Retriever FastAPI service
        └── orchestrator/           # Orchestrator FastAPI service (UI talks to this)
```

## Contributing

Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the Apache-2.0 License - see the LICENSE file for details.

## Author

**Dhruba Pujary**

- Email: pujarydhruba@gmail.com
- GitHub: [@druv022](https://github.com/druv022)

## Acknowledgments

- Built with [Cookiecutter](https://github.com/cookiecutter/cookiecutter)
- Optimized for [Cursor IDE](https://cursor.sh/)
