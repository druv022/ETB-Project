"""Tests for ``asset_path`` relative to retriever ``ETB_DOCUMENT_OUTPUT_DIR``."""

from __future__ import annotations

from pathlib import Path

from etb_project.document_processing import processor as proc


def test_compute_asset_path_nested_under_document_output_root(
    tmp_path: Path,
) -> None:
    """Multi-PDF indexing writes under ``<output>/<stem>/images``; paths must be
    relative to the top-level document output dir for ``/v1/assets/...``.
    """
    doc_root = tmp_path / "document_output"
    nested = doc_root / "report_a" / "images"
    nested.mkdir(parents=True)
    img = nested / "page1_image1.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")

    rel = proc._compute_asset_path(img, doc_root)
    assert rel.replace("\\", "/") == "report_a/images/page1_image1.png"


def test_compute_asset_path_single_pdf_layout(tmp_path: Path) -> None:
    doc_root = tmp_path / "document_output"
    images = doc_root / "images"
    images.mkdir(parents=True)
    img = images / "x.png"
    img.write_bytes(b"x")

    rel = proc._compute_asset_path(img, doc_root)
    assert rel.replace("\\", "/") == "images/x.png"
