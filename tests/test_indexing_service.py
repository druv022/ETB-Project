from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.document_processing import ImageCaptioner
from etb_project.document_processing.processor import ChunkingConfig
from etb_project.vectorstore.indexing_service import (
    DEFAULT_EMBEDDING_MODEL_ID,
    append_to_and_persist_index_for_pdfs,
    build_and_persist_index,
    build_and_persist_index_for_pdfs,
    build_dual_vectorstores_from_pdfs,
)


def test_build_and_persist_index_happy_path() -> None:
    pdf_path = Path("/some/doc.pdf")
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    image_captioner: ImageCaptioner | None = None

    text_vs = MagicMock()
    caption_vs = MagicMock()

    backend = MagicMock()
    backend.backend_name = "faiss"

    with patch(
        "etb_project.vectorstore.indexing_service.process_pdf_to_vectorstores",
        return_value=(text_vs, caption_vs),
    ) as mock_process:
        text_store, caption_store = build_and_persist_index(
            pdf_path=pdf_path,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            backend=backend,
        )

    mock_process.assert_called_once()
    assert text_store is text_vs
    assert caption_store is caption_vs

    backend.persist.assert_called_once()
    call_kwargs = backend.persist.call_args.kwargs

    assert call_kwargs["text_vectorstore"] is text_vs
    assert call_kwargs["caption_vectorstore"] is caption_vs
    assert call_kwargs["manifest"].backend == "faiss"
    assert call_kwargs["manifest"].pdf_path == str(pdf_path)
    assert call_kwargs["manifest"].chunk_size == 100
    assert call_kwargs["manifest"].chunk_overlap == 10
    assert call_kwargs["manifest"].embedding_model_id == DEFAULT_EMBEDDING_MODEL_ID
    assert call_kwargs["manifest"].created_at  # non-empty string


def test_build_and_persist_index_backend_name_fallback_to_faiss() -> None:
    pdf_path = Path("/some/doc.pdf")
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    text_vs = MagicMock()
    caption_vs = MagicMock()

    class BackendWithoutName:
        def __init__(self) -> None:
            self.persist = MagicMock()

    backend = BackendWithoutName()

    with patch(
        "etb_project.vectorstore.indexing_service.process_pdf_to_vectorstores",
        return_value=(text_vs, caption_vs),
    ):
        build_and_persist_index(
            pdf_path=pdf_path,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
        )

    assert backend.persist.call_args.kwargs["manifest"].backend == "faiss"


def test_build_dual_vectorstores_from_pdfs_raises_when_empty() -> None:
    """build_dual_vectorstores_from_pdfs errors when no PDFs are provided."""
    with pytest.raises(ValueError):
        build_dual_vectorstores_from_pdfs(
            pdf_paths=[],
            output_dir=Path("/some/out"),
            chunking_config=ChunkingConfig(chunk_size=100, chunk_overlap=10),
            image_captioner=None,
        )


def test_build_dual_vectorstores_from_pdfs_builds_from_aggregated_docs() -> None:
    """build_dual_vectorstores_from_pdfs aggregates docs across PDFs."""
    pdf_paths = [Path("/some/b.pdf"), Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    fake_text_vs = MagicMock()
    fake_caption_vs = MagicMock()

    fake_text_docs_a = [MagicMock()]
    fake_caption_docs_a = [MagicMock()]
    fake_text_docs_b = [MagicMock()]
    fake_caption_docs_b = [MagicMock()]

    # Sorted order should be: /some/a.pdf, /some/b.pdf
    with (
        patch(
            "etb_project.vectorstore.indexing_service.process_pdf_to_text_and_caption_docs",
            side_effect=[
                (fake_text_docs_a, fake_caption_docs_a),
                (fake_text_docs_b, fake_caption_docs_b),
            ],
        ) as mock_process,
        patch(
            "etb_project.vectorstore.indexing_service.build_two_vectorstores",
            return_value=(fake_text_vs, fake_caption_vs),
        ) as mock_build_two,
    ):
        text_vs, caption_vs = build_dual_vectorstores_from_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            chunking_config=chunking_config,
            image_captioner=None,
        )

    assert text_vs is fake_text_vs
    assert caption_vs is fake_caption_vs
    assert mock_process.call_count == 2

    # Verify per-PDF output directories use <output_dir>/<pdf_stem>.
    call_output_dirs = [
        call.kwargs["output_dir"] for call in mock_process.call_args_list
    ]
    assert call_output_dirs == [output_dir / "a", output_dir / "b"]

    aggregated_text = fake_text_docs_a + fake_text_docs_b
    aggregated_caption = fake_caption_docs_a + fake_caption_docs_b
    mock_build_two.assert_called_once_with(aggregated_text, aggregated_caption)


