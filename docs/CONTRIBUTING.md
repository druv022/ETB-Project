# Contributing to ETB-project

Thank you for your interest in contributing to ETB-project! This document provides guidelines and instructions for contributing.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/etb_project.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Set up development environment (see README.md)

## Development Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

## Making Changes

### Project layout

- The installable application lives in `src/etb_project/`.
- Utility scripts and side projects (e.g. data generation) live under `tools/` and are **not** installed with the package. Add such scripts under `tools/` (e.g. `tools/data_generation/`) and document how to run them in the README.

### Code Style

- Follow PEP 8 style guidelines
- Use type hints for all functions
- Format code with Black (line length: 88)
- Use Ruff for linting
- Run MyPy for type checking

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting, etc.)
- `refactor:` Code refactoring
- `test:` Adding or updating tests
- `chore:` Maintenance tasks

Example:
```
feat: add user authentication endpoint

- Implement JWT token generation
- Add login and logout endpoints
- Include unit tests
```

### Testing

- Write tests for all new features
- Ensure all tests pass: `pytest`
- Maintain or improve test coverage
- Include both unit and integration tests where appropriate

### Documentation

- Update README.md if needed
- Add docstrings to all public functions and classes
- Update API documentation if applicable
- Keep CHANGELOG.md updated

## Pull Request Process

1. Ensure your code follows the project's style guidelines
2. Run all tests and ensure they pass
3. Run linting and type checking: `make lint && make type-check`
4. Update documentation as needed
5. Submit a pull request with a clear description

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests added/updated and passing
- [ ] Documentation updated
- [ ] Type hints added
- [ ] Pre-commit hooks passing
- [ ] No merge conflicts

## Review Process

- All PRs require at least one approval
- Address review comments promptly
- Keep PRs focused and reasonably sized
- Respond to feedback constructively

## Reporting Issues

When reporting issues, please include:

- Description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (OS, Python version, etc.)
- Relevant logs or error messages

## Feature Requests

For feature requests, please:

- Check if the feature already exists
- Describe the use case
- Explain the expected behavior
- Consider implementation approach

## Questions?

Feel free to open an issue for questions or reach out to the maintainers.

Thank you for contributing!

