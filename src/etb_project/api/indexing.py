"""Run PDF indexing for the HTTP API.

The retriever service can build/update its own indices via ``POST /v1/index``.
This module adapts the existing indexing pipeline (used by
``document_processor_cli``) to run inside the API process.

Key constraints (why it looks slightly "low level"):
- The API must update on-disk indices *and then* reload in-memory FAISS stores
  atomically from the perspective of concurrent retrieval requests.
- We therefore reuse the state object's re-entrant lock across the entire
  persist + reload section.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from etb_project.api.settings import RetrieverAPISettings
from etb_project.api.state import RetrieverServiceState
from etb_project.config import load_config
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


def _captioner_from_config() -> ImageCaptioner | None:
    """Enable image captioning only when configured.

    Captioning can be expensive and requires an external API key; the default is
    intentionally "off" unless a model is configured in YAML.
    """
    cfg = load_config()
    if cfg.openrouter_image_caption_model:
        return OpenRouterImageCaptioner()
    if cfg.openai_image_caption_model:
        return OpenAIImageCaptioner()
    return None


def run_index_pdfs(
    pdf_paths: list[Path],
    *,
    reset: bool,
    settings: RetrieverAPISettings,
    state: RetrieverServiceState,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    """Append or rebuild the persisted dual index, then reload in-memory stores."""
    if not pdf_paths:
        raise ValueError("No PDF paths to index.")

    resolved_store = settings.vector_store_path
    output_dir = settings.document_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    backend = FaissDualVectorStoreBackend()
    if reset and resolved_store.exists():
        logger.info("Resetting VDB by deleting: %s", resolved_store)
        shutil.rmtree(resolved_store)

    chunk_config = ChunkingConfig(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    captioner = _captioner_from_config()
    embeddings = get_embeddings()

    # Hold the shared lock across persist + reload so retrieval can't read a
    # partially written index. The lock is re-entrant (RLock) so this is safe
    # even if called by code that already holds it.
    with state._lock:
        append_to_and_persist_index_for_pdfs(
            pdf_paths=pdf_paths,
            output_dir=output_dir,
            vector_store_dir=resolved_store,
            chunking_config=chunk_config,
            image_captioner=captioner,
            backend=backend,
            embeddings=embeddings,
        )
        state.load_from_disk()
