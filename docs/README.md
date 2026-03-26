# Documentation index

This folder contains the detailed documentation for ETB-project. If you are new to the repo, start with the root [`README.md`](../README.md) for quickstart instructions, then use the pages below for deeper guidance.

## Guides (how to use the project)

- [`USAGE.md`](USAGE.md): how to run the RAG app (single-query vs interactive) and what it does at runtime.
- [`CONFIGURATION.md`](CONFIGURATION.md): all configuration knobs (YAML + environment variables) and common setups.
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md): how to preprocess PDFs, generate artifacts, and build/update persisted vector stores.
- [`CLI_REFERENCE.md`](CLI_REFERENCE.md): complete CLI flag reference for `python -m etb_project.document_processor_cli`.
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md): image captioning backends (OpenRouter/OpenAI/mock), config precedence, metadata flow.

## Developer documentation

- [`DEVELOPMENT.md`](DEVELOPMENT.md): development setup, tests, lint/type-check, pre-commit, and Docker.
- [`TOOLS.md`](TOOLS.md): utilities under `tools/` (not installed with the package), including data generation and standalone captioning.
- [`ARCHITECTURE.md`](ARCHITECTURE.md): system boundaries and data flows (high-level; links out to the guides above).

## Contributing

- [`CONTRIBUTING.md`](CONTRIBUTING.md): contribution guidelines and PR process.
