---
name: README-to-docs-reorg
overview: Refactor the root README.md into a concise entry point (overview, quickstart, project structure) and move detailed guides into a structured docs/ set of markdown pages, linked from the README.
todos:
  - id: audit-readme-sections
    content: "Map current README sections to new docs pages; decide what remains in root README (per chosen scope: keep Project Structure)."
    status: completed
  - id: create-docs-pages
    content: Create docs pages (README, USAGE, DOCUMENT_PROCESSING, CLI_REFERENCE, IMAGE_CAPTIONING, CONFIGURATION, DEVELOPMENT, TOOLS) and move/expand content accordingly.
    status: completed
  - id: trim-root-readme
    content: Rewrite root README to concise basics + docs links, keeping the Project Structure tree updated.
    status: completed
  - id: reconcile-architecture-doc
    content: Update docs/ARCHITECTURE.md to avoid duplication and link to the new docs pages.
    status: completed
  - id: final-link-check
    content: Verify all intra-repo markdown links resolve and docs navigation is coherent.
    status: completed
isProject: false
---

# README → docs re-organization plan

## Goal

- Keep `README.md` **short and skimmable** (overview, requirements, install, quickstart usage, project structure tree, and links).
- Move feature- and workflow-specific detail into **dedicated pages under `docs/`**, written in full detail.

## Current state (what’s “extra” in root README)

- Deep usage flows and pipelines: preprocessing → vector-store build → RAG loop.
- Full CLI invocation(s) and flags for `document_processor_cli`.
- Programmatic examples for `process_pdf`, `process_pdf_to_vectorstores`, `process_prechunked_documents`.
- Detailed image captioning backend documentation (interfaces, OpenRouter/OpenAI presets, metadata flow).
- Tooling pages (data generation, standalone captioning script).
- Development workflows (tests, lint, type-check, pre-commit, Docker).
- Configuration details beyond “how to point at a PDF and run”.

## Target information architecture

### Root README stays concise

Update `[README.md](README.md)` to keep:

- **Project name + 1–2 sentence overview**
- **Features** (short bullets)
- **Requirements**
- **Installation** (pip + poetry, but trimmed)
- **Quickstart usage** (one primary “happy path” run)
- **Project Structure** (keep the existing tree; update `docs/` entries to match new files)
- **Docs index section** linking to detailed pages under `docs/`
- Keep existing links for **Contributing** and **License**

### New/updated docs pages (descriptive)

Create these new pages under `docs/` and move the detailed content from root README into them.

- `[docs/README.md](docs/README.md)`
  - “Docs index” landing page mirroring the README links, with short descriptions.
- `[docs/USAGE.md](docs/USAGE.md)`
  - Explain single-query vs interactive loop.
  - Explain what the app loads (persisted indices) vs what builds indices.
  - Include examples for `python -m etb_project.main` and `make run`.
- `[docs/DOCUMENT_PROCESSING.md](docs/DOCUMENT_PROCESSING.md)`
  - Move “Document preprocessing → vector store build → basic RAG retrieval”.
  - Move “Standalone document processor (PyMuPDF)” section.
  - Include detailed CLI examples and the “fixed run path” requirement.
  - Include a clear artifacts section (`pages.json`, `chunks.jsonl`, `images/`) and how reruns behave.
- `[docs/CLI_REFERENCE.md](docs/CLI_REFERENCE.md)`
  - Full flag reference for `python -m etb_project.document_processor_cli`:
    - `--pdf`, `--pdf-dir`, `--output-dir`, `--chunk-size`, `--chunk-overlap`, `--build-faiss`, `--persist-index`, `--vector-store-dir`, `--reset-vdb`.
  - Put edge cases and “append vs reset” semantics here.
- `[docs/IMAGE_CAPTIONING.md](docs/IMAGE_CAPTIONING.md)`
  - Move the “Image captioning backends” section in full.
  - Include:
    - interface/implementations list
    - config precedence (OpenRouter vs OpenAI)
    - env vars (`OPENROUTER_API_KEY`, `OPENAI_API_KEY`)
    - metadata flow into `pages.json` and LangChain `Document.metadata`
    - failure modes and logging behavior
- `[docs/CONFIGURATION.md](docs/CONFIGURATION.md)`
  - Move/expand the config section:
    - `src/config/settings.yaml` resolution order and `ETB_CONFIG`
    - keys (`pdf`, `query`, `retriever_k`, `log_level`, and captioning model keys)
    - example YAMLs for common scenarios
- `[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)`
  - Move the “Development / Setup / Running Tests / Code Quality / Docker” sections.
  - Include conda + editable install variants, and the canonical commands.
- `[docs/TOOLS.md](docs/TOOLS.md)`
  - Move “Tools (not installed)”, “Data generation”, and “Image captioning (standalone)” sections.
  - Keep `tools/` guidance centralized here.

## Reconcile with existing docs

- Review `[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)` and adjust it so it:
  - **Does not duplicate** the new `DEVELOPMENT.md` / `CONFIGURATION.md` / `DOCUMENT_PROCESSING.md` pages
  - Focuses on: component boundaries, data flow (including dual retrieval), and where each responsibility lives
  - Links out to the new pages for operational details

## Link strategy

- Add a **“Documentation”** section to root `README.md` with bullets linking to the pages above.
- Use **relative links** consistently (`docs/USAGE.md`, etc.).
- Ensure every new doc has a short “Related docs” section at the bottom to cross-link (usage ↔ config ↔ processing ↔ captioning).

## Acceptance checklist

- Root `README.md` is ≤ ~150–200 lines and skimmable.
- Every previously-detailed README section is preserved (verbatim where useful) in a `docs/*.md` page.
- No broken links; `docs/` contains an index `docs/README.md`.
