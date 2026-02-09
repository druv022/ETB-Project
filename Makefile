.PHONY: help install install-dev test lint format type-check clean run docker-build docker-up docker-down

# Variables
PYTHON := python3
PIP := pip
VENV := .venv
PYTHON_VENV := $(VENV)/bin/python
PIP_VENV := $(VENV)/bin/pip

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install production dependencies
	@echo "Installing production dependencies..."
	$(PIP) install -r requirements.txt

install-dev: ## Install development dependencies
	@echo "Installing development dependencies..."
	$(PIP) install -r requirements-dev.txt
	@if [ "y" = "y" ]; then \
		pre-commit install; \
	fi

venv: ## Create virtual environment
	@echo "Creating virtual environment..."
	$(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created. Activate with: source $(VENV)/bin/activate"

test: ## Run tests
	@echo "Running tests..."
	pytest tests/ -v --cov=etb_project --cov-report=term-missing --cov-report=html

test-watch: ## Run tests in watch mode
	@echo "Running tests in watch mode..."
	pytest-watch tests/

lint: ## Run linters
	@echo "Running linters..."
	ruff check .
	mypy etb_project

format: ## Format code
	@echo "Formatting code..."
	black .
	ruff check --fix .

type-check: ## Run type checker
	@echo "Running type checker..."
	mypy etb_project

clean: ## Clean build artifacts
	@echo "Cleaning..."
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage dist build

run: ## Run the application
	@echo "Running application..."
	python -m etb_project.main

docker-build: ## Build Docker image
	@echo "Building Docker image..."
	docker build -t etb_project:latest .

docker-up: ## Start Docker containers
	@echo "Starting Docker containers..."
	docker-compose up -d

docker-down: ## Stop Docker containers
	@echo "Stopping Docker containers..."
	docker-compose down

docker-logs: ## View Docker logs
	docker-compose logs -f

pre-commit: ## Run pre-commit hooks on all files
	@echo "Running pre-commit hooks..."
	pre-commit run --all-files

