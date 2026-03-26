"""High-level PDF document processor built on PyMuPDF extraction.

This module combines the low-level extraction helpers from
``pymupdf_extractor`` with LangChain text splitting primitives to produce
chunk-level ``Document`` objects and write useful artifacts to disk.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from etb_project.document_processing import (
    ExtractedImageInfo,
    ImageCaptioner,
    extract_images,
    extract_page_documents,
)

LengthFunction = Callable[[str], int]


@dataclass
class ChunkingConfig:
    """Configuration for text chunking.

    Mirrors the key arguments of ``RecursiveCharacterTextSplitter`` to allow
    granular control while keeping a simple, serialisable structure.
    """

    chunk_size: int = 1000
    chunk_overlap: int = 200
    separators: list[str] = field(default_factory=lambda: ["\n\n", "\n", " ", ""])
    keep_separator: bool = True
    strip_whitespace: bool = True
    add_start_index: bool = True
    length_function: LengthFunction = len


def _ensure_output_root(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)


def _build_text_splitter(config: ChunkingConfig) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        length_function=config.length_function,
        separators=config.separators,
        keep_separator=config.keep_separator,
        strip_whitespace=config.strip_whitespace,
        add_start_index=config.add_start_index,
    )


def _serialize_documents_to_jsonl(path: Path, documents: Iterable[Document]) -> None:
    import json

    with path.open("w", encoding="utf-8") as f:
        for doc in documents:
            record: dict[str, Any] = {
                "page_content": doc.page_content,
                "metadata": dict(doc.metadata),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _serialize_pages_to_json(
    path: Path,
    pages: list[Document],
    images_by_page: dict[int, list[ExtractedImageInfo]],
    captions_by_page: dict[int, list[str | None]] | None = None,
) -> None:
    import json

    serializable_pages: list[dict[str, Any]] = []
    for page_index, doc in enumerate(pages):
        images = images_by_page.get(page_index, [])
        captions_for_page = (captions_by_page or {}).get(page_index, [])
        serializable_images = [
            {
                "page_index": info.page_index,
                "image_index": info.image_index,
                "xref": info.xref,
                "path": str(info.path),
                "ext": info.ext,
                "caption": (
                    captions_for_page[idx] if idx < len(captions_for_page) else None
                ),
                "caption_source": (
                    "vlm"
                    if captions_for_page
                    and idx < len(captions_for_page)
                    and captions_for_page[idx]
                    else None
                ),
            }
            for idx, info in enumerate(images)
        ]
        serializable_pages.append(
            {
                "page_content": doc.page_content,
                "metadata": dict(doc.metadata),
                "images": serializable_images,
            }
        )

    path.write_text(
        json.dumps(serializable_pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def process_pdf(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None = None,
    image_captioner: ImageCaptioner | None = None,
) -> list[Document]:
    """Process a PDF into chunk-level LangChain documents and artifacts.

    This function:

    1. Extracts page-level text into ``Document`` objects.
    2. Extracts images to ``<output_dir>/images`` and associates them with pages.
    3. Applies a configurable text splitter to produce chunk-level ``Document``s.
    4. Writes:
       * ``pages.json`` (page text + image metadata)
       * ``chunks.jsonl`` (one JSON record per chunk)
    """
    text_chunks, _caption_docs = _process_pdf_to_text_and_caption_docs(
        pdf_path=pdf_path,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
    )
    return text_chunks


def process_pdf_to_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None = None,
    image_captioner: ImageCaptioner | None = None,
) -> tuple[list[Document], list[Document]]:
    """Return both text chunk documents and caption documents."""
    return _process_pdf_to_text_and_caption_docs(
        pdf_path=pdf_path,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
    )


def _process_pdf_to_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None,
    image_captioner: ImageCaptioner | None,
) -> tuple[list[Document], list[Document]]:
    pdf_path_obj = Path(pdf_path)
    output_root = Path(output_dir)
    _ensure_output_root(output_root)

    # 1) Page-level text
    page_docs = extract_page_documents(pdf_path_obj)

    # 2) Images
    images_by_page = extract_images(pdf_path_obj, output_root)

    # 2b) Optional image captioning
    captions_by_page: dict[int, list[str | None]] = {}
    caption_docs: list[Document] = []
    if image_captioner is not None:
        caption_source_label = "vlm"

        for page_index, images in images_by_page.items():
            page_captions: list[str | None] = []
            for info in images:
                caption = image_captioner.caption_image(info.path)
                page_captions.append(caption)
            if page_captions:
                captions_by_page[page_index] = page_captions

        # Create caption documents from non-empty captions.
        total_pages = len(page_docs)
        for page_index, images in images_by_page.items():
            page_captions = captions_by_page.get(page_index, [])
            for idx, info in enumerate(images):
                caption_value = page_captions[idx] if idx < len(page_captions) else None
                if not caption_value:
                    continue
                caption_docs.append(
                    Document(
                        page_content=f"Image caption: {caption_value}",
                        metadata={
                            "source": str(pdf_path_obj),
                            "page": page_index + 1,  # 1-based
                            "total_pages": total_pages,
                            "image_index": info.image_index,
                            "xref": info.xref,
                            "path": str(info.path),
                            "ext": info.ext,
                            "caption_source": caption_source_label,
                        },
                    )
                )

        # Attach aggregated captions to page-level metadata so they propagate
        # into chunk-level ``Document.metadata`` via the splitter.
        for page_index, doc in enumerate(page_docs):
            image_infos = images_by_page.get(page_index, [])
            page_captions = captions_by_page.get(page_index, [])
            if not image_infos or not page_captions:
                continue
            image_caption_records: list[dict[str, Any]] = []
            for idx, info in enumerate(image_infos):
                caption_value = page_captions[idx] if idx < len(page_captions) else None
                if caption_value:
                    image_caption_records.append(
                        {
                            "path": str(info.path),
                            "caption": caption_value,
                        }
                    )
            if image_caption_records:
                doc.metadata["image_captions"] = image_caption_records

    # 3) Chunking
    splitter = _build_text_splitter(chunking_config or ChunkingConfig())
    chunk_docs = splitter.split_documents(page_docs)

    # 4) Artifacts
    pages_json = output_root / "pages.json"
    chunks_jsonl = output_root / "chunks.jsonl"
    _serialize_pages_to_json(
        pages_json, page_docs, images_by_page, captions_by_page or None
    )
    _serialize_documents_to_jsonl(chunks_jsonl, chunk_docs)

    return list(chunk_docs), caption_docs


__all__ = ["ChunkingConfig", "process_pdf", "process_pdf_to_text_and_caption_docs"]
