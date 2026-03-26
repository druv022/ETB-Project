# Development

This page contains development setup and day-to-day workflows (tests, linting, formatting, typing, pre-commit, Docker).

For end-user usage, see [`USAGE.md`](USAGE.md).

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

Install git hooks:

```bash
pre-commit install
```

Pre-push hooks run the same lint and format checks as CI (Ruff, Black, MyPy) so that failed checks are caught before you push.

## Running tests

From project root, with the package importable (recommended: `pip install -e .`):

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=etb_project --cov-report=html

# Run a specific test file
pytest tests/test_main.py

# Or using make
make test
```

If you prefer not to use editable install:

```bash
PYTHONPATH=src pytest
```

### Conda environment (if you use it)

If you use Conda for this project, activate the env before installing and running tests:

```bash
conda activate etb
pip install -e ".[dev]"
pytest
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

# Run container
docker-compose up

# Or using make
make docker-build
make docker-up
```

## Related docs

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`TOOLS.md`](TOOLS.md)
