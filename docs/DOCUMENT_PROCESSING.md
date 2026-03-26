# Document processing and indexing

This project includes a standalone document processing workflow that extracts and serializes PDF content, then builds and persists vector indices for RAG.

If you only want to *query* an already-built index, see [`USAGE.md`](USAGE.md).

## The end-to-end workflow

At a high level, the workflow looks like:

1) **Extract** text and embedded images from PDF(s)
2) **Serialize** extracted artifacts to disk (`pages.json`, `chunks.jsonl`, and `images/`)
3) **Chunk** text using LangChain’s `RecursiveCharacterTextSplitter`
4) Optionally **caption** images using a pluggable captioner backend
5) **Index** documents into vector stores:
   - one index for text chunks
   - one index for image caption documents (if captioning enabled and captions exist)
6) Optionally **persist** the indices to disk for later querying

## Fixed run path (important)

Run the CLI from the project root after installing the package in editable mode:

```bash
pip install -e .
python -m etb_project.document_processor_cli --help
```

This ensures imports and config resolution behave consistently.

## Build/update a persisted dual vector index (CLI)

Use this when you want to preprocess a PDF and build a persisted dual index (text + image captions) for RAG.

### Single PDF

```bash
python -m etb_project.document_processor_cli \
  --pdf "data/Introduction to Agents.pdf" \
  --output-dir "./data/document_output" \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --persist-index \
  --vector-store-dir "./data/vector_index"
```

### Folder of PDFs (combined index)

```bash
python -m etb_project.document_processor_cli \
  --pdf-dir ./data/pdfs \
  --output-dir ./data/document_output \
  --chunk-size 1000 \
  --chunk-overlap 200 \
  --vector-store-dir ./data/vector_index
```

Notes:

- The `--pdf-dir` mode iterates `*.pdf` files and builds **one combined index**.
- If persistence is enabled and the vector store already exists, **new documents are appended** unless you reset the VDB (see below).

## After indexing: run the app (load-only)

Once your indices exist, you can run the RAG app:

```bash
python -m etb_project.main
```

Important behavior:

- `etb_project.main` loads persisted indices from `vector_store_path` in `src/config/settings.yaml`.
- It does **not** rebuild indices from the PDF during normal runtime.

## Artifacts written to disk

The processor writes durable artifacts that make the workflow inspectable and reproducible:

- `images/`: one image file per embedded image
  - JPEG2000-family types are converted to PNG for broader compatibility
- `pages.json`: one entry per page containing:
  - extracted text
  - page metadata
  - associated image info
  - optional captions (if captioning enabled)
- `chunks.jsonl`: one JSON record per chunk containing:
  - `page_content`
  - `metadata` (propagated through chunking)

Re-running preprocessing with the same `--output-dir` updates the exported artifacts (`pages.json`, `chunks.jsonl`, and `images/`).

## Reset vs append semantics

- **Append/update**: re-run the CLI against new PDFs or changed PDFs and append new documents to the existing persisted index.
- **Reset**: delete the existing vector index and rebuild from scratch.

See the exact flag behavior in [`CLI_REFERENCE.md`](CLI_REFERENCE.md).

## Programmatic usage (APIs)

If you want to embed this workflow into code, there are programmatic entry points that return LangChain `Document` objects and/or vector stores.

### Reuse chunked documents

```python
from pathlib import Path

from etb_project.document_processing.processor import ChunkingConfig, process_pdf
from etb_project.retrieval.process import process_prechunked_documents

pdf_path = Path("data/Introduction to Agents.pdf")
output_dir = Path("data/document_output")

chunk_config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
chunk_docs = process_pdf(pdf_path, output_dir, chunk_config)

vectorstore = process_prechunked_documents(chunk_docs)
retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
```

### Build both indices (text + captions)

```python
from pathlib import Path

from etb_project.document_processing import OpenRouterImageCaptioner
from etb_project.document_processing.processor import ChunkingConfig
from etb_project.retrieval.process import process_pdf_to_vectorstores

pdf_path = Path("data/Introduction to Agents.pdf")
output_dir = Path("data/document_output")

chunk_config = ChunkingConfig(chunk_size=1000, chunk_overlap=200)
captioner = OpenRouterImageCaptioner()

text_vectorstore, caption_vectorstore = process_pdf_to_vectorstores(
    pdf_path=pdf_path,
    output_dir=output_dir,
    chunking_config=chunk_config,
    image_captioner=captioner,
)
```

See [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md) for captioner configuration and precedence.

## Related docs

- [`USAGE.md`](USAGE.md)
- [`CLI_REFERENCE.md`](CLI_REFERENCE.md)
- [`CONFIGURATION.md`](CONFIGURATION.md)
- [`IMAGE_CAPTIONING.md`](IMAGE_CAPTIONING.md)
