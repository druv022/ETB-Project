# Usage

This page explains how to run the ETB-project RAG application, what modes it supports, and what happens at runtime.

## What you run

The primary entry point is:

```bash
python -m etb_project.main
```

You can also run the same command via:

```bash
make run
```

## Runtime modes

The app supports two main modes, controlled by configuration (see [`CONFIGURATION.md`](CONFIGURATION.md)).

### 1) Single-query mode

If `query` is set in your config, the app:

- Loads the persisted vector indices from `vector_store_path`
- Runs retrieval using the configured retriever (text + image-caption indices, merged)
- Logs/prints the merged retrieval results and/or the generated answer (depending on app settings)
- Exits

This is useful for CI smoke tests, quick checks, and reproducible runs.

### 2) Interactive mode

If `query` is empty, the app enters an interactive loop:

- You type a question
- The question is passed through a LangGraph-based RAG graph:
  - `ingest_query → retrieve_rag → generate_answer`
- The LLM produces an answer grounded (where possible) in the retrieved PDF context
- Empty input line or Ctrl+C exits

## What the app loads vs what builds indices

It’s important to separate **index building** from **runtime querying**:

- **Index building** is done by the document processing workflow (CLI or programmatic APIs). It reads PDFs, extracts text/images, chunks text, optionally captions images, then builds/persists indices.
- **Runtime querying** (`etb_project.main`) typically **loads existing persisted indices** and does not rebuild them from the PDF.

If you change the underlying PDF(s), you should rebuild/update the persisted indices first. See [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md).

## Dual retrieval (text + image captions)

When both indices exist, the app retrieves from:

- A **text-chunk** index built from document text
- An **image-caption** index built from caption documents (if captioning is enabled/configured)

The results are merged and de-duplicated before answer generation.

## Common “happy path”

1) Build or update the persisted indices from your PDF(s) (CLI).
2) Configure `pdf`, `vector_store_path`, and (optionally) `query` in `settings.yaml`.
3) Run the app:

```bash
python -m etb_project.main
```

## Related docs

- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
