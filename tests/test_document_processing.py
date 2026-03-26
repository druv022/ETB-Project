"""Tests for PyMuPDF-based document processing utilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from etb_project.config import AppConfig
from etb_project.document_processing.captioning import (
    MockImageCaptioner,
    OpenAIImageCaptioner,
    OpenRouterImageCaptioner,
)
from etb_project.document_processing.processor import (
    ChunkingConfig,
    process_pdf,
    process_pdf_to_text_and_caption_docs,
)
from etb_project.document_processing.pymupdf_extractor import (
    ExtractedImageInfo,
    extract_images,
    extract_page_documents,
)

if TYPE_CHECKING:
    pass


def _build_fake_page(
    text: str, images: list[tuple[int, dict[str, bytes | str]]]
) -> MagicMock:
    """Helper to build a fake PyMuPDF page."""
    page = MagicMock()
    page.get_text.return_value = text
    # get_images returns a list of tuples; first item is xref
    page.get_images.return_value = [(meta["xref"],) for meta in images]
    return page


@pytest.fixture
def sample_pdf_path(tmp_path: Path) -> Path:
    """Create a dummy PDF file path (content not used due to mocking)."""
    pdf = tmp_path / "dummy.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% Dummy\n")
    return pdf


def test_extract_page_documents_returns_one_document_per_page(
    sample_pdf_path: Path,
) -> None:
    """extract_page_documents returns a Document per page with metadata."""
    fake_doc = MagicMock()
    fake_doc.__len__.return_value = 2
    fake_doc.__getitem__.side_effect = [
        _build_fake_page("Page 1 text", []),
        _build_fake_page("Page 2 text", []),
    ]

    with patch(
        "etb_project.document_processing.pymupdf_extractor.fitz.open",
        return_value=fake_doc,
    ):
        docs = extract_page_documents(sample_pdf_path)

    assert len(docs) == 2
    assert isinstance(docs[0], Document)
    assert docs[0].page_content == "Page 1 text"
    assert docs[0].metadata["page"] == 1
    assert docs[1].page_content == "Page 2 text"
    assert docs[1].metadata["page"] == 2
    assert docs[0].metadata["total_pages"] == 2


def test_extract_images_converts_jpeg2000_to_png(
    tmp_path: Path, sample_pdf_path: Path
) -> None:
    """extract_images converts JPEG2000-family images to PNG and writes files."""
    # Build fake document with one page and one JPEG2000 image
    fake_doc = MagicMock()
    fake_doc.__len__.return_value = 1

    page = MagicMock()
    page.get_images.return_value = [(10,)]  # xref = 10
    fake_doc.__getitem__.return_value = page

    base_image = {"image": b"fake-bytes", "ext": "jp2"}

    with (
        patch(
            "etb_project.document_processing.pymupdf_extractor.fitz.open",
            return_value=fake_doc,
        ),
        patch(
            "etb_project.document_processing.pymupdf_extractor.Image.open",
        ) as mock_image_open,
    ):
        fake_image = MagicMock()
        mock_image_open.return_value = fake_image
        fake_doc.extract_image.return_value = base_image

        result = extract_images(sample_pdf_path, tmp_path)

    assert 0 in result
    images = result[0]
    assert len(images) == 1
    info = images[0]
    assert isinstance(info, ExtractedImageInfo)
    assert info.ext == "png"
    # Ensure save was called with PNG format
    fake_image.save.assert_called_once()
    args, kwargs = fake_image.save.call_args
    assert kwargs.get("format") == "PNG"


def test_extract_images_writes_non_jpeg2000_with_original_extension(
    tmp_path: Path, sample_pdf_path: Path
) -> None:
    """extract_images writes non-JPEG2000 images with their original extension."""
    fake_doc = MagicMock()
    fake_doc.__len__.return_value = 1

    page = MagicMock()
    page.get_images.return_value = [(20,)]
    fake_doc.__getitem__.return_value = page

    base_image = {"image": b"raw-bytes", "ext": "jpeg"}

    with patch(
        "etb_project.document_processing.pymupdf_extractor.fitz.open",
        return_value=fake_doc,
    ):
        fake_doc.extract_image.return_value = base_image
        result = extract_images(sample_pdf_path, tmp_path)

    images_dir = tmp_path / "images"
    assert images_dir.exists()
    file_list = list(images_dir.iterdir())
    assert len(file_list) == 1
    saved_file = file_list[0]
    assert saved_file.suffix == ".jpeg"

    info = result[0][0]
    assert info.ext == "jpeg"
    assert info.path == saved_file


def test_process_pdf_writes_artifacts_and_returns_chunks(
    tmp_path: Path, sample_pdf_path: Path
) -> None:
    """process_pdf writes pages.json and chunks.jsonl and returns chunk documents."""
    pages_dir = tmp_path

    # Mock page extraction to avoid depending on real PyMuPDF behaviour
    page_docs = [
        Document(page_content="First page content", metadata={"page": 1}),
        Document(page_content="Second page content", metadata={"page": 2}),
    ]

    images_by_page = {
        0: [
            ExtractedImageInfo(
                page_index=0,
                image_index=1,
                xref=1,
                path=pages_dir / "img1.png",
                ext="png",
            )
        ]
    }

    with (
        patch(
            "etb_project.document_processing.processor.extract_page_documents",
            return_value=page_docs,
        ),
        patch(
            "etb_project.document_processing.processor.extract_images",
            return_value=images_by_page,
        ),
    ):
        chunk_config = ChunkingConfig(chunk_size=10, chunk_overlap=0)
        chunks = process_pdf(sample_pdf_path, pages_dir, chunk_config)

    # Should return at least as many chunks as pages (likely more)
    assert len(chunks) >= len(page_docs)
    assert all(isinstance(d, Document) for d in chunks)

    # Artifacts written
    pages_json = pages_dir / "pages.json"
    chunks_jsonl = pages_dir / "chunks.jsonl"
    assert pages_json.exists()
    assert chunks_jsonl.exists()


def test_process_pdf_includes_captions_when_captioner_provided(
    tmp_path: Path, sample_pdf_path: Path
) -> None:
    """process_pdf uses an ImageCaptioner to enrich pages.json and metadata."""
    pages_dir = tmp_path

    page_docs = [
        Document(page_content="First page content", metadata={"page": 1}),
        Document(page_content="Second page content", metadata={"page": 2}),
    ]

    images_by_page = {
        0: [
            ExtractedImageInfo(
                page_index=0,
                image_index=1,
                xref=1,
                path=pages_dir / "img1.png",
                ext="png",
            )
        ]
    }

    with (
        patch(
            "etb_project.document_processing.processor.extract_page_documents",
            return_value=page_docs,
        ),
        patch(
            "etb_project.document_processing.processor.extract_images",
            return_value=images_by_page,
        ),
    ):
        captioner = MockImageCaptioner(prefix="Test caption for")
        chunk_config = ChunkingConfig(chunk_size=10, chunk_overlap=0)
        chunks = process_pdf(
            sample_pdf_path, pages_dir, chunk_config, image_captioner=captioner
        )

    # Artifacts written
    pages_json = pages_dir / "pages.json"
    assert pages_json.exists()
    data = pages_json.read_text(encoding="utf-8")
    assert "Test caption for img1.png" in data

    # Metadata on chunks should include image_captions
    assert chunks
    assert all(isinstance(d, Document) for d in chunks)
    assert any("image_captions" in d.metadata for d in chunks)


def test_process_pdf_to_text_and_caption_docs_builds_caption_docs(
    tmp_path: Path, sample_pdf_path: Path
) -> None:
    """process_pdf_to_text_and_caption_docs returns caption documents for images with captions."""

    class _SelectiveCaptioner:
        def caption_image(self, path: Path) -> str | None:  # noqa: D401
            if path.name == "img_none.png":
                return None
            return f"Test caption for {path.name}"

    pages_dir = tmp_path

    page_docs = [
        Document(page_content="First page content", metadata={"page": 1}),
        Document(page_content="Second page content", metadata={"page": 2}),
    ]

    images_by_page = {
        0: [
            ExtractedImageInfo(
                page_index=0,
                image_index=1,
                xref=111,
                path=pages_dir / "img1.png",
                ext="png",
            ),
            ExtractedImageInfo(
                page_index=0,
                image_index=2,
                xref=222,
                path=pages_dir / "img_none.png",
                ext="png",
            ),
        ]
    }

    with (
        patch(
            "etb_project.document_processing.processor.extract_page_documents",
            return_value=page_docs,
        ),
        patch(
            "etb_project.document_processing.processor.extract_images",
            return_value=images_by_page,
        ),
    ):
        chunk_config = ChunkingConfig(chunk_size=10, chunk_overlap=0)
        text_chunks, caption_docs = process_pdf_to_text_and_caption_docs(
            sample_pdf_path,
            pages_dir,
            chunk_config,
            image_captioner=_SelectiveCaptioner(),
        )

    # One image has a None caption -> only one caption doc.
    assert len(caption_docs) == 1
    cd = caption_docs[0]
    assert cd.page_content == "Image caption: Test caption for img1.png"
    assert cd.metadata["image_index"] == 1
    assert cd.metadata["xref"] == 111
    assert cd.metadata["path"] == str(pages_dir / "img1.png")
    assert cd.metadata["ext"] == "png"
    assert cd.metadata["page"] == 1  # 1-based
    assert cd.metadata["total_pages"] == 2
    assert cd.metadata["source"] == str(sample_pdf_path)

    # Text chunks should still be produced.
    assert text_chunks
    assert all(isinstance(d, Document) for d in text_chunks)


def _fake_completion(content: str) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def test_openrouter_captioner_resolves_model_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OpenRouterImageCaptioner() should use config model and env API key."""
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"fake-image-bytes")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key")

    captioner = OpenRouterImageCaptioner()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_completion(
        "A caption from OpenRouter (mock)"
    )

    with (
        patch(
            "etb_project.document_processing.captioning.load_config",
            return_value=AppConfig(openrouter_image_caption_model="test-model"),
        ),
        patch(
            "etb_project.document_processing.captioning.OpenAI",
            return_value=mock_client,
        ) as mock_openai,
    ):
        caption = captioner.caption_image(img_path)

    assert caption == "A caption from OpenRouter (mock)"
    assert mock_client.chat.completions.create.call_count == 1
    create_kw = mock_client.chat.completions.create.call_args.kwargs
    assert create_kw["model"] == "test-model"
    mock_openai.assert_called_once()
    call_kw = mock_openai.call_args.kwargs
    assert call_kw["base_url"] == "https://openrouter.ai/api/v1"
    assert call_kw["api_key"] == "test-api-key"


