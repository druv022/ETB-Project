# Prompts Log

This file logs all prompts given to the AI agent for this project.

## Format
- **Timestamp**: YYYY-MM-DD HH:MM:SS
- **Prompt**: The exact prompt given
- **Context**: Brief description of what was being worked on

- **2025-02-08**: `bandit: command not found` (exit code 127) in CI — fix by adding bandit to dev deps and simplifying Safety step.

- **2025-02-08**: CI `ruff check .` failures (F401 unused imports, F841 unused variable, W293 whitespace) and Ruff deprecation warning for top-level lint options — fix tests and move config to `lint` section.

---

