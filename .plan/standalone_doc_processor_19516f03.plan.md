---
name: Standalone Doc Processor
overview: Create a new standalone PDF document processor that uses PyMuPDF to extract both page text and images, writes extracted artifacts to disk, and returns LangChain `Document`s chunked with configurable LangChain text-splitting primitives.
todos:
  - id: deps-pymupdf-pillow
    content: Update `requirements.txt` to include `pymupdf` (PyMuPDF) and `Pillow` needed by the extraction/conversion layer.
    status: completed
  - id: implement-extractor
    content: Create `src/etb_project/document_processing/pymupdf_extractor.py` implementing page text extraction and image extraction (including JPX/JPEG2000 -> PNG conversion) returning data needed for LangChain Documents and writing images.
    status: completed
  - id: implement-processor
    content: Create `src/etb_project/document_processing/processor.py` that builds LangChain `Document`s (page + chunk) and writes `pages.json` and `chunks.jsonl`, with a configurable `ChunkingConfig` using `RecursiveCharacterTextSplitter` (LangChain primitive) for granular control.
    status: completed
  - id: prechunked-faiss-adapter
    content: Add a small adapter (e.g. `process_prechunked_documents`) so existing FAISS storage can reuse chunked Documents without re-running `split_documents`.
    status: completed
  - id: cli-entrypoint
    content: Add `src/etb_project/document_processor_cli.py` (or similar) to run the standalone processor from the command line, optionally building FAISS.
    status: completed
  - id: unit-tests
    content: Add unit tests covering extraction decision branches (e.g., JPX conversion path vs raw write), chunking configuration behavior, and artifact writing. Use mocks for PyMuPDF/Pillow to avoid requiring real PDFs in unit tests.
    status: completed
  - id: docs-update
    content: Update root `README.md` with the new standalone processor usage and explain output artifacts and chunking controls.
    status: completed
isProject: false
---

## Goal

Add a standalone, reusable document processing module that:

- Extracts **text + images** from a PDF using PyMuPDF (and Pillow for JPX/JPEG2000 image conversion).
- **Writes artifacts to disk** (extracted images + extracted page text and/or chunk JSONL).
- **Returns LangChain `Document` objects** so the rest of the pipeline (embeddings + FAISS) can reuse them.
- Performs **chunking inside this processor** with granular controls via LangChain text-splitting primitives.

## Current pipeline (for context)

- PDF ingestion: `[src/etb_project/retrieval/loader.py](src/etb_project/retrieval/loader.py)` uses `PyPDFLoader(..., mode="page", extract_images=True)`.
- Chunking: `[src/etb_project/retrieval/process.py](src/etb_project/retrieval/process.py)` uses `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, ...)`.
- Embedding + storage: same file builds a FAISS index.

## Proposed design

### 1) PyMuPDF extraction layer (standalone “extract image and texts”)

Create a module, e.g. `src/etb_project/document_processing/pymupdf_extractor.py`, containing functions like:

- `extract_page_texts(doc: fitz.Document) -> list[Document]`
  - For each page: `page.get_text(...)`.
  - Returns **page-level** `Document`s with metadata `{source: pdf_path, page: page_num, ...}`.
- `extract_images(doc: fitz.Document, output_dir: Path) -> dict[int, list[ImageInfo]]`
  - For each page: `page.get_images(full=True)`.
  - `doc.extract_image(xref)` yields `image_bytes` and `ext`.
  - If `ext` is in the JPX/JPEG2000 set, convert to PNG via Pillow; otherwise write raw bytes as `{ext}`.
  - Store image output paths in `ImageInfo` and attach them to the page metadata.

### 2) LangChain-facing processor (returns chunked Documents + writes artifacts)

Create `src/etb_project/document_processing/processor.py` exposing:

- `process_pdf(pdf_path: str | Path, output_dir: str | Path, chunking_config: ChunkingConfig) -> list[Document]`

Behavior:

- Use PyMuPDF extraction layer to obtain page-level `Document`s.
- Apply chunking using a configurable LangChain splitter instance:
  - Default to `RecursiveCharacterTextSplitter` (already used in the app), but expose parameters for granular control:
    - `chunk_size`
    - `chunk_overlap`
    - `separators`
    - `keep_separator`
    - `strip_whitespace`
    - `add_start_index`
    - `length_function`
- Return **chunk-level** `Document`s.
- Write to disk:
  - `output_dir/images/page{N}_image{K}.{ext}` (or PNG converted)
  - `output_dir/pages.json` (page text + metadata including image paths)
  - `output_dir/chunks.jsonl` (one JSON line per chunk; include `page_content` and `metadata`)

### 3) Reuse with existing embedding/FAISS code

Since chunking will now happen inside the standalone processor, add a small adapter so we can reuse existing FAISS storage without re-splitting:

- Add `store_documents(documents: list[Document], embeddings: Embeddings) -> FAISS` is already present.
- Introduce a new wrapper like `process_prechunked_documents(documents: list[Document]) -> FAISS` (or reuse `store_documents` directly).
- Optionally add a CLI flag `--build-faiss` to generate a FAISS index after chunking.

### 4) CLI / entry point

Add a runnable module, for example `python -m etb_project.document_processor_cli`, supporting:

- `--pdf` (required)
- `--output-dir` (default like `./document_output`)
- chunking args (`--chunk-size`, `--chunk-overlap`, `--separators` etc. or just YAML/JSON config)
- `--build-faiss` (optional)

### 5) Config strategy

Avoid bloating `AppConfig` unless you want the main app to support the standalone processor.

- For minimum scope: keep standalone processor config in its own `ChunkingConfig` dataclass / pydantic model.
- If you do want the main app to switch behavior, add a flag to `src/etb_project/config.py` (e.g. `use_standalone_processor: bool`).

## Data flow (proposed)

```mermaid
flowchart LR
  PDF[Input PDF] --> Extract[PyMuPDF Extract: text + images]
  Extract --> Pages[LangChain page Documents + image metadata]
  Pages --> Chunk[LangChain TextSplitter (configurable)]
  Chunk --> Chunks[Chunk-level Documents]
  Chunk --> Disk[Write images + pages.json + chunks.jsonl]
  Chunks --> Embed[Embed documents]
  Embed --> FAISS[Store in FAISS]
```



## Files to touch (high level)

- Add new modules under `src/etb_project/document_processing/`
- Add tests under `tests/`
- Update `requirements.txt` to include `pymupdf` and `Pillow`
- Update `README.md` with usage for the standalone processor
- (Optional) extend retrieval pipeline with a pre-chunked adapter