def test_openrouter_captioner_returns_none_when_model_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If model isn't configured, captioning should fail gracefully."""
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"fake-image-bytes")

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-api-key")

    captioner = OpenRouterImageCaptioner()

    with (
        patch(
            "etb_project.document_processing.captioning.load_config",
            return_value=AppConfig(openrouter_image_caption_model=None),
        ),
        patch(
            "etb_project.document_processing.captioning.OpenAI",
        ) as mock_openai,
    ):
        caption = captioner.caption_image(img_path)

    assert caption is None
    mock_openai.assert_not_called()


def test_openai_captioner_resolves_model_from_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OpenAIImageCaptioner() should use config model and OPENAI_API_KEY."""
    img_path = tmp_path / "img.png"
    img_path.write_bytes(b"fake-image-bytes")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    captioner = OpenAIImageCaptioner()
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = _fake_completion(
        "Caption from OpenAI"
    )

    with (
        patch(
            "etb_project.document_processing.captioning.load_config",
            return_value=AppConfig(openai_image_caption_model="gpt-4o-mini"),
        ),
        patch(
            "etb_project.document_processing.captioning.OpenAI",
            return_value=mock_client,
        ) as mock_openai,
    ):
        caption = captioner.caption_image(img_path)

    assert caption == "Caption from OpenAI"
    assert (
        mock_client.chat.completions.create.call_args.kwargs["model"] == "gpt-4o-mini"
    )
    mock_openai.assert_called_once()
    assert "base_url" not in mock_openai.call_args.kwargs
