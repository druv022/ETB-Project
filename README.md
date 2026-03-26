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

- The app loads persisted FAISS indices (text chunks + image-caption chunks) from `vector_store_path` and runs each query through a merged dual retriever.
- If `query` is set in config, the app runs that single query and logs the merged retrieval results.
- If `query` is empty, the app enters an **interactive loop**: each question is passed through a LangGraph-based RAG graph (`ingest_query → retrieve_rag → generate_answer`) and the LLM's answer (grounded in the PDF where possible) is printed; empty line or Ctrl+C to exit.

### Document preprocessing -> vector store build -> basic RAG retrieval

Use this flow when you want to preprocess a PDF and build a persisted dual vector index (text + image captions) for RAG.

**Fixed run path:** run all commands from the project root (`ETB-Project/`) after installing the package with `pip install -e .`.

1) Preprocess the document and build/persist vector stores:

```bash
python -m etb_project.document_processor_cli \
  --pdf "data/Introduction to Agents.pdf" \
  --output-dir "./data/document_output" \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --persist-index \
  --vector-store-dir "./data/vector_index"
```

2) Run the app for basic RAG using the same updated PDF source:

```bash
python -m etb_project.main
```

Notes:
- `etb_project.main` loads persisted FAISS indices from `vector_store_path` in `src/config/settings.yaml` (it does not rebuild from the PDF).
- `main` uses dual retrieval by default: it queries both text and caption stores with the same input and merges/de-duplicates results before answer generation.
- Re-running preprocessing with the same `--output-dir` updates the exported artifacts (`pages.json`, `chunks.jsonl`, and `images/`).

### Standalone document processor (PyMuPDF)

In addition to the main RAG application, there is a standalone, PyMuPDF-based document processor that:

- Extracts **page text and images** from a PDF.
- Writes artifacts to disk:
  - `images/` (one image file per embedded image, converting JPEG2000-family types to PNG).
  - `pages.json` (one entry per page with text, metadata, associated image info, and optional image captions).
  - `chunks.jsonl` (one JSON record per chunk with `page_content` and `metadata`).
- Returns chunk-level LangChain `Document` objects (text chunks) that can be fed into FAISS.
  When an `ImageCaptioner` is configured, image captions are also generated and can be embedded/indexed separately.

Run it from the project root (after `pip install -e .`):

```bash
python -m etb_project.document_processor_cli \
  --pdf data/Introduction\ to\ Agents.pdf \
  --output-dir ./data/document_output \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --vector-store-dir ./data/vector_index
```

- Example: process multiple PDFs from a folder (build + persist one combined index):

```bash
python -m etb_project.document_processor_cli \
  --pdf-dir ./data/pdfs \
  --output-dir ./data/document_output \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --vector-store-dir ./data/vector_index
```

- `--pdf`: path to the input PDF (required).
- `--pdf-dir`: path to a folder of PDFs (one of `--pdf` or `--pdf-dir` is required). The CLI iterates `*.pdf` in the folder and builds a single combined vector index.
- `--output-dir`: where artifacts will be written (default: `document_output`, stored under `data/`).
- `--chunk-size` / `--chunk-overlap`: control how text is chunked using LangChain's `RecursiveCharacterTextSplitter`.
- `--build-faiss`: builds in-memory FAISS indices for both (enabled by default):
  - text chunks (from `chunks.jsonl`)
  - image captions (from caption documents generated from extracted images; may be empty if captioning is not configured)
- `--persist-index`: persists the FAISS indices to `--vector-store-dir` (or `vector_store_path` from settings.yaml). If the VDB already exists, new documents are appended (enabled by default).
- `--vector-store-dir`: where to write the persisted vector index when using `--persist-index`.
- `--reset-vdb`: delete the existing persisted vector index (VDB) and rebuild from scratch.

If you want to reuse the chunked documents programmatically:

```python
from pathlib import Path

from etb_project.document_processing.processor import ChunkingConfig, process_pdf
from etb_project.retrieval.process import process_prechunked_documents

pdf_path = Path("data/Introduction to Agents.pdf")
output_dir = Path("data/document_output")

chunk_config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
chunk_docs = process_pdf(pdf_path, output_dir, chunk_config)
vectorstore = process_prechunked_documents(chunk_docs)
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
```

If you want both indices (text + captions) programmatically:

```python
from etb_project.document_processing import OpenRouterImageCaptioner
from etb_project.document_processing.processor import ChunkingConfig
from etb_project.retrieval.process import process_pdf_to_vectorstores

chunk_config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
captioner = OpenRouterImageCaptioner()

text_vectorstore, caption_vectorstore = process_pdf_to_vectorstores(
    pdf_path=pdf_path,
    output_dir=output_dir,
    chunking_config=chunk_config,
    image_captioner=captioner,
)
```

### Image captioning backends

The document processor can optionally generate captions for extracted images via a pluggable `ImageCaptioner` interface:

- **Interfaces and implementations** (in `etb_project.document_processing.captioning`):
  - `ImageCaptioner`: abstract base interface for captioning images.
  - `MockImageCaptioner`: returns deterministic placeholder captions (useful for tests and local development).
  - `OpenRouterImageCaptioner`: uses a vision-capable model exposed via OpenRouter (for example `openai/gpt-4.1-mini`) to generate real captions.

When an `ImageCaptioner` is provided to `process_pdf`:

- Each image record in `pages.json` gains:
  - `caption`: caption text (if one was produced).
  - `caption_source`: a simple label such as `"vlm"` when the caption comes from a vision-language model.
- Page-level `Document.metadata` gains an `image_captions` key containing a list of objects with:
  - `path`: the image file path.
  - `caption`: the generated caption.
- Because the LangChain text splitter preserves metadata, chunk-level `Document` objects also carry `image_captions`, so downstream retrieval or prompting can incorporate this information.

To use the OpenRouter backend in your own script:

```python
from pathlib import Path
import os

from etb_project.document_processing.captioning import OpenRouterImageCaptioner
from etb_project.document_processing.processor import ChunkingConfig, process_pdf

pdf_path = Path("data/Introduction to Agents.pdf")
output_dir = Path("data/document_output")

captioner = OpenRouterImageCaptioner()

chunk_config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
chunk_docs = process_pdf(pdf_path, output_dir, chunk_config, image_captioner=captioner)
```

If no `ImageCaptioner` is provided, the processor behaves exactly as before (no network calls are made and no caption fields are added).

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

# Run all checks (lint = ruff + black --check + mypy; same as pre-push and CI)
make lint
make format
make type-check

# Commit and push use the same checks as CI
pre-commit run --all-files   # commit hooks (including mypy src/etb_project)
make pre-push                # push checks without pushing
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
│       ├── main.py            # Entry point: build dual vector retrieval (text+captions), run single-query mode or LangGraph interactive loop
│       ├── models.py          # LLM and embedding helpers; Ollama embeddings wrapped for FAISS (batch shape fix)
│       ├── graph_rag.py       # LangGraph RAG graph (ingest_query → retrieve_rag → generate_answer, designed for future nodes)
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
