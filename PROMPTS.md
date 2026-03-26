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

- **2026-03-08**: LangGraph Migration Plan — Implementing an extensible LangGraph-based RAG pipeline (ingest_query → retrieve_rag → generate_answer) with future support for query rewriting, parallel retrieval, SQL tools, reasoning, and response shaping, and updating tests/docs accordingly.
- **2026-03-08**: Fix mypy pre-commit failure by adding an explicit `-> Any` return type annotation to `build_rag_graph` in `graph_rag.py` on the `feature/langgraph-migration` branch so the mypy hook passes.

- **2026-03-18**: Plan and implement a standalone PyMuPDF-based document processor that extracts text and images, performs configurable LangChain-based chunking, writes artifacts to disk, and integrates with the existing FAISS-based RAG pipeline.
- **2026-03-18 16:25:46 CDT**: `are the extracted images information incorporated in the main pipeline ?` (Context: checking whether image metadata flows into the RAG/vector retrieval pipeline)
- **2026-03-19 08:06:03 CDT**: `Implement the plan to incorporate image captioning info in the serialized object using a VLM model, keeping the code modular.` (Context: adding ImageCaptioner abstractions, OpenRouter backend, processor integration, tests, and docs)
- **2026-03-19 10:17:38 CDT**: `model information for openrouterimage captioner should be read from the config file. The api key will be present in the .env file` (Context: adjust OpenRouterImageCaptioner to resolve model via load_config/settings.yaml and api key via OPENROUTER_API_KEY env)
- **2026-03-19 13:57:32 CDT**: `@/Users/dhrubapujary/.cursor/plans/two-faiss-indices_96027c6a.plan.md build` (Context: build dual FAISS vector stores for text chunks and image-caption documents)
- **2026-03-19 14:30:56 CDT**: `remove the redundent codes related to two faiss index` (Context: refactor/remove duplicated dual-index logic while preserving behavior)
- **2026-03-19 14:51:10 CDT**: `Update the readme with description of the content and the fix path of running the document preprocessing step to create/update the vecotr store and the basic rag using the retrival from the updated vecotr_store.` (Context: README update for corrected preprocessing/vector-store/RAG execution path and content description)
- **2026-03-19**: `Dual Retriever Main Pipeline Plan Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.` (Context: add DualRetriever meta-retriever, wire dual vector stores into main pipeline, and update tests/docs)

- **2026-03-20 09:17:29 CDT**: `Modular vector DB: build/store vs RAG load` (Context: implement the modular vector DB indexing plan via new vectorstore layer, CLI persistence, and main load-only behavior; update tests + README.)

- **2026-03-20 10:12:42 CDT**: `Add --pdf-dir to CLI and update VDB` (Context: iterate PDFs in a folder, build/update the persisted vector store indices.)

- **2026-03-20 10:21:28 CDT**: `Default FAISS+persist; append or reset VDB` (Context: enable default build/persist, append when VDB exists, add flag to delete and rebuild fresh.)
- **2026-03-20 12:21:41 CDT**: `Store every artifical created under src/ codebase in the folder data folder with respective naming convention. Make this changes throughout the src code. Test only in conda etb env` (Context: route artifact outputs (vector index + extracted docs/images) under project `data/` directory and update docs/tests accordingly.)

- **2026-03-20**: `fix it.` (Context: wrap Ollama embeddings so single-document `embed_documents` output is always 2D for LangChain FAISS; fix `ValueError: not enough values to unpack (expected 2, got 1)` at `faiss.index.add`)

- **2026-03-25**: `Implement the plan as specified` (OpenAI SDK image captioning refactor: `ChatCompletionImageCaptioner`, `OpenAIImageCaptioner`, config `openai_image_caption_model`, CLI precedence, tests; README/PROMPTS updates.)

- **2026-03-25**: `use openouter api with openapi backend for testing` (Context: default `tools/test_image_captioning.py` to `--backend openrouter`, document OpenRouter + OpenAI Python SDK; preflight `OPENROUTER_API_KEY` / `OPENAI_API_KEY`; README Tools update.)

- **2026-03-26**: `remove any extraneous information from the parent README.md file other than keeping the basic information and usage example. All additional description for each of the feature can be moved to separate markdown file in the docs folder. Be as descriptive as possible in the docs folder but remove extra information from the main README.md file.` (Context: restructure root README into a brief entry point and move detailed feature documentation into `docs/` pages.)

- **2026-03-26**: `README → docs re-organization plan Implement the plan as specified, it is attached for your reference. Do NOT edit the plan file itself.` (Context: create a docs IA under `docs/`, migrate detailed README content into dedicated pages, and slim the root README to an entry point with links.)