def test_build_and_persist_index_for_pdfs_happy_path() -> None:
    """build_and_persist_index_for_pdfs persists once using a combined manifest."""
    pdf_paths = [Path("/some/b.pdf"), Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    text_vs = MagicMock()
    caption_vs = MagicMock()

    backend = MagicMock()
    backend.backend_name = "faiss"

    with (
        patch(
            "etb_project.vectorstore.indexing_service.build_dual_vectorstores_from_pdfs",
            return_value=(text_vs, caption_vs),
        ) as mock_build,
    ):
        build_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
        )

    mock_build.assert_called_once()
    backend.persist.assert_called_once()
    persist_kwargs = backend.persist.call_args.kwargs
    assert persist_kwargs["text_vectorstore"] is text_vs
    assert persist_kwargs["caption_vectorstore"] is caption_vs

    manifest = persist_kwargs["manifest"]
    assert manifest.backend == "faiss"
    assert manifest.pdf_path == ", ".join(str(p) for p in sorted(pdf_paths))
    assert manifest.chunk_size == 100
    assert manifest.chunk_overlap == 10
    assert manifest.embedding_model_id == DEFAULT_EMBEDDING_MODEL_ID
    assert manifest.created_at  # non-empty string


def test_build_and_persist_index_for_pdfs_raises_when_empty() -> None:
    """build_and_persist_index_for_pdfs errors when no PDFs are provided."""
    backend = MagicMock()
    backend.backend_name = "faiss"

    with pytest.raises(ValueError):
        build_and_persist_index_for_pdfs(
            pdf_paths=[],
            output_dir=Path("/some/out"),
            vector_store_dir=Path("/some/vector_store"),
            chunking_config=ChunkingConfig(chunk_size=100, chunk_overlap=10),
            image_captioner=None,
            backend=backend,
        )


