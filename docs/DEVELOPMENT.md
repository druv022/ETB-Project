# Development

This page contains development setup and day-to-day workflows (tests, linting, formatting, typing, pre-commit, Docker).

For end-user CLI behavior, see [`USAGE.md`](USAGE.md). For HTTP services, see [`APP_RUN_MODES.md`](APP_RUN_MODES.md).

## Setup

From the repo root:

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install the local package so `python -m etb_project.main` and pytest imports work
pip install -e .
```

Equivalent using **optional** `uv` (if you use it; the repo may include `uv.lock`):

```bash
uv sync --all-extras   # or: uv pip install -e ".[dev]"
```

Install git hooks:

```bash
pre-commit install
```

Pre-push hooks run the same lint and format checks as CI (Ruff, Black, MyPy) so that failed checks are caught before you push.

## Running tests

From project root, with the package importable (recommended: `pip install -e .`):

```bash
# Run all tests
pytest tests/

# Run with coverage (matches Makefile / CI style)
pytest tests/ -v --cov=etb_project --cov-report=term-missing --cov-report=html

# Run a specific test file
pytest tests/test_main.py

# Or using make
make test
```

If you prefer not to use editable install:

```bash
PYTHONPATH=src pytest tests/
```

### Conda (`ETB` environment)

If you use Miniconda/Anaconda, the environment name in this project is typically **`ETB`**:

```bash
conda activate ETB
pip install -r requirements.txt
pip install -r requirements-dev.txt
pip install -e .
pytest tests/
```

One-shot without activating:

```bash
conda run -n ETB pytest tests/
```

## Code quality

Formatting + linting:

```bash
black .
ruff check --fix .
```

Type checking:

```bash
mypy src/etb_project
```

Project convenience targets:

```bash
make lint
make format
make type-check
```

Run pre-commit hooks explicitly:

```bash
pre-commit run --all-files
```

## Docker

```bash
# Build image
docker build -t etb_project:latest .

# Run stack (Compose v2)
docker compose up --build

# Makefile targets call `docker-compose` (V1 CLI); use `docker compose` if you don't have the old binary
make docker-build
make docker-up
```

## Related docs

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`TOOLS.md`](TOOLS.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
