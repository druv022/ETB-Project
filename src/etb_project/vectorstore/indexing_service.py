from __future__ import annotations

from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from etb_project.document_processing import ImageCaptioner
from etb_project.document_processing.processor import (
    ChunkingConfig,
    process_pdf_to_text_and_caption_docs,
)
from etb_project.retrieval.process import (
    append_documents_to_faiss,
    build_two_vectorstores,
    process_pdf_to_vectorstores,
)

from .base import DualVectorStoreBackend
from .manifest import IndexManifest

# Stable tag used for manifest metadata.
# If you later make the embedding model configurable, update this to match.
DEFAULT_EMBEDDING_MODEL_ID = "ollama:qwen3-embedding:0.6b"


def _path_to_manifest_str(path: Path) -> str:
    """Return a stable POSIX-like path string for manifest storage."""
    return path.as_posix()


def build_and_persist_index(
    *,
    pdf_path: Path,
    output_dir: Path,
    vector_store_dir: Path,
    chunking_config: ChunkingConfig,
    image_captioner: ImageCaptioner | None,
    backend: DualVectorStoreBackend,
) -> tuple[FAISS, FAISS]:
    """Build dual FAISS vector stores and persist them via ``backend``."""

    text_vectorstore, caption_vectorstore = process_pdf_to_vectorstores(
        pdf_path=pdf_path,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
    )

    manifest_backend = getattr(backend, "backend_name", "faiss")
    manifest = IndexManifest.create(
        backend=str(manifest_backend),
        pdf_path=_path_to_manifest_str(pdf_path),
        chunk_size=chunking_config.chunk_size,
        chunk_overlap=chunking_config.chunk_overlap,
        embedding_model_id=DEFAULT_EMBEDDING_MODEL_ID,
    )

    backend.persist(
        vector_store_dir,
        text_vectorstore=text_vectorstore,
        caption_vectorstore=caption_vectorstore,
        manifest=manifest,
    )
    return text_vectorstore, caption_vectorstore


def build_dual_vectorstores_from_pdfs(
    *,
    pdf_paths: list[Path],
    output_dir: Path,
    chunking_config: ChunkingConfig,
    image_captioner: ImageCaptioner | None,
) -> tuple[FAISS, FAISS]:
    """Build dual FAISS vectorstores for multiple PDFs (in-memory).

    This aggregates all chunk documents across PDFs and then builds a single
    text store and a single caption store.
    """
    if not pdf_paths:
        raise ValueError("pdf_paths must contain at least one PDF")

    # Ensure deterministic ordering for consistent manifest and artifacts.
    pdf_paths_sorted = sorted(pdf_paths)

    aggregated_text_docs = []
    aggregated_caption_docs = []

    for pdf_path in pdf_paths_sorted:
        per_pdf_output_dir = (
            output_dir if len(pdf_paths_sorted) == 1 else output_dir / pdf_path.stem
        )
        text_docs, caption_docs = process_pdf_to_text_and_caption_docs(
            pdf_path=pdf_path,
            output_dir=per_pdf_output_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            asset_path_root=output_dir,
        )
        aggregated_text_docs.extend(text_docs)
        aggregated_caption_docs.extend(caption_docs)

    # Build stores from the aggregated (pre-chunked) documents.
    # We call build_two_vectorstores so the caption empty-store behavior stays
    # consistent with the existing single-PDF pipeline.
    text_vectorstore, caption_vectorstore = build_two_vectorstores(
        aggregated_text_docs,
        aggregated_caption_docs,
    )

    return text_vectorstore, caption_vectorstore


