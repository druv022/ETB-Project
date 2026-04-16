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

### Conda (`ETB` environment)

If you use Miniconda/Anaconda, activate the **`ETB`** environment (create it first if needed), then install as above:

```bash
conda activate ETB
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
```

Run tests without manually activating (use your env name: **`ETB`**, **`etb`**, or whatever you created):

```bash
conda run -n ETB pytest
# or
conda run -n etb pytest
```

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

## RAGAS evaluation (offline)

This repo includes a **decoupled** evaluation tool that treats the orchestrator as a **black-box HTTP service**.

- **Install eval deps** (recommended in conda `etb` env):

```bash
conda run -n etb pip install -e ".[eval]"
```

- **Run a full synthetic eval pipeline** (PDF → synthetic questions → call `/v1/chat` → RAGAS → HTML):

```bash
conda run -n etb python -m etb_project.evaluation pipeline \
  --pdf "path/to/your.pdf" \
  --testset-size 20 \
  --orchestrator-base-url "http://localhost:8001"
```

- **Outputs**:
  - `data/evals/dashboard.html` (all runs + filters)
  - `data/evals/runs/<run_id>/report.html` (per-run detail)

**RAGAS metric scoring** uses an OpenAI-compatible API (required for `evaluate`):
- `ETB_EVAL_OPENAI_API_KEY` (or `OPENAI_API_KEY`)
- `ETB_EVAL_OPENAI_BASE_URL` (or `OPENAI_BASE_URL`) when not using the default OpenAI endpoint
- `ETB_EVAL_METRICS_MODEL` (default `gpt-4o-mini`) — judge LLM for faithfulness, precision, etc.
- `ETB_EVAL_EMBEDDING_MODEL` (default `text-embedding-3-small`) — embeddings for answer relevancy and answer correctness

**Notes + git commit (optional):**
- Disable AI Notes: add `--no-notes-llm`
- Enable git commits for each run: add `--git-commit` (or set `ETB_EVAL_GIT_COMMIT=1`)
- Notes LLM config (OpenAI-compatible):
  - `ETB_EVAL_NOTES_MODEL` (default `gpt-4o-mini`)
  - `ETB_EVAL_OPENAI_API_KEY` (or `OPENAI_API_KEY`)
  - `ETB_EVAL_OPENAI_BASE_URL` (or `OPENAI_BASE_URL`)

**Batch eval tip:** set `ETB_ORION_CLARIFY=0` for the orchestrator so it reliably enters the retrieve+answer path.

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
