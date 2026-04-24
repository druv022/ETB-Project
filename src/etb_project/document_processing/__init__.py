"""PyMuPDF-based document processing utilities.

This package provides low-level extraction helpers and higher-level processors
that produce LangChain ``Document`` objects from PDF files, including both text
and image metadata.
"""

from .captioning import (
    ChatCompletionImageCaptioner,
    ImageCaptioner,
    MockImageCaptioner,
    OpenAIImageCaptioner,
    OpenRouterImageCaptioner,
)
from .pymupdf_extractor import (
    ExtractedImageInfo,
    extract_images,
    extract_page_documents,
)
from .table_extractor import (
    extract_page_documents_with_tables,
    extract_page_text_with_tables,
    extract_tables_from_page,
)

__all__ = [
    "ChatCompletionImageCaptioner",
    "ExtractedImageInfo",
    "ImageCaptioner",
    "MockImageCaptioner",
    "OpenAIImageCaptioner",
    "OpenRouterImageCaptioner",
    "extract_images",
    "extract_page_documents",
    "extract_page_documents_with_tables",
    "extract_page_text_with_tables",
    "extract_tables_from_page",
]
