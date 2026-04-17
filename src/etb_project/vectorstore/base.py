"""Backend abstraction for persisted dual vector stores.

The indexing pipeline and retriever runtime treat "the vector store" as two
coordinated indices:
- text chunks
- image-caption documents

This interface keeps persistence/load checks behind a single abstraction so the
rest of the codebase doesn't depend on FAISS-specific layout details.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from .manifest import IndexManifest


class DualVectorStoreBackend(ABC):
    """Abstract interface for building/persisting/loading dual vector stores."""

    @abstractmethod
    def persist(
        self,
        root: Path,
        *,
        text_vectorstore: FAISS,
        caption_vectorstore: FAISS,
        manifest: IndexManifest,
    ) -> None:
        """Persist the provided vector stores under ``root``."""

    @abstractmethod
    def load(
        self,
        root: Path,
        *,
        embeddings: Embeddings,
    ) -> tuple[FAISS, FAISS]:
        """Load persisted vector stores from ``root``."""

    @abstractmethod
    def is_ready(self, root: Path) -> bool:
        """Return True if ``root`` contains a usable persisted index."""
