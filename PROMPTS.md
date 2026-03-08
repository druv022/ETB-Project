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

- **2026-02-12**: Fix CI workflows by replacing unrendered cookiecutter template syntax with valid GitHub Actions expressions, ensuring proper execution of test and release jobs.

- **2026-03-06**: Remove unnecessary checks and restriction for git cli that are failing — fixed CI/release workflows by replacing unrendered cookiecutter template syntax (`${% raw %}{{ ... }}`) with valid GitHub Actions expressions (`${{ ... }}`) so Test jobs run correctly on all matrix combinations.

---

- **2026-03-06**: Fix error @git-error-1772822737375 — Updated Bandit pre-commit hook with `pass_filenames: false` so pre-commit no longer passes individual file paths as CLI arguments, resolving the `unrecognized arguments` error.

- **2026-03-06**: Fix error @git-error-1772822811075 — Corrected YAML indentation for the Bandit hook in `.pre-commit-config.yaml` so `args`, `exclude`, and `pass_filenames` are properly nested under the `bandit` hook entry and the config parses successfully.

- **2026-03-06 14:24:03 EST**: Resolve this merge conflict @Branch — resolved the outstanding Git merge conflict in `PROMPTS.md` by preserving both prompt-history lines and re-staging the prompt log.

- **2026-03-06**: Fix such this error doesn't happen in the github cli server after pushing to origin — updated GitHub Actions CI to install the local package with `pip install -e .` before linting and tests so the `src`-layout package `etb_project` can be imported on the runner; also clarified local setup in `README.md`.

- **2026-03-06 14:53:17 EST**: fix GitHub detected a deprecated action version — upgraded `.github/workflows/ci.yml` from `actions/upload-artifact@v3` to `actions/upload-artifact@v4` to resolve the GitHub Actions deprecation failure during artifact upload setup.
- **2026-03-07**: Update any documentation if required without creating a new branch — updated README (Configuration section for settings.yaml and ETB_CONFIG, Usage for single-query vs interactive mode, Project Structure, Running Tests with conda/PYTHONPATH), ARCHITECTURE (Project Structure to match RAG modules), and this PROMPTS log.

- **2026-03-07**: Make commit checks, push checks and CLI testing in server consistent — Pre-commit: replaced mirrors-mypy (--ignore-missing-imports) with local hook running `mypy src/etb_project` so commit uses same mypy as push/CI. pyproject: added mypy override for etb_project.retrieval.process (ignore_missing_imports) to avoid faiss inline type: ignore flip. Makefile: lint = ruff + black --check + mypy; test = pytest with term-missing, html, xml. CI: pytest args aligned with Makefile. README: documented that commit, push, and CI run the same checks.
