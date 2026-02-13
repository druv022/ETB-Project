# Prompts Log

This file logs all prompts given to the AI agent for this project.

## Format
- **Timestamp**: YYYY-MM-DD HH:MM:SS
- **Prompt**: The exact prompt given
- **Context**: Brief description of what was being worked on

- **2025-02-08**: `bandit: command not found` (exit code 127) in CI — fix by adding bandit to dev deps and simplifying Safety step.

- **2025-02-08**: CI `ruff check .` failures (F401 unused imports, F841 unused variable, W293 whitespace) and Ruff deprecation warning for top-level lint options — fix tests and move config to `lint` section.

- **2025-02-09**: Verify before pushing that lint and format checks are passed using GitHub prehooks — added pre-push git hook via pre-commit so Ruff, Black, and MyPy run before push (same as CI).

- **2025-02-09**: Test if all precommit push works — ran pre-push checks (ruff, black --check, mypy); formatted 4 files with black; fixed mypy to use `src/etb_project` so it works without editable install (updated .pre-commit-config.yaml, Makefile, CI, README). All pre-push checks now pass.

- **2026-02-12**: Help me resolve the error and push the changes to GitHub. What's the blocking point here — GitHub rejected push because transaction_database_5yrs_full.sql (176.14 MB) exceeds 100 MB limit. Need to use Git LFS or remove large file.

- **2026-02-12**: Can you add the .csv file to the github, since it is small — Updated .gitignore to only exclude large SQL file, added transactions_JanFeb_2020.csv (3.6 MB) to repository, and updated README documentation.

---

