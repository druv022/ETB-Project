# ETB-project

An Enterprise Chatbot

## Features

- Modern Python project structure
- Type hints and static type checking with MyPy
- Code formatting with Black and Ruff
- Comprehensive testing with pytest
- Pre-commit hooks for code quality
- Docker support for containerized development
- CI/CD pipelines with GitHub Actions
- Cursor IDE optimized with `.cursorrules`

## Requirements

- Python 3.10+
- pip or poetry for dependency management

## Installation

### Using pip

```bash
# Clone the repository
git clone https://github.com/druv022/etb_project.git
cd etb_project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt

# Install the local package so `python -m etb_project.main` and pytest imports work
pip install -e .
```

### Using poetry

```bash
# Install poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

## Usage

Configure a PDF path and optional query (see [Configuration](#configuration)), then run:

```bash
# From project root (with package installed: pip install -e .)
python -m etb_project.main

# Or using make
make run
```

- If `query` is set in config, the app runs that single query and logs the retrieval results.
- If `query` is empty, the app enters an **interactive loop**: type a question and press Enter to see retrieved chunks; empty line or Ctrl+C to exit.

## Tools (not installed)

Utility scripts and side projects live under `tools/` and are **not** part of the installed package. They are for development and one-off tasks only.

### Data generation

Data generation scripts are in `tools/data_generation/`. They are not installed with `pip install .`.

**How to run:**

1. From the project root, set `PYTHONPATH` so Python can find the `tools` package:
   ```bash
   PYTHONPATH=. python -m tools.data_generation
   ```
2. Or run a specific script inside the folder:
   ```bash
   python tools/data_generation/your_script.py
   ```

## Development

### Setup

1. Clone the repository
2. Create a virtual environment
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Install the package in editable mode: `pip install -e .`
5. Install git hooks: `pre-commit install` (installs both pre-commit and pre-push hooks; or use `make install-dev`)
6. Copy `.env.example` to `.env` and configure

Pre-push hooks run the same lint and format checks as CI (Ruff, Black, MyPy) so that failed checks are caught before you push.

### Running Tests

From project root, with the package on the path (e.g. `pip install -e .` or `PYTHONPATH=src`):

```bash
# Run all tests
pytest

# With conda env (e.g. etb) without installing the package
conda activate etb
PYTHONPATH=src pytest

# Run with coverage
pytest --cov=etb_project --cov-report=html

# Run specific test file
pytest tests/test_main.py

# Or using make
make test
```

### Code Quality

```bash
# Format code
black .
ruff check --fix .

# Type checking
mypy src/etb_project

# Run all checks
make lint
make format
make type-check

# Or use pre-commit (on commit) and pre-push (before push)
pre-commit run --all-files
make pre-push   # Run lint/format check without pushing
```

### Docker

```bash
# Build image
docker build -t etb_project:latest .

# Run container
docker-compose up

# Or using make
make docker-build
make docker-up
```

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
│       ├── main.py            # Entry point: load PDF, build retriever, query or interactive loop
│       ├── models.py          # LLM and embedding helpers (Ollama, OpenAI)
│       └── retrieval/
│           ├── __init__.py    # Re-exports load_pdf, process_documents, split_documents, store_documents
│           ├── loader.py     # load_pdf (PyPDFLoader)
│           └── process.py    # split_documents, store_documents, process_documents, FAISS
├── tools/                     # Utilities and side projects (not installed)
│   └── data_generation/
├── tests/
│   ├── test_config.py
│   ├── test_main.py
│   └── test_retrieval_process.py
├── docs/
│   ├── README.md
│   ├── CONTRIBUTING.md
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

## Configuration

### RAG application (settings.yaml)

The main app reads configuration from **`src/config/settings.yaml`**. It looks for this file relative to the current working directory first, then relative to the package location (so it works when run from project root or from inside `src/`). You can override the config file path with the **`ETB_CONFIG`** environment variable (absolute path to another YAML file).

| Key           | Description                          | Default   |
|---------------|--------------------------------------|-----------|
| `pdf`         | Path to the PDF to index and query   | `null`    |
| `query`       | Single query to run (optional)       | `""`      |
| `retriever_k` | Number of chunks to retrieve per query (1–100) | `10` |
| `log_level`   | Logging level: DEBUG, INFO, WARNING, ERROR | `INFO` |

Example `src/config/settings.yaml`:

```yaml
pdf: data/your-document.pdf
query: ""   # leave empty for interactive mode
retriever_k: 10
log_level: INFO
```

**Required:** Set `pdf` to a path that exists (relative to the current working directory or absolute). The app exits with an error if `pdf` is missing or the file is not found.

### Environment variables

Copy `.env.example` to `.env` for other app settings:

```bash
cp .env.example .env
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