def test_build_and_persist_index_for_pdfs_backend_name_fallback_to_faiss() -> None:
    """build_and_persist_index_for_pdfs falls back to 'faiss' when backend has no name."""
    pdf_paths = [Path("/some/doc.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    text_vs = MagicMock()
    caption_vs = MagicMock()

    class BackendWithoutName:
        def __init__(self) -> None:
            self.persist = MagicMock()

    backend = BackendWithoutName()

    with patch(
        "etb_project.vectorstore.indexing_service.build_dual_vectorstores_from_pdfs",
        return_value=(text_vs, caption_vs),
    ):
        build_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
        )

    assert backend.persist.call_args.kwargs["manifest"].backend == "faiss"


def test_append_to_and_persist_index_for_pdfs_builds_when_not_ready() -> None:
    """append_to_and_persist_index_for_pdfs should build when VDB isn't ready."""
    pdf_paths = [Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    backend = MagicMock()
    backend.is_ready.return_value = False

    text_vs = MagicMock()
    caption_vs = MagicMock()

    embeddings = MagicMock()
    with patch(
        "etb_project.vectorstore.indexing_service.build_and_persist_index_for_pdfs",
        return_value=(text_vs, caption_vs),
    ) as mock_build:
        res_text, res_caption = append_to_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
            embeddings=embeddings,
        )

    assert res_text is text_vs
    assert res_caption is caption_vs
    mock_build.assert_called_once()


def test_append_to_and_persist_index_for_pdfs_raises_when_empty() -> None:
    """append_to_and_persist_index_for_pdfs errors when no PDFs are provided."""
    backend = MagicMock()
    backend.is_ready.return_value = False

    with pytest.raises(ValueError):
        append_to_and_persist_index_for_pdfs(
            pdf_paths=[],
            output_dir=Path("/some/out"),
            vector_store_dir=Path("/some/vector_store"),
            chunking_config=ChunkingConfig(chunk_size=100, chunk_overlap=10),
            image_captioner=None,
            backend=backend,
            embeddings=MagicMock(),
        )


def test_append_to_and_persist_index_for_pdfs_appends_when_ready() -> None:
    """When manifest is compatible, append adds docs and persists updated manifest."""
    pdf_paths = [Path("/some/b.pdf"), Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    existing_text_vs = MagicMock()
    existing_caption_vs = MagicMock()
    text_store_emb = MagicMock(spec=Embeddings)
    text_store_emb.embed_documents.side_effect = lambda texts: [
        [0.0] * 8 for _ in texts
    ]
    caption_store_emb = MagicMock(spec=Embeddings)
    caption_store_emb.embed_documents.side_effect = lambda texts: [
        [0.0] * 8 for _ in texts
    ]
    existing_text_vs.embedding_function = text_store_emb
    existing_caption_vs.embedding_function = caption_store_emb

    backend = MagicMock()
    backend.is_ready.return_value = True
    backend.load.return_value = (existing_text_vs, existing_caption_vs)

    # Compatible manifest in the persisted index.
    existing_manifest = MagicMock()
    existing_manifest.chunk_size = 100
    existing_manifest.chunk_overlap = 10
    existing_manifest.embedding_model_id = DEFAULT_EMBEDDING_MODEL_ID
    existing_manifest.backend = "faiss"
    existing_manifest.pdf_path = "/some/old.pdf"

    embeddings = MagicMock()

    fake_text_docs_a = [Document(page_content="ta", metadata={})]
    fake_caption_docs_a = [Document(page_content="ca", metadata={})]
    fake_text_docs_b = [Document(page_content="tb", metadata={})]
    fake_caption_docs_b = [Document(page_content="cb", metadata={})]

    with (
        patch(
            "etb_project.vectorstore.indexing_service.IndexManifest.load",
            return_value=existing_manifest,
        ),
        patch(
            "etb_project.vectorstore.indexing_service.process_pdf_to_text_and_caption_docs",
            side_effect=[
                (fake_text_docs_a, fake_caption_docs_a),
                (fake_text_docs_b, fake_caption_docs_b),
            ],
        ),
    ):
        # We need a real IndexManifest.create so that the manifest passed to
        # backend.persist has the right shape.
        res_text, res_caption = append_to_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
            embeddings=embeddings,
        )

    assert res_text is existing_text_vs
    assert res_caption is existing_caption_vs
    assert text_store_emb.embed_documents.call_count == 2
    assert caption_store_emb.embed_documents.call_count == 2
    assert existing_text_vs.add_embeddings.call_count == 2
    assert existing_caption_vs.add_embeddings.call_count == 2

    persist_kwargs = backend.persist.call_args.kwargs
    manifest = persist_kwargs["manifest"]
    assert manifest.pdf_path == "/some/old.pdf, /some/a.pdf, /some/b.pdf"


def test_append_to_and_persist_index_for_pdfs_combines_when_old_pdf_path_empty() -> (
    None
):
    """If existing manifest.pdf_path is empty, combined manifest should not prefix a comma."""
    pdf_paths = [Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    existing_text_vs = MagicMock()
    existing_caption_vs = MagicMock()
    text_store_emb = MagicMock(spec=Embeddings)
    text_store_emb.embed_documents.side_effect = lambda texts: [
        [0.0] * 8 for _ in texts
    ]
    caption_store_emb = MagicMock(spec=Embeddings)
    caption_store_emb.embed_documents.side_effect = lambda texts: [
        [0.0] * 8 for _ in texts
    ]
    existing_text_vs.embedding_function = text_store_emb
    existing_caption_vs.embedding_function = caption_store_emb

    backend = MagicMock()
    backend.is_ready.return_value = True
    backend.load.return_value = (existing_text_vs, existing_caption_vs)

    existing_manifest = MagicMock()
    existing_manifest.chunk_size = 100
    existing_manifest.chunk_overlap = 10
    existing_manifest.embedding_model_id = DEFAULT_EMBEDDING_MODEL_ID
    existing_manifest.backend = "faiss"
    existing_manifest.pdf_path = "   "

    with (
        patch(
            "etb_project.vectorstore.indexing_service.IndexManifest.load",
            return_value=existing_manifest,
        ),
        patch(
            "etb_project.vectorstore.indexing_service.process_pdf_to_text_and_caption_docs",
            return_value=(
                [Document(page_content="t", metadata={})],
                [Document(page_content="c", metadata={})],
            ),
        ),
    ):
        append_to_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=vector_store_dir,
            chunking_config=chunking_config,
            image_captioner=None,
            backend=backend,
            embeddings=MagicMock(),
        )

    manifest = backend.persist.call_args.kwargs["manifest"]
    assert manifest.pdf_path == "/some/a.pdf"


def test_append_to_and_persist_index_for_pdfs_raises_when_chunking_differs() -> None:
    """append_to_and_persist_index_for_pdfs should require --reset-vdb if chunking differs."""
    pdf_paths = [Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=999, chunk_overlap=10)

    backend = MagicMock()
    backend.is_ready.return_value = True
    backend.load.return_value = (MagicMock(), MagicMock())

    existing_manifest = MagicMock()
    existing_manifest.chunk_size = 100
    existing_manifest.chunk_overlap = 10
    existing_manifest.embedding_model_id = DEFAULT_EMBEDDING_MODEL_ID
    existing_manifest.backend = "faiss"
    existing_manifest.pdf_path = "/some/old.pdf"

    embeddings = MagicMock()

    with patch(
        "etb_project.vectorstore.indexing_service.IndexManifest.load",
        return_value=existing_manifest,
    ):
        with pytest.raises(ValueError):
            append_to_and_persist_index_for_pdfs(
                pdf_paths=pdf_paths,
                output_dir=output_dir,
                vector_store_dir=vector_store_dir,
                chunking_config=chunking_config,
                image_captioner=None,
                backend=backend,
                embeddings=embeddings,
            )


def test_append_to_and_persist_index_for_pdfs_raises_when_embedding_model_differs() -> (
    None
):
    """append_to_and_persist_index_for_pdfs should require the same embedding model id."""
    pdf_paths = [Path("/some/a.pdf")]
    output_dir = Path("/some/out")
    vector_store_dir = Path("/some/vector_store")
    chunking_config = ChunkingConfig(chunk_size=100, chunk_overlap=10)

    backend = MagicMock()
    backend.is_ready.return_value = True
    backend.load.return_value = (MagicMock(), MagicMock())

    existing_manifest = MagicMock()
    existing_manifest.chunk_size = 100
    existing_manifest.chunk_overlap = 10
    existing_manifest.embedding_model_id = "some-other-embedding"
    existing_manifest.backend = "faiss"
    existing_manifest.pdf_path = "/some/old.pdf"

    with patch(
        "etb_project.vectorstore.indexing_service.IndexManifest.load",
        return_value=existing_manifest,
    ):
        with pytest.raises(ValueError):
            append_to_and_persist_index_for_pdfs(
                pdf_paths=pdf_paths,
                output_dir=output_dir,
                vector_store_dir=vector_store_dir,
                chunking_config=chunking_config,
                image_captioner=None,
                backend=backend,
                embeddings=MagicMock(),
            )
