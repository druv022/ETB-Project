"""Tests for Streamlit/orchestrator asset path helpers."""

from __future__ import annotations

import pytest

from etb_project.ui.asset_paths import (
    asset_request_headers,
    derive_asset_path_from_stored_path,
    display_name_for_source_file,
)


def test_derive_asset_path_macos_style() -> None:
    p = "/Users/dev/ETB-Project/data/document_output/images/page1_image1.png"
    assert derive_asset_path_from_stored_path(p) == "images/page1_image1.png"


def test_derive_asset_path_nested_pdf_stem() -> None:
    p = "/app/data/document_output/my_report/images/page1_image1.png"
    assert derive_asset_path_from_stored_path(p) == "my_report/images/page1_image1.png"


def test_derive_asset_path_windows_backslashes() -> None:
    p = r"C:\proj\data\document_output\images\a.png"
    assert derive_asset_path_from_stored_path(p) == "images/a.png"


def test_display_name_strips_upload_uuid_prefix() -> None:
    assert (
        display_name_for_source_file(
            "f411370fd13b44fbb0c18db63207e351_pdf_with_image.pdf"
        )
        == "pdf_with_image.pdf"
    )


def test_display_name_strips_prefix_from_full_path() -> None:
    p = "/data/uploads/f411370fd13b44fbb0c18db63207e351_My Doc.pdf"
    assert display_name_for_source_file(p) == "My Doc.pdf"


def test_display_name_unchanged_without_prefix() -> None:
    assert display_name_for_source_file("chapter1.pdf") == "chapter1.pdf"


def test_display_name_empty() -> None:
    assert display_name_for_source_file("") == ""


def test_derive_asset_path_returns_none_for_garbage() -> None:
    assert derive_asset_path_from_stored_path("") is None
    assert derive_asset_path_from_stored_path("not/a/known/path/file.png") is None


def test_derive_asset_path_fallback_after_images_segment() -> None:
    """If ``document_output`` is missing, still recover ``images/...`` suffix."""
    p = "/home/ci/build/output/images/page1.png"
    assert derive_asset_path_from_stored_path(p) == "images/page1.png"


def test_asset_request_headers_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_ASSET_BEARER_TOKEN", raising=False)
    assert asset_request_headers() == {}


def test_asset_request_headers_retriever_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER_API_KEY", "secret-token")
    h = asset_request_headers()
    assert h.get("Authorization") == "Bearer secret-token"


def test_asset_request_headers_bearer_token_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    monkeypatch.setenv("ORCHESTRATOR_ASSET_BEARER_TOKEN", "other")
    assert asset_request_headers()["Authorization"] == "Bearer other"
