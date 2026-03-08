# Architecture Documentation

## Overview

ETB-project is built with a modular, scalable architecture following Python best practices.

## Project Structure

```
etb_project/
├── src/
│   ├── config/
│   │   └── settings.yaml        # Default config file (pdf, query, retriever_k, log_level)
│   └── etb_project/
│       ├── __init__.py
│       ├── config.py            # AppConfig, load_config (reads settings.yaml or ETB_CONFIG)
│       ├── main.py              # Entry point: load PDF, build retriever, query or interactive loop
│       ├── models.py            # LLM and embedding helpers (Ollama, OpenAI)
│       └── retrieval/
│           ├── __init__.py      # Re-exports load_pdf, process_documents, split_documents, store_documents
│           ├── loader.py        # load_pdf (PyPDFLoader)
│           └── process.py       # split_documents, store_documents, process_documents (FAISS)
├── tools/                       # Utilities and side projects (not installed)
│   └── data_generation/
├── tests/                       # test_config, test_main, test_retrieval_process
├── docs/
└── .github/
```

### Tools and utilities

Code under `tools/` is **not** part of the installed package. Only `src/etb_project/` is packaged and installed. The `tools/` directory holds development and one-off utilities (e.g. data generation) that are run from the repo with `PYTHONPATH=. python -m tools.data_generation` or by executing scripts under `tools/` directly.

## Design Principles

### 1. Modularity
- Code is organized into logical modules
- Each module has a single responsibility
- Clear separation of concerns

### 2. Type Safety
- Type hints throughout the codebase
- Static type checking with MyPy
- Runtime type validation where needed

### 3. Testability
- Dependency injection for testability
- Mock-friendly design
- Comprehensive test coverage

### 4. Scalability
- Designed for horizontal scaling
- Stateless services where possible
- Efficient resource usage

## Core Components

### Main Application

The main application entry point is in `src/etb_project/main.py`. This module:

- Loads configuration from `src/config/settings.yaml` (or `ETB_CONFIG` path)
- Sets log level from config
- Loads the configured PDF, builds a FAISS vector store, and creates a retriever
- Runs a single query if `config.query` is set, otherwise enters an interactive query loop

### RAG pipeline

```mermaid
flowchart LR
  Config[Config] --> Main[main]
  Main --> LoadPDF[load_pdf]
  LoadPDF --> Process[process_documents]
  Process --> Retriever[retriever]
  Retriever --> Query[query]
```

- **Config** (`etb_project.config`): `AppConfig` holds `pdf`, `query`, `retriever_k`, `log_level`. Loaded from YAML or `ETB_CONFIG`.
- **load_pdf** (`etb_project.retrieval.loader`): Loads PDF pages (and optional image extraction) into LangChain `Document` list.
- **process_documents** (`etb_project.retrieval.process`): Splits documents with `RecursiveCharacterTextSplitter`, embeds with Ollama, stores in FAISS.
- **retriever**: FAISS vector store exposed as a retriever; `main` runs one query or an interactive CLI loop.

### Configuration Management

Configuration is managed through:

- Environment variables (`.env` file)
- Configuration classes
- Type-safe configuration loading

### Error Handling

- Custom exception classes
- Structured error responses
- Comprehensive logging
- Graceful error recovery

### Logging

- Structured logging with appropriate levels
- Configurable log formats
- Log rotation and retention policies

## Development Workflow

### Code Quality Tools

- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **Pytest**: Testing framework
- **Pre-commit**: Git hooks for quality checks

### CI/CD Pipeline

The CI/CD pipeline includes:

1. **Linting**: Code style and quality checks
2. **Testing**: Automated test execution
3. **Security**: Dependency and code scanning
4. **Build**: Package building and validation
5. **Release**: Automated releases on tags

## Dependencies

### Production Dependencies

- Core Python libraries
- Framework-specific dependencies (if applicable)

### Development Dependencies

- Testing: pytest, pytest-cov, pytest-mock
- Code Quality: black, ruff, mypy
- Security: bandit, safety
- Pre-commit hooks

## Deployment

### Docker

The project includes Docker support:

- Multi-stage builds for optimization
- Non-root user for security
- Health checks
- Environment variable configuration

### Environment Variables

Key environment variables:

- `DEBUG`: Enable debug mode
- `SECRET_KEY`: Application secret key
- `ENVIRONMENT`: Deployment environment
- `LOG_LEVEL`: Logging level

## Security Considerations

- No secrets in code or version control
- Dependency vulnerability scanning
- Security linting with Bandit
- Regular dependency updates
- Input validation and sanitization

## Performance

- Efficient algorithms and data structures
- Caching strategies where appropriate
- Database query optimization
- Resource pooling

## Future Enhancements

- [ ] Add API documentation with OpenAPI/Swagger
- [ ] Implement caching layer
- [ ] Add monitoring and observability
- [ ] Expand test coverage
- [ ] Performance optimization

## References

- [Python Packaging User Guide](https://packaging.python.org/)
- [PEP 8 Style Guide](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [Pytest Documentation](https://docs.pytest.org/)
