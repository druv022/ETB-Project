"""PyMuPDF-based low-level PDF extraction utilities.

This module is intentionally independent of the main RAG pipeline so it can be
reused in standalone scripts or other applications. It extracts:

* Page-level text into LangChain ``Document`` objects.
* Images from each page to disk, normalising JPEG2000-family formats to PNG.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz
from langchain_core.documents import Document
from PIL import Image

JPEG2000_EXTENSIONS = {"jpx", "jp2", "j2k", "jpf", "jpg2", "j2c", "jpc"}


@dataclass(frozen=True)
class ExtractedImageInfo:
    """Metadata about an image extracted from a PDF page."""

    page_index: int
    image_index: int
    xref: int
    path: Path
    ext: str


def _ensure_output_dir(path: Path) -> None:
    """Create the output directory if it does not already exist."""
    path.mkdir(parents=True, exist_ok=True)


def extract_images(
    pdf_path: str | Path, output_dir: str | Path
) -> dict[int, list[ExtractedImageInfo]]:
    """Extract images from a PDF to ``output_dir``.

    Images using JPEG2000-family encodings are converted to PNG using Pillow;
    other image types are written to disk with their original extensions.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF file.
    output_dir:
        Directory where extracted images will be written. A subdirectory
        ``images`` will be created inside this folder.

    Returns
    -------
    dict[int, list[ExtractedImageInfo]]
        Mapping of 0-based page index to a list of extracted images for that
        page.
    """
    pdf_path_obj = Path(pdf_path)
    images_root = Path(output_dir) / "images"
    _ensure_output_dir(images_root)

    page_to_images: dict[int, list[ExtractedImageInfo]] = {}

    doc = fitz.open(pdf_path_obj)
    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            image_list = page.get_images(full=True)
            page_images: list[ExtractedImageInfo] = []

            for image_index, img in enumerate(image_list, start=1):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes: bytes = base_image["image"]
                ext: str = base_image.get("ext", "png")
                ext_lc = ext.lower()

                if ext_lc in JPEG2000_EXTENSIONS:
                    filename = (
                        images_root / f"page{page_index + 1}_image{image_index}.png"
                    )
                    image = Image.open(io.BytesIO(image_bytes))
                    try:
                        image.save(filename, format="PNG")
                    finally:
                        image.close()
                    final_ext = "png"
                else:
                    filename = (
                        images_root
                        / f"page{page_index + 1}_image{image_index}.{ext_lc}"
                    )
                    filename.write_bytes(image_bytes)
                    final_ext = ext_lc

                info = ExtractedImageInfo(
                    page_index=page_index,
                    image_index=image_index,
                    xref=xref,
                    path=filename,
                    ext=final_ext,
                )
                page_images.append(info)

            if page_images:
                page_to_images[page_index] = page_images
    finally:
        close = getattr(doc, "close", None)
        if callable(close):
            close()

    return page_to_images


def extract_page_documents(pdf_path: str | Path) -> list[Document]:
    """Extract page-level text into LangChain ``Document`` objects.

    Each page becomes a single ``Document`` with ``page_content`` set to the
    extracted text and metadata including:

    * ``source``: original PDF path
    * ``page``: 1-based page number
    * ``total_pages``: total number of pages in the document
    """
    pdf_path_obj = Path(pdf_path)

    documents: list[Document] = []
    doc = fitz.open(pdf_path_obj)
    try:
        total_pages = len(doc)
        for page_index in range(total_pages):
            page = doc[page_index]
            text = page.get_text() or ""
            metadata = {
                "source": str(pdf_path_obj),
                "page": page_index + 1,
                "total_pages": total_pages,
            }
            documents.append(Document(page_content=text, metadata=metadata))
    finally:
        close = getattr(doc, "close", None)
        if callable(close):
            close()

    return documents