def build_and_persist_index_for_pdfs(
    *,
    pdf_paths: list[Path],
    output_dir: Path,
    vector_store_dir: Path,
    chunking_config: ChunkingConfig,
    image_captioner: ImageCaptioner | None,
    backend: DualVectorStoreBackend,
) -> tuple[FAISS, FAISS]:
    """Build dual FAISS vectorstores for multiple PDFs and persist them once."""
    if not pdf_paths:
        raise ValueError("pdf_paths must contain at least one PDF")

    pdf_paths_sorted = sorted(pdf_paths)
    text_vectorstore, caption_vectorstore = build_dual_vectorstores_from_pdfs(
        pdf_paths=pdf_paths_sorted,
        output_dir=output_dir,
        chunking_config=chunking_config,
        image_captioner=image_captioner,
    )

    manifest_backend = getattr(backend, "backend_name", "faiss")
    pdf_path_field = ", ".join(_path_to_manifest_str(p) for p in pdf_paths_sorted)
    manifest = IndexManifest.create(
        backend=str(manifest_backend),
        pdf_path=pdf_path_field,
        chunk_size=chunking_config.chunk_size,
        chunk_overlap=chunking_config.chunk_overlap,
        embedding_model_id=DEFAULT_EMBEDDING_MODEL_ID,
    )

    backend.persist(
        vector_store_dir,
        text_vectorstore=text_vectorstore,
        caption_vectorstore=caption_vectorstore,
        manifest=manifest,
    )
    return text_vectorstore, caption_vectorstore


def _combine_pdf_path_field(old_pdf_path: str, new_pdf_paths: list[Path]) -> str:
    new_pdf_field = ", ".join(_path_to_manifest_str(p) for p in new_pdf_paths)
    if not old_pdf_path.strip():
        return new_pdf_field
    return f"{old_pdf_path}, {new_pdf_field}"


def append_to_and_persist_index_for_pdfs(
    *,
    pdf_paths: list[Path],
    output_dir: Path,
    vector_store_dir: Path,
    chunking_config: ChunkingConfig,
    image_captioner: ImageCaptioner | None,
    backend: DualVectorStoreBackend,
    embeddings: Embeddings,
) -> tuple[FAISS, FAISS]:
    """Append newly processed PDFs into an existing persisted VDB.

    If the persisted VDB is not ready, this function behaves like a fresh
    build-and-persist.
    """
    if not pdf_paths:
        raise ValueError("pdf_paths must contain at least one PDF")

    pdf_paths_sorted = sorted(pdf_paths)

    if not backend.is_ready(vector_store_dir):
        return build_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths_sorted,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            backend=backend,
        )

    # Load existing stores and validate chunking / embedding configuration so
    # we don't silently mix incompatible indices.
    existing_text_vectorstore, existing_caption_vectorstore = backend.load(
        vector_store_dir, embeddings=embeddings
    )
    existing_manifest = IndexManifest.load(vector_store_dir / "manifest.json")
    if existing_manifest.chunk_size != chunking_config.chunk_size or (
        existing_manifest.chunk_overlap != chunking_config.chunk_overlap
    ):
        raise ValueError(
            "Persisted index exists but chunking_config differs. "
            "Pass --reset-vdb to rebuild from scratch."
        )
    if existing_manifest.embedding_model_id != DEFAULT_EMBEDDING_MODEL_ID:
        raise ValueError(
            "Persisted index exists but embedding_model_id differs. "
            "Pass --reset-vdb to rebuild from scratch."
        )

    for pdf_path in pdf_paths_sorted:
        per_pdf_output_dir = (
            output_dir if len(pdf_paths_sorted) == 1 else output_dir / pdf_path.stem
        )
        text_docs, caption_docs = process_pdf_to_text_and_caption_docs(
            pdf_path=pdf_path,
            output_dir=per_pdf_output_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            asset_path_root=output_dir,
        )
        if text_docs:
            append_documents_to_faiss(existing_text_vectorstore, text_docs)
        if caption_docs:
            append_documents_to_faiss(existing_caption_vectorstore, caption_docs)

    updated_manifest = IndexManifest.create(
        backend=str(getattr(backend, "backend_name", existing_manifest.backend)),
        pdf_path=_combine_pdf_path_field(existing_manifest.pdf_path, pdf_paths_sorted),
        chunk_size=chunking_config.chunk_size,
        chunk_overlap=chunking_config.chunk_overlap,
        embedding_model_id=existing_manifest.embedding_model_id,
    )
    backend.persist(
        vector_store_dir,
        text_vectorstore=existing_text_vectorstore,
        caption_vectorstore=existing_caption_vectorstore,
        manifest=updated_manifest,
    )
    return existing_text_vectorstore, existing_caption_vectorstore
