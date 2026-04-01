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


@dataclass(frozen=True)
class HierarchicalParent:
    """One PDF page row for ``hierarchy.sqlite`` (parent table)."""

    parent_id: str
    source: str
    page_start: int
    page_end: int
    full_text: str
    metadata: dict[str, Any]


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


def _compute_asset_path(image_path: Path, asset_root: Path) -> str:
    """Path relative to ``asset_root`` for HTTP ``GET /v1/assets/{asset_path}``."""
    try:
        return str(image_path.resolve().relative_to(asset_root.resolve()))
    except ValueError:
        return str(image_path)


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
    *,
    asset_path_root: Path | None = None,
) -> None:
    import json

    root = (asset_path_root if asset_path_root is not None else path.parent).resolve()
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
                "asset_path": _compute_asset_path(info.path, root),
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
    *,
    asset_path_root: Path | None = None,
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
        asset_path_root=asset_path_root,
    )
    return text_chunks


def process_pdf_to_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None = None,
    image_captioner: ImageCaptioner | None = None,
    *,
    asset_path_root: Path | None = None,
) -> tuple[list[Document], list[Document]]:
    """Return both text chunk documents and caption documents."""
    return _process_pdf_to_text_and_caption_docs(
        pdf_path=pdf_path,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
        asset_path_root=asset_path_root,
    )


def process_pdf_to_hierarchical_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None = None,
    image_captioner: ImageCaptioner | None = None,
    *,
    asset_path_root: Path | None = None,
) -> tuple[list[Document], list[Document], list[HierarchicalParent]]:
    """Like :func:`process_pdf_to_text_and_caption_docs` but chunk **per page** with ``child_id`` / ``parent_id``."""
    return _process_pdf_to_hierarchical_text_and_caption_docs(
        pdf_path=pdf_path,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
        asset_path_root=asset_path_root,
    )


def _process_pdf_to_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None,
    image_captioner: ImageCaptioner | None,
    *,
    asset_path_root: Path | None = None,
) -> tuple[list[Document], list[Document]]:
    pdf_path_obj = Path(pdf_path)
    output_root = Path(output_dir)
    _ensure_output_root(output_root)
    asset_root = (
        Path(asset_path_root).resolve()
        if asset_path_root is not None
        else output_root.resolve()
    )

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
                asset_path = _compute_asset_path(info.path, asset_root)
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
                            "asset_path": asset_path,
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
                    asset_path = _compute_asset_path(info.path, asset_root)
                    image_caption_records.append(
                        {
                            "path": str(info.path),
                            "asset_path": asset_path,
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
        pages_json,
        page_docs,
        images_by_page,
        captions_by_page or None,
        asset_path_root=asset_root,
    )
    _serialize_documents_to_jsonl(chunks_jsonl, chunk_docs)

    return list(chunk_docs), caption_docs


def _process_pdf_to_hierarchical_text_and_caption_docs(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None,
    image_captioner: ImageCaptioner | None,
    *,
    asset_path_root: Path | None = None,
) -> tuple[list[Document], list[Document], list[HierarchicalParent]]:
    pdf_path_obj = Path(pdf_path)
    output_root = Path(output_dir)
    _ensure_output_root(output_root)
    asset_root = (
        Path(asset_path_root).resolve()
        if asset_path_root is not None
        else output_root.resolve()
    )
    normalized_source = pdf_path_obj.resolve().as_posix()

    page_docs = extract_page_documents(pdf_path_obj)
    images_by_page = extract_images(pdf_path_obj, output_root)

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

        total_pages = len(page_docs)
        for page_index, images in images_by_page.items():
            page_captions = captions_by_page.get(page_index, [])
            for idx, info in enumerate(images):
                caption_value = page_captions[idx] if idx < len(page_captions) else None
                if not caption_value:
                    continue
                asset_path = _compute_asset_path(info.path, asset_root)
                caption_docs.append(
                    Document(
                        page_content=f"Image caption: {caption_value}",
                        metadata={
                            "source": str(pdf_path_obj),
                            "page": page_index + 1,
                            "total_pages": total_pages,
                            "image_index": info.image_index,
                            "xref": info.xref,
                            "path": str(info.path),
                            "asset_path": asset_path,
                            "ext": info.ext,
                            "caption_source": caption_source_label,
                        },
                    )
                )

        for page_index, doc in enumerate(page_docs):
            image_infos = images_by_page.get(page_index, [])
            page_captions = captions_by_page.get(page_index, [])
            if not image_infos or not page_captions:
                continue
            image_caption_records: list[dict[str, Any]] = []
            for idx, info in enumerate(image_infos):
                caption_value = page_captions[idx] if idx < len(page_captions) else None
                if caption_value:
                    asset_path = _compute_asset_path(info.path, asset_root)
                    image_caption_records.append(
                        {
                            "path": str(info.path),
                            "asset_path": asset_path,
                            "caption": caption_value,
                        }
                    )
            if image_caption_records:
                doc.metadata["image_captions"] = image_caption_records

    splitter = _build_text_splitter(chunking_config or ChunkingConfig())
    child_docs: list[Document] = []
    parent_records: list[HierarchicalParent] = []

    for page_index, page_doc in enumerate(page_docs):
        page_num = page_index + 1
        parent_id = f"{normalized_source}::page::{page_num}"
        full_text = page_doc.page_content or ""
        parent_records.append(
            HierarchicalParent(
                parent_id=parent_id,
                source=normalized_source,
                page_start=page_num,
                page_end=page_num,
                full_text=full_text,
                metadata=dict(page_doc.metadata or {}),
            )
        )
        page_chunks = splitter.split_documents([page_doc])
        for ci, ch in enumerate(page_chunks):
            child_id = f"{normalized_source}::p{page_num}::c{ci}"
            meta = dict(ch.metadata or {})
            meta["parent_id"] = parent_id
            meta["child_id"] = child_id
            meta["chunk_index"] = ci
            child_docs.append(Document(page_content=ch.page_content, metadata=meta))

    pages_json = output_root / "pages.json"
    chunks_jsonl = output_root / "chunks.jsonl"
    _serialize_pages_to_json(
        pages_json,
        page_docs,
        images_by_page,
        captions_by_page or None,
        asset_path_root=asset_root,
    )
    _serialize_documents_to_jsonl(chunks_jsonl, child_docs)

    return child_docs, caption_docs, parent_records


__all__ = [
    "ChunkingConfig",
    "HierarchicalParent",
    "process_pdf",
    "process_pdf_to_hierarchical_text_and_caption_docs",
    "process_pdf_to_text_and_caption_docs",
]
