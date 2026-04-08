"""Index build/append orchestration for persisted vector stores.

This module is the "glue" between:
- Document processing (PDF → Documents + artifacts on disk)
- Vector store construction/updating (FAISS add/persist)
- Optional sparse export (BM25 corpus) and hierarchy index maintenance
- A manifest that records the schema/version expectations of the persisted index

Why it exists:
- The retriever API and the CLI both need the same index lifecycle behaviors.
- Append mode must enforce invariants (same chunking + embedding model) to avoid
  silently mixing incompatible embeddings or chunk definitions in one index.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from etb_project.document_processing import ImageCaptioner
from etb_project.document_processing.processor import (
    ChunkingConfig,
    HierarchicalParent,
    process_pdf_to_hierarchical_text_and_caption_docs,
    process_pdf_to_text_and_caption_docs,
)
from etb_project.retrieval.process import (
    append_documents_to_faiss,
    build_two_vectorstores,
)

from .base import DualVectorStoreBackend
from .hierarchy_store import (
    HIERARCHY_BACKEND_SQLITE_V1,
    HIERARCHY_SCHEMA_VERSION,
    append_parents_and_children,
    hierarchy_sqlite_path,
    replace_all_hierarchy,
)
from .manifest import IndexManifest
from .sparse_export import SPARSE_VERSION, export_sparse_corpus_from_vectorstores

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

    text_docs, caption_docs, parent_records = (
        process_pdf_to_hierarchical_text_and_caption_docs(
            pdf_path=pdf_path,
            output_dir=output_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            asset_path_root=output_dir,
        )
    )
    text_vectorstore, caption_vectorstore = build_two_vectorstores(
        text_docs,
        caption_docs,
    )

    manifest_backend = getattr(backend, "backend_name", "faiss")
    manifest = IndexManifest.create(
        backend=str(manifest_backend),
        pdf_path=_path_to_manifest_str(pdf_path),
        chunk_size=chunking_config.chunk_size,
        chunk_overlap=chunking_config.chunk_overlap,
        embedding_model_id=DEFAULT_EMBEDDING_MODEL_ID,
        sparse_backend="bm25",
        sparse_version=SPARSE_VERSION,
        hierarchy_backend=HIERARCHY_BACKEND_SQLITE_V1,
        hierarchy_schema_version=HIERARCHY_SCHEMA_VERSION,
    )

    backend.persist(
        vector_store_dir,
        text_vectorstore=text_vectorstore,
        caption_vectorstore=caption_vectorstore,
        manifest=manifest,
    )
    replace_all_hierarchy(
        hierarchy_sqlite_path(vector_store_dir),
        parent_records,
        text_docs,
    )
    export_sparse_corpus_from_vectorstores(
        text_vectorstore,
        caption_vectorstore,
        vector_store_dir,
    )
    return text_vectorstore, caption_vectorstore


def build_dual_vectorstores_from_pdfs(
    *,
    pdf_paths: list[Path],
    output_dir: Path,
    chunking_config: ChunkingConfig,
    image_captioner: ImageCaptioner | None,
) -> tuple[FAISS, FAISS, list[HierarchicalParent], list]:
    """Build dual FAISS vectorstores for multiple PDFs (in-memory).

    Text chunks are **per-page** child chunks (see hierarchical retrieval plan).
    Returns ``(text_vs, caption_vs, parent_records, child_text_documents)``.
    """
    if not pdf_paths:
        raise ValueError("pdf_paths must contain at least one PDF")

    pdf_paths_sorted = sorted(pdf_paths)

    aggregated_text_docs = []
    aggregated_caption_docs = []
    aggregated_parents: list[HierarchicalParent] = []

    for pdf_path in pdf_paths_sorted:
        per_pdf_output_dir = (
            output_dir if len(pdf_paths_sorted) == 1 else output_dir / pdf_path.stem
        )
        text_docs, caption_docs, parents = (
            process_pdf_to_hierarchical_text_and_caption_docs(
                pdf_path=pdf_path,
                output_dir=per_pdf_output_dir,
                chunking_config=chunking_config,
                image_captioner=image_captioner,
                asset_path_root=output_dir,
            )
        )
        aggregated_text_docs.extend(text_docs)
        aggregated_caption_docs.extend(caption_docs)
        aggregated_parents.extend(parents)

    text_vectorstore, caption_vectorstore = build_two_vectorstores(
        aggregated_text_docs,
        aggregated_caption_docs,
    )

    return (
        text_vectorstore,
        caption_vectorstore,
        aggregated_parents,
        aggregated_text_docs,
    )


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
    (
        text_vectorstore,
        caption_vectorstore,
        parent_records,
        child_text_docs,
    ) = build_dual_vectorstores_from_pdfs(
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
        sparse_backend="bm25",
        sparse_version=SPARSE_VERSION,
        hierarchy_backend=HIERARCHY_BACKEND_SQLITE_V1,
        hierarchy_schema_version=HIERARCHY_SCHEMA_VERSION,
    )

    backend.persist(
        vector_store_dir,
        text_vectorstore=text_vectorstore,
        caption_vectorstore=caption_vectorstore,
        manifest=manifest,
    )
    replace_all_hierarchy(
        hierarchy_sqlite_path(vector_store_dir),
        parent_records,
        child_text_docs,
    )
    export_sparse_corpus_from_vectorstores(
        text_vectorstore,
        caption_vectorstore,
        vector_store_dir,
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

    use_hierarchy = (
        existing_manifest.hierarchy_schema_version == HIERARCHY_SCHEMA_VERSION
        and existing_manifest.hierarchy_backend == HIERARCHY_BACKEND_SQLITE_V1
    )
    if use_hierarchy:
        hier_path = hierarchy_sqlite_path(vector_store_dir)
        if not hier_path.is_file():
            raise ValueError(
                "Manifest declares hierarchical index but hierarchy.sqlite is missing. "
                "Pass --reset-vdb to rebuild from scratch."
            )

    batch_parents: list[HierarchicalParent] = []
    batch_child_docs: list = []

    for pdf_path in pdf_paths_sorted:
        per_pdf_output_dir = (
            output_dir if len(pdf_paths_sorted) == 1 else output_dir / pdf_path.stem
        )
        if use_hierarchy:
            text_docs, caption_docs, parents = (
                process_pdf_to_hierarchical_text_and_caption_docs(
                    pdf_path=pdf_path,
                    output_dir=per_pdf_output_dir,
                    chunking_config=chunking_config,
                    image_captioner=image_captioner,
                    asset_path_root=output_dir,
                )
            )
            batch_parents.extend(parents)
            batch_child_docs.extend(text_docs)
        else:
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

    if use_hierarchy and batch_parents:
        conn = sqlite3.connect(str(hierarchy_sqlite_path(vector_store_dir)))
        try:
            append_parents_and_children(conn, batch_parents, batch_child_docs)
        finally:
            conn.close()

    prev_backend = getattr(existing_manifest, "sparse_backend", None)
    sparse_backend = (
        prev_backend if isinstance(prev_backend, str) and prev_backend else "bm25"
    )
    prev_version = getattr(existing_manifest, "sparse_version", None)
    sparse_version = (
        prev_version
        if isinstance(prev_version, str) and prev_version
        else SPARSE_VERSION
    )
    updated_manifest = IndexManifest.create(
        backend=str(getattr(backend, "backend_name", existing_manifest.backend)),
        pdf_path=_combine_pdf_path_field(existing_manifest.pdf_path, pdf_paths_sorted),
        chunk_size=chunking_config.chunk_size,
        chunk_overlap=chunking_config.chunk_overlap,
        embedding_model_id=existing_manifest.embedding_model_id,
        sparse_backend=sparse_backend,
        sparse_version=sparse_version,
        hierarchy_backend=existing_manifest.hierarchy_backend,
        hierarchy_schema_version=existing_manifest.hierarchy_schema_version,
    )
    backend.persist(
        vector_store_dir,
        text_vectorstore=existing_text_vectorstore,
        caption_vectorstore=existing_caption_vectorstore,
        manifest=updated_manifest,
    )
    export_sparse_corpus_from_vectorstores(
        existing_text_vectorstore,
        existing_caption_vectorstore,
        vector_store_dir,
    )
    return existing_text_vectorstore, existing_caption_vectorstore
