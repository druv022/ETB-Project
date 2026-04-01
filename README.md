# ETB-project

An enterprise chatbot-style RAG project for querying PDF content using persisted vector indices (text + optional image-caption retrieval).

## Features

- Dual retrieval (text chunks + image captions), merged for RAG
- Persisted vector indices (build once, load for runtime querying)
- Optional pluggable image captioning backends (OpenRouter/OpenAI)
- Modern Python tooling: Ruff, Black, MyPy, pytest, pre-commit, Docker

## Requirements

- Python 3.10+ (see `requires-python` in `pyproject.toml`)
- pip (or [uv](https://github.com/astral-sh/uv) if you use the lockfile)

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

If you use **uv** and `uv.lock`:

```bash
uv sync --all-extras
```

### Conda (`etb` environment)

Use the **`etb`** conda environment for local development (create it first if needed):

```bash
conda create -n etb python=3.11 -y
conda activate etb
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

Run tools **without** manually activating:

```bash
conda run -n etb pytest
conda run -n etb pre-commit run --all-files
conda run -n etb python -m streamlit run app.py
conda run -n etb python -m uvicorn etb_project.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

If your environment is named **`ETB`** (capital letters) instead, substitute that name in the commands above.

## Quickstart

1. Create a `.env` (e.g. `OPENROUTER_API_KEY=...` for the orchestrator’s OpenAI-compatible client) and configure `src/config/settings.yaml`, or set `ETB_CONFIG` to another YAML path.

2. Start everything (UI + orchestrator + retriever + Ollama) with Docker:

```bash
docker compose up --build
```

The repo ships a **standalone retriever HTTP API** (retrieve + index PDFs). The **LangGraph RAG** graph runs in the **orchestrator**, not in the retriever. The orchestrator can run an **Orion** clarification step before retrieval (`ETB_ORION_CLARIFY`, default on); see [`docs/ORCHESTRATOR_API.md`](docs/ORCHESTRATOR_API.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

3. Open the UI:

- `http://localhost:8501`

**Docker note (Sources / images):** The retriever stores extracted PDF images under `ETB_DOCUMENT_OUTPUT_DIR` (Compose sets this to `/app/data/document_output` on the shared `etb_data` volume). The Streamlit UI loads them via the orchestrator at `GET /v1/assets/...`. If you set `RETRIEVER_API_KEY` on the retriever, set the same value in the UI environment (e.g. in `.env` used by Compose) as `RETRIEVER_API_KEY` or `ORCHESTRATOR_ASSET_BEARER_TOKEN` so image requests are authorized.

### Streamlit UI (login, admin, API tokens)

The Orion UI requires **login**. The first screen is a centered, fixed max-width card (~28rem) with **Sign in** and **Create account** tabs so the form stays consistent across window sizes (forms with rate limiting). General users **register** in the app (SQLite DB; Compose persists it at `ETB_USERS_DB_PATH`, default `/app/data/users.sqlite` on the `etb_data` volume). **Admin** uses fixed credentials from the environment or Streamlit secrets (not from the UI):

| Variable | Purpose |
| --- | --- |
| `ETB_ADMIN_USERNAME` / `ETB_ADMIN_PASSWORD` | Admin sign-in only (cannot be changed in the UI). |
| `ETB_ADMIN_API_TOKEN` | Bearer for `/v1/admin/*` on **orchestrator** and **retriever** (Logs, document list/delete/reindex). Use the **same** secret in all three places. |
| `ETB_ORCHESTRATOR_API_KEY` | When set, `POST /v1/chat` requires `Authorization: Bearer`; the UI sends this automatically if the variable is set for Streamlit. |
| `RETRIEVER_API_KEY` | When set on the retriever, required for indexing/uploads and job polling from the UI. |

Local Streamlit can use [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) as a template (copy to `.streamlit/secrets.toml`).

### Verification (tests and smoke)

```bash
conda run -n etb pytest tests/test_user_auth_store.py tests/test_orchestrator_admin_auth.py tests/test_retriever_admin_routes.py tests/test_orchestrator_api.py tests/test_api_retriever.py -q
```

With `ETB_ORCHESTRATOR_API_KEY` and `ETB_ADMIN_API_TOKEN` set on running services, quick HTTP checks:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://localhost:8001/v1/chat -H "Content-Type: application/json" -d '{"session_id":"x","message":"hi"}'
# Expect 401 when the orchestrator chat key is set and no Bearer header.

curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8001/v1/admin/recent-logs
# Expect 401 when admin token is set; 404 when admin token is unset on the server.
```

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
- **CLI RAG (`python -m etb_project.main`)**: [`docs/USAGE.md`](docs/USAGE.md) — single-query vs interactive; Ollama-only chat in CLI vs orchestrator OpenRouter
- **Run modes (updated)**: [`docs/APP_RUN_MODES.md`](docs/APP_RUN_MODES.md)
- **Retriever HTTP API**: [`docs/RETRIEVER_API.md`](docs/RETRIEVER_API.md)
- **Orchestrator HTTP API**: [`docs/ORCHESTRATOR_API.md`](docs/ORCHESTRATOR_API.md)
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
├── app.py                    # Streamlit UI → Orchestrator API
├── docker-compose.yml        # UI, orchestrator, retriever, Ollama
├── Dockerfile
├── Makefile
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── src/
│   ├── config/
│   │   └── settings.yaml     # Primary YAML (see docs/CONFIGURATION.md)
│   └── etb_project/          # Main package (`pip install -e .`)
│       ├── api/              # Retriever FastAPI
│       ├── orchestrator/       # Orchestrator FastAPI (chat + asset proxy)
│       ├── ui/                 # Shared helpers for Streamlit (e.g. asset paths)
│       ├── document_processing/
│       ├── retrieval/
│       ├── vectorstore/
│       ├── main.py
│       ├── graph_rag.py
│       └── ...
├── docker/                   # Ollama entrypoint / healthchecks
├── docs/                     # Start with docs/README.md
├── tools/                    # Not installed with the package
├── tests/
└── data/                     # Typical: uploads, document_output, vector indices
```

For a fuller component diagram and boundaries, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

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
