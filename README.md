# ETB-project

An enterprise chatbot-style RAG project for querying PDF content using persisted vector indices (text + optional image-caption retrieval).

## Features

- Dual retrieval (text chunks + image captions), merged for RAG
- Persisted vector indices (build once, load for runtime querying)
- Optional pluggable image captioning backends (OpenRouter/OpenAI/mock)
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

1) Configure `src/config/settings.yaml` (or set `ETB_CONFIG` to an alternate YAML).

2) Run the app:

```bash
python -m etb_project.main
make run
```

If you need to build/update the persisted indices first (PDF preprocessing, chunking, optional captioning), see the docs below.

## Documentation

- **Start here**: [`docs/README.md`](docs/README.md)
- **Run the RAG app**: [`docs/USAGE.md`](docs/USAGE.md)
- **Configure the project**: [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- **Preprocess PDFs + build/update indices**: [`docs/DOCUMENT_PROCESSING.md`](docs/DOCUMENT_PROCESSING.md)
- **Document processor CLI flags**: [`docs/CLI_REFERENCE.md`](docs/CLI_REFERENCE.md)
- **Image captioning backends**: [`docs/IMAGE_CAPTIONING.md`](docs/IMAGE_CAPTIONING.md)
- **Development workflows**: [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)
- **Tools under `tools/`**: [`docs/TOOLS.md`](docs/TOOLS.md)
- **Architecture overview**: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

## Project Structure

```
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
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── README.md
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
