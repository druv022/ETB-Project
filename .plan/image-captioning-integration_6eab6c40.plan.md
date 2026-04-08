---
name: image-captioning-integration
overview: Integrate modular VLM-based image captioning into the PyMuPDF document processor, enriching serialized image records and document metadata without hardwiring to any specific VLM provider.
todos:
  - id: define-captioning-interface
    content: Define an ImageCaptioner interface and a simple MockImageCaptioner in a new captioning module under document_processing.
    status: completed
  - id: integrate-captioner-into-processor
    content: Extend process_pdf in processor.py to accept an optional image_captioner, call it for each ExtractedImageInfo, and propagate captions to serialization.
    status: completed
  - id: extend-serialization-with-captions
    content: Modify _serialize_pages_to_json to include optional caption (and caption_source) on each serialized image entry in pages.json.
    status: completed
  - id: enrich-metadata-with-captions
    content: Attach aggregated image caption information to page-level Document.metadata so it flows into chunk metadata.
    status: completed
  - id: add-tests-for-captions
    content: Add unit tests verifying captions appear in pages.json and Document.metadata when an ImageCaptioner is provided, and that behavior is unchanged when it is not.
    status: completed
  - id: update-docs-for-captioning
    content: Update README/docs to describe caption fields, the ImageCaptioner abstraction, and how to plug in a real VLM-backed implementation.
    status: completed
isProject: false
---

### Goal

Add a pluggable image-captioning layer that:

- Generates captions for all extracted images via a VLM **interface** (mock implementation by default).
- Stores captions in the serialized image objects in `pages.json`.
- Optionally enriches page/chunk `Document.metadata` with caption info, so the main FAISS/RAG pipeline can use it later.

### High-level design

- **Caption interface module**: Define a small, provider-agnostic interface for captioning a single image or a batch of images, plus a mock implementation.
- **Processor integration**: In the high-level processor, call the captioning interface right after `extract_images` and before `_serialize_pages_to_json`.
- **Serialization changes**: Extend the `serializable_images` objects to include `caption` (and possibly `caption_source`) while remaining backward compatible.
- **Metadata enrichment**: Attach aggregated captions to the corresponding page-level `Document.metadata`, which will then flow into chunk-level metadata via the existing splitter.
- **Configuration knobs**: Provide a way to enable/disable captioning and select an implementation in a modular way, without wiring to a specific VLM.
- **Tests and docs**: Add unit tests around the new behavior and update README/docs to mention captioning.

### Detailed steps

- **1. Introduce a captioning interface**
  - Create a new module (e.g. `[src/etb_project/document_processing/captioning.py]`) that defines:
    - A small `ImageCaptioner` protocol/class with a method like `caption_image(path: Path) -> str | None` and/or a batch method.
    - A simple `MockImageCaptioner` that returns deterministic placeholder captions (e.g. `"Caption for {path.name}"`), suitable for unit tests and for users to later swap out with a real VLM-backed implementation.
  - Rationale: keeps all VLM details encapsulated and lets you add OpenAI/Ollama/etc. later without touching the core processor logic.
- **2. Wire captioning into the processor flow**
  - In `[src/etb_project/document_processing/processor.py]`, extend `process_pdf` to accept an optional `image_captioner` argument (`ImageCaptioner | None`).
  - After `images_by_page = extract_images(...)`, if an `image_captioner` is provided:
    - Iterate over `images_by_page` and call `image_captioner.caption_image(info.path)` for each `ExtractedImageInfo`.
    - Attach the resulting caption string back to each `ExtractedImageInfo` (either by:
      - extending the dataclass in a backward-compatible way, or
      - storing captions in a parallel `Dict[int, Dict[int, str]]` map keyed by `(page_index, image_index)`).
  - Pass the caption information into `_serialize_pages_to_json` so it can include `"caption"` in each serialized image record.
- **3. Extend serialized image objects in `_serialize_pages_to_json`**
  - Update the `serializable_images` list construction in `_serialize_pages_to_json` to optionally include:
    - `"caption"`: caption text or `null`/omitted if no caption.
    - Optionally `"caption_source"`: e.g. `"mock"`, `"vlm"`, or `"manual"` for future traceability.
  - Keep the existing fields (`page_index`, `image_index`, `xref`, `path`, `ext`) unchanged so current consumers don’t break.
- **4. Enrich `Document.metadata` with caption info**
  - Decide on a compact shape for the metadata extension, for example:
    - At the page level (before splitting): `doc.metadata["image_captions"] = ["...", "..."]` or a list of small dicts with `{"path": ..., "caption": ...}`.
  - In `process_pdf`, after captioning but before splitting:
    - For each page index, aggregate its images’ captions into a list and attach to that page’s `Document.metadata`.
  - Because `RecursiveCharacterTextSplitter` preserves metadata on each chunked `Document`, chunk metadata will then carry `image_captions` too, allowing the retrieval pipeline to access or even embed captions later.
- **5. CLI-level integration hooks (but keep default behavior simple)**
  - In `[src/etb_project/document_processor_cli.py]` plan to:
    - Add an optional flag like `--caption-images` in the future to construct and pass a real `ImageCaptioner`.
    - For now, keep the CLI’s default behavior unchanged (no captioner injected) to avoid introducing fake captions unless explicitly configured in code.
  - Expose the `ImageCaptioner` interface so advanced users can import it and wire in a real VLM-backed implementation in their own scripts.
- **6. Testing strategy**
  - In `[tests/test_document_processing.py]`:
    - Add tests that construct a fake `ImageCaptioner` (or use `MockImageCaptioner`) and assert that:
      - `pages.json` includes `"caption"` for each serialized image.
      - Page-level `Document.metadata` contains the expected `image_captions` list before and after splitting.
    - Ensure tests still pass when `image_captioner=None` (captions absent, behavior unchanged).
  - Optionally, add a small test to verify that chunk `Document` objects produced by `process_pdf` retain `image_captions` in their metadata.
- **7. Documentation updates**
  - Update the **Standalone document processor (PyMuPDF)** section of `README.md` (and/or `docs/ARCHITECTURE.md`) to:
    - Describe that `pages.json` now includes optional `caption` fields for images.
    - Explain the `ImageCaptioner` abstraction and how users can plug in their own VLM-backed implementation.
    - Note that when captions are enabled, page and chunk `Document.metadata` will contain aggregated caption information, which can be leveraged in downstream RAG steps.

### Notes and future extensions

- You can later add concrete `ImageCaptioner` implementations for specific backends (OpenAI, Ollama, etc.) in separate modules that comply with the same interface, without changing the core processor.
- A future enhancement could add a small utility that, given a chunk result, walks back to `pages.json` and provides the exact image paths + captions for the corresponding page, for UI rendering or answer enrichment.
