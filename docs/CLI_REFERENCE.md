# CLI reference

This page is a complete reference for the document processor CLI:

```bash
python -m etb_project.document_processor_cli
```

If you want the “how-to” guide and examples first, see [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md).

## Canonical invocation

Run from the project root after installing the package:

```bash
pip install -e .
python -m etb_project.document_processor_cli --help
```

## Inputs

- `--pdf <path>`
  - Path to a single input PDF.
  - Mutually exclusive with `--pdf-dir`.

- `--pdf-dir <dir>`
  - Path to a folder containing PDFs.
  - The CLI iterates `*.pdf` and builds a **single combined index**.
  - Mutually exclusive with `--pdf`.

## Output artifacts

- `--output-dir <dir>`
  - Where extraction artifacts are written (e.g., `pages.json`, `chunks.jsonl`, and `images/`).
  - Re-running with the same output dir updates these artifacts.

## Chunking

- `--chunk-size <int>`
  - Chunk size passed to LangChain’s `RecursiveCharacterTextSplitter`.

- `--chunk-overlap <int>`
  - Chunk overlap passed to LangChain’s `RecursiveCharacterTextSplitter`.

## Vector index build + persistence

- `--build-faiss`
  - Builds FAISS indices in memory for:
    - text chunks (from `chunks.jsonl`)
    - image captions (from caption documents; may be empty if captioning not configured)
  - In this project’s workflow, FAISS build is generally enabled by default.

- `--persist-index`
  - Persists the FAISS indices to disk so the main app can load them later.
  - If the destination already exists, new documents are **appended** by default.

- `--vector-store-dir <dir>`
  - Target directory to write the persisted index when using persistence.
  - If not provided, the CLI may fall back to `vector_store_path` from `settings.yaml` (depending on implementation).

- `--reset-vdb`
  - Deletes the existing persisted index directory (VDB) and rebuilds from scratch.
  - Use this if:
    - you changed chunking parameters and want a clean rebuild
    - you want to remove previously-indexed documents
    - you suspect the existing index is stale/corrupted

## Common scenarios

### Build + persist for a single PDF

```bash
python -m etb_project.document_processor_cli \
  --pdf "data/Introduction to Agents.pdf" \
  --output-dir "./data/document_output" \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --persist-index \
  --vector-store-dir "./data/vector_index"
```

### Append new PDFs to an existing persisted index

```bash
python -m etb_project.document_processor_cli \
  --pdf-dir ./data/pdfs \
  --output-dir ./data/document_output \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --persist-index \
  --vector-store-dir "./data/vector_index"
```

### Reset and rebuild the persisted index

```bash
python -m etb_project.document_processor_cli \
  --pdf-dir ./data/pdfs \
  --output-dir ./data/document_output \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --persist-index \
  --vector-store-dir "./data/vector_index" \
  --reset-vdb
```

## Related docs

- [`DOCUMENT_PROCESSING.md`](DOCUMENT_PROCESSING.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
