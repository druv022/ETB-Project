"""Tests for the standalone document processor CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from etb_project.document_processor_cli import main as cli_main

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_cli_errors_when_pdf_missing(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """CLI exits with error when the PDF path does not exist."""
    missing_pdf = tmp_path / "missing.pdf"

    test_args = [
        "etb_project.document_processor_cli",
        "--pdf",
        str(missing_pdf),
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_runs_with_mocked_processing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """CLI persists (default) by calling append_to_and_persist_index_for_pdfs."""
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    test_args = [
        "etb_project.document_processor_cli",
        "--pdf",
        str(pdf_path),
        "--output-dir",
        str(tmp_path / "out"),
        "--chunk-size",
        "50",
        "--chunk-overlap",
        "5",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    fake_text_vectorstore = MagicMock()
    fake_caption_vectorstore = MagicMock()

    with (
        patch(
            "etb_project.document_processor_cli.load_config",
            return_value=MagicMock(
                openrouter_image_caption_model=None,
                openai_image_caption_model=None,
                vector_store_path=None,
            ),
        ),
        patch(
            "etb_project.document_processor_cli.get_embeddings",
            return_value=MagicMock(),
        ),
        patch(
            "etb_project.document_processor_cli.append_to_and_persist_index_for_pdfs",
            return_value=(fake_text_vectorstore, fake_caption_vectorstore),
        ) as mock_append,
    ):
        cli_main()

    assert mock_append.call_count == 1
    assert mock_append.call_args.kwargs["pdf_paths"] == [pdf_path]


def test_cli_resets_vdb_when_flag_set(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """CLI deletes existing VDB when --reset-vdb is provided."""
    pdf_path = tmp_path / "dummy.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    vector_store_dir = tmp_path / "vector_index"
    vector_store_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "out"

    test_args = [
        "etb_project.document_processor_cli",
        "--pdf",
        str(pdf_path),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "50",
        "--chunk-overlap",
        "5",
        "--reset-vdb",
        "--vector-store-dir",
        str(vector_store_dir),
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    fake_text_vectorstore = MagicMock()
    fake_text_vectorstore.docstore._dict = {"a": "b"}  # type: ignore[assignment]
    fake_caption_vectorstore = MagicMock()
    fake_caption_vectorstore.docstore._dict = {"c": "d"}  # type: ignore[assignment]

    fake_backend = MagicMock()
    fake_backend.is_ready.return_value = False

    with (
        patch(
            "etb_project.document_processor_cli.load_config",
            return_value=MagicMock(
                openrouter_image_caption_model=None,
                openai_image_caption_model=None,
                vector_store_path=None,
            ),
        ),
        patch(
            "etb_project.document_processor_cli.FaissDualVectorStoreBackend",
            return_value=fake_backend,
        ),
        patch(
            "etb_project.document_processor_cli.get_embeddings",
            return_value=MagicMock(),
        ),
        patch(
            "etb_project.document_processor_cli.shutil.rmtree",
        ) as mock_rmtree,
        patch(
            "etb_project.document_processor_cli.append_to_and_persist_index_for_pdfs",
            return_value=(fake_text_vectorstore, fake_caption_vectorstore),
        ) as mock_append,
    ):
        cli_main()

    mock_rmtree.assert_called_once()
    assert mock_append.call_count == 1
    assert mock_append.call_args.kwargs["pdf_paths"] == [pdf_path]
    assert mock_append.call_args.kwargs["vector_store_dir"] == vector_store_dir


def test_cli_errors_when_pdf_dir_missing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """CLI exits with error when the PDF directory path does not exist."""
    missing_dir = tmp_path / "missing_pdfs"
    test_args = [
        "etb_project.document_processor_cli",
        "--pdf-dir",
        str(missing_dir),
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_errors_when_pdf_dir_has_no_pdfs(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """CLI exits with error when the directory contains no PDFs."""
    empty_dir = tmp_path / "empty_pdfs"
    empty_dir.mkdir(parents=True, exist_ok=True)
    test_args = [
        "etb_project.document_processor_cli",
        "--pdf-dir",
        str(empty_dir),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    with pytest.raises(SystemExit):
        cli_main()


def test_cli_processes_all_pdfs_in_dir_by_default(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """CLI iterates over PDFs in a directory and appends/persists by default."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    pdf1 = pdfs_dir / "a.pdf"
    pdf1.write_bytes(b"%PDF-1.4\n")
    pdf2 = pdfs_dir / "b.pdf"
    pdf2.write_bytes(b"%PDF-1.4\n")

    out_dir = tmp_path / "out"
    test_args = [
        "etb_project.document_processor_cli",
        "--pdf-dir",
        str(pdfs_dir),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "50",
        "--chunk-overlap",
        "5",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    with (
        patch(
            "etb_project.document_processor_cli.load_config",
            return_value=MagicMock(
                openrouter_image_caption_model=None,
                openai_image_caption_model=None,
                vector_store_path=None,
            ),
        ),
        patch(
            "etb_project.document_processor_cli.get_embeddings",
            return_value=MagicMock(),
        ),
        patch(
            "etb_project.document_processor_cli.append_to_and_persist_index_for_pdfs",
            return_value=(MagicMock(), MagicMock()),
        ) as mock_append,
    ):
        cli_main()

    assert mock_append.call_count == 1
    assert mock_append.call_args.kwargs["pdf_paths"] == sorted([pdf1, pdf2])
    assert mock_append.call_args.kwargs["output_dir"] == out_dir
    assert mock_append.call_args.kwargs["chunking_config"].chunk_size == 50
    assert mock_append.call_args.kwargs["chunking_config"].chunk_overlap == 5


def test_cli_builds_faiss_for_pdf_dir(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Passing --build-faiss still results in append/persist for a folder."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    pdf1 = pdfs_dir / "a.pdf"
    pdf1.write_bytes(b"%PDF-1.4\n")
    pdf2 = pdfs_dir / "b.pdf"
    pdf2.write_bytes(b"%PDF-1.4\n")

    out_dir = tmp_path / "out"
    test_args = [
        "etb_project.document_processor_cli",
        "--pdf-dir",
        str(pdfs_dir),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "50",
        "--chunk-overlap",
        "5",
        "--build-faiss",
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    with (
        patch(
            "etb_project.document_processor_cli.load_config",
            return_value=MagicMock(
                openrouter_image_caption_model=None,
                openai_image_caption_model=None,
            ),
        ),
        patch(
            "etb_project.document_processor_cli.get_embeddings",
            return_value=MagicMock(),
        ),
        patch(
            "etb_project.document_processor_cli.append_to_and_persist_index_for_pdfs",
            return_value=(MagicMock(), MagicMock()),
        ) as mock_append,
    ):
        cli_main()

    assert mock_append.call_count == 1
    assert mock_append.call_args.kwargs["pdf_paths"] == sorted([pdf1, pdf2])
    assert mock_append.call_args.kwargs["output_dir"] == out_dir
    assert mock_append.call_args.kwargs["chunking_config"].chunk_size == 50
    assert mock_append.call_args.kwargs["chunking_config"].chunk_overlap == 5
    assert mock_append.call_args.kwargs["image_captioner"] is None


def test_cli_persists_index_for_pdf_dir_when_flag_set(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    """CLI persists by appending/persisting for a folder of PDFs."""
    pdfs_dir = tmp_path / "pdfs"
    pdfs_dir.mkdir(parents=True, exist_ok=True)

    pdf1 = pdfs_dir / "a.pdf"
    pdf1.write_bytes(b"%PDF-1.4\n")
    pdf2 = pdfs_dir / "b.pdf"
    pdf2.write_bytes(b"%PDF-1.4\n")

    vector_store_dir = tmp_path / "vector_index"
    out_dir = tmp_path / "out"
    test_args = [
        "etb_project.document_processor_cli",
        "--pdf-dir",
        str(pdfs_dir),
        "--output-dir",
        str(out_dir),
        "--chunk-size",
        "50",
        "--chunk-overlap",
        "5",
        "--persist-index",
        "--vector-store-dir",
        str(vector_store_dir),
    ]
    monkeypatch.setattr(sys, "argv", test_args)

    fake_text_vectorstore = MagicMock()
    fake_text_vectorstore.docstore._dict = {"a": "b"}  # type: ignore[attr-defined]
    fake_caption_vectorstore = MagicMock()
    fake_caption_vectorstore.docstore._dict = {"c": "d"}  # type: ignore[attr-defined]

    fake_backend = MagicMock()

    with (
        patch(
            "etb_project.document_processor_cli.load_config",
            return_value=MagicMock(
                openrouter_image_caption_model=None,
                openai_image_caption_model=None,
                vector_store_path=None,
            ),
        ),
        patch(
            "etb_project.document_processor_cli.FaissDualVectorStoreBackend",
            return_value=fake_backend,
        ),
        patch(
            "etb_project.document_processor_cli.get_embeddings",
            return_value=MagicMock(),
        ),
        patch(
            "etb_project.document_processor_cli.append_to_and_persist_index_for_pdfs",
            return_value=(fake_text_vectorstore, fake_caption_vectorstore),
        ) as mock_append,
    ):
        cli_main()

    mock_append.assert_called_once()
    assert mock_append.call_args.kwargs["pdf_paths"] == sorted([pdf1, pdf2])
    assert mock_append.call_args.kwargs["vector_store_dir"] == vector_store_dir
    assert mock_append.call_args.kwargs["chunking_config"].chunk_size == 50
    assert mock_append.call_args.kwargs["chunking_config"].chunk_overlap == 5
