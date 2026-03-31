"""Command-line entry point for the standalone document processor.

Usage (from project root, after ``pip install -e .``):

.. code-block:: bash

    python -m etb_project.document_processor_cli \\
        --pdf data/Introduction\\ to\\ Agents.pdf \\
        # OR: process all PDFs in a folder
        # --pdf-dir data/pdfs \\
        --output-dir ./data/document_output \\
        --chunk-size 1000 \\
        --chunk-overlap 200 \\
        --build-faiss
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

from etb_project.config import load_config, resolve_artifact_path
from etb_project.document_processing import (
    ImageCaptioner,
    OpenAIImageCaptioner,
    OpenRouterImageCaptioner,
)
from etb_project.document_processing.processor import ChunkingConfig
from etb_project.models import get_ollama_embedding_model as get_embeddings
from etb_project.vectorstore.faiss_backend import FaissDualVectorStoreBackend
from etb_project.vectorstore.indexing_service import (
    append_to_and_persist_index_for_pdfs,
)

logger = logging.getLogger(__name__)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Standalone PyMuPDF-based document processor that extracts text and "
            "images, writes artifacts to disk, and optionally builds/persists FAISS indices."
        )
    )
    pdf_group = parser.add_mutually_exclusive_group(required=True)
    pdf_group.add_argument(
        "--pdf",
        required=False,
        type=str,
        help="Path to the input PDF file.",
    )
    pdf_group.add_argument(
        "--pdf-dir",
        required=False,
        dest="pdf_dir",
        type=str,
        help="Path to a folder containing PDFs to process (iterates *.pdf in the folder).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="document_output",
        help=(
            "Directory where extracted artifacts will be written. "
            "Relative paths are stored under the project top-level `data/` "
            "(default: document_output -> data/document_output)."
        ),
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for text splitting (default: 1000).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap for text splitting (default: 200).",
    )
    parser.add_argument(
        "--build-faiss",
        action="store_true",
        default=True,
        help=(
            "Build FAISS vector stores from the extracted chunked documents "
            "(enabled by default)."
        ),
    )
    parser.add_argument(
        "--persist-index",
        action="store_true",
        default=True,
        help=(
            "Persist the dual FAISS indices (text + captions) to disk. "
            "If an existing index is found, new documents are appended "
            "(enabled by default)."
        ),
    )
    parser.add_argument(
        "--reset-vdb",
        action="store_true",
        help=(
            "Delete the existing persisted vector index (VDB) and rebuild "
            "from scratch before processing the new PDFs."
        ),
    )
    parser.add_argument(
        "--vector-store-dir",
        type=str,
        default=None,
        help=(
            "Directory where the persisted vector index will be written "
            "(default: value from settings.yaml `vector_store_path`)."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    return parser


def main() -> None:
    """Run the standalone document processor CLI."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    output_dir = resolve_artifact_path(args.output_dir)
    if output_dir is None:
        parser.error("--output-dir resolved to None (unexpected)")
    if args.pdf:
        pdf_paths = [Path(args.pdf)]
        pdf_path = pdf_paths[0]
        if not pdf_path.exists():
            parser.error(f"PDF file does not exist: {pdf_path}")
        logger.info("Processing PDF: %s", pdf_path)
    else:
        pdf_dir = Path(args.pdf_dir)
        if not pdf_dir.exists():
            parser.error(f"PDF directory does not exist: {pdf_dir}")

        pdf_paths = sorted(
            [p for p in pdf_dir.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
        )
        if not pdf_paths:
            parser.error(f"No PDFs found in directory: {pdf_dir}")

        logger.info("Processing %d PDFs in: %s", len(pdf_paths), pdf_dir)
    logger.info("Writing artifacts to: %s", output_dir)

    chunk_config = ChunkingConfig(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    cfg = load_config()
    image_captioner: ImageCaptioner | None
    if cfg.openrouter_image_caption_model:
        image_captioner = OpenRouterImageCaptioner()
    elif cfg.openai_image_caption_model:
        image_captioner = OpenAIImageCaptioner()
    else:
        image_captioner = None

    backend = FaissDualVectorStoreBackend()
    resolved_store_dir = (
        resolve_artifact_path(args.vector_store_dir)
        if args.vector_store_dir
        else resolve_artifact_path(
            cfg.vector_store_path or (output_dir / "vector_index")
        )
    )
    if resolved_store_dir is None:
        parser.error(
            "--vector-store-dir and config vector_store_path are both unset (unexpected)"
        )

    logger.info(
        "Building/persisting FAISS indices (text + captions) to: %s",
        resolved_store_dir,
    )

    if args.reset_vdb and resolved_store_dir.exists():
        logger.info("Resetting VDB by deleting: %s", resolved_store_dir)
        shutil.rmtree(resolved_store_dir)

    is_append_mode = backend.is_ready(resolved_store_dir)
    embeddings = get_embeddings()

    text_vectorstore, caption_vectorstore = append_to_and_persist_index_for_pdfs(
        pdf_paths=pdf_paths,
        output_dir=output_dir,
        vector_store_dir=resolved_store_dir,
        chunking_config=chunk_config,
        image_captioner=image_captioner,
        backend=backend,
        embeddings=embeddings,
    )
    if is_append_mode and not args.reset_vdb:
        logger.info("Appended documents to existing vector index")
    else:
        logger.info("Built a new vector index (or reset before build)")
    logger.info("Vector index persisted successfully")

    logger.info(
        "Text FAISS store built with %d documents",
        len(getattr(text_vectorstore.docstore, "_dict", {})),  # noqa: SLF001
    )
    logger.info(
        "Caption FAISS store built with %d documents",
        len(getattr(caption_vectorstore.docstore, "_dict", {})),  # noqa: SLF001
    )


if __name__ == "__main__":
    main()
