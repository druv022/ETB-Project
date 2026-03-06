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

```bash
# Run the application
python -m etb_project.main

# Or using make
make run
```

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

```bash
# Run all tests
pytest

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
│   └── etb_project/           # Main package (installed with pip install .)
│       ├── __init__.py
│       └── main.py
├── tools/                     # Utilities and side projects (not installed)
│   └── data_generation/       # Data generation scripts
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── docs/
│   ├── README.md
│   ├── CONTRIBUTING.md
│   └── ARCHITECTURE.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── .cursorrules
├── .pre-commit-config.yaml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and configure your environment variables:

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
