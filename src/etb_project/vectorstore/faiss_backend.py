"""FAISS persistence backend for ETB dual vector stores.

The project maintains *two* dense indices:
- **text**: chunk-level text content
- **captions**: image-caption documents

Why a backend abstraction:
- Keeps persistence/load behavior (folder layout, manifest validation) in one place.
- Makes it possible to add other vector DBs later without rewriting the indexing API.

Compatibility note:
- LangChain's `FAISS.load_local` signature has changed across versions. We use
  signature inspection to pass only supported arguments while still enabling
  deserialization for locally persisted indices.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

from .base import DualVectorStoreBackend
from .manifest import IndexManifest


class FaissDualVectorStoreBackend(DualVectorStoreBackend):
    """Persist/load dual FAISS indices (text + captions)."""

    backend_name = "faiss"
    manifest_filename = "manifest.json"
    text_dirname = "text"
    captions_dirname = "captions"

    def is_ready(self, root: Path) -> bool:
        manifest_path = root / self.manifest_filename
        if not (
            manifest_path.exists()
            and (root / self.text_dirname).exists()
            and (root / self.captions_dirname).exists()
        ):
            return False
        try:
            manifest = IndexManifest.load(manifest_path)
        except Exception:
            return False
        if manifest.sparse_backend:
            sparse = root / "sparse"
            for name in ("version.txt", "text_corpus.jsonl", "captions_corpus.jsonl"):
                if not (sparse / name).is_file():
                    return False
        return True

    def persist(
        self,
        root: Path,
        *,
        text_vectorstore: FAISS,
        caption_vectorstore: FAISS,
        manifest: IndexManifest,
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)

        text_dir = root / self.text_dirname
        captions_dir = root / self.captions_dirname
        text_dir.mkdir(parents=True, exist_ok=True)
        captions_dir.mkdir(parents=True, exist_ok=True)

        # Save into separate subfolders so each index can be loaded independently.
        text_vectorstore.save_local(str(text_dir))
        caption_vectorstore.save_local(str(captions_dir))
        manifest.save(root / self.manifest_filename)

    def _faiss_load(
        self,
        *,
        index_dir: Path,
        embeddings: Embeddings,
    ) -> FAISS:
        sig = inspect.signature(FAISS.load_local)
        allow_dangerous = "allow_dangerous_deserialization" in sig.parameters
        has_index_name = "index_name" in sig.parameters

        # Avoid `**kwargs` so mypy can type-check across LangChain versions.
        if allow_dangerous and has_index_name:
            return FAISS.load_local(
                str(index_dir),
                embeddings,
                index_name="index",
                allow_dangerous_deserialization=True,
            )
        if allow_dangerous:
            return FAISS.load_local(
                str(index_dir),
                embeddings,
                allow_dangerous_deserialization=True,
            )
        if has_index_name:
            return FAISS.load_local(
                str(index_dir),
                embeddings,
                index_name="index",
            )
        return FAISS.load_local(str(index_dir), embeddings)

    def load(
        self,
        root: Path,
        *,
        embeddings: Embeddings,
    ) -> tuple[FAISS, FAISS]:
        if not self.is_ready(root):
            raise FileNotFoundError(
                f"Persisted vector index not found or incomplete at: {root}"
            )

        # Load manifest to allow backend/version validation later if needed.
        manifest = IndexManifest.load(root / self.manifest_filename)
        if manifest.backend != self.backend_name:
            raise ValueError(
                f"Index backend mismatch: manifest={manifest.backend}, expected={self.backend_name}"
            )

        text_dir = root / self.text_dirname
        captions_dir = root / self.captions_dirname
        text_store = self._faiss_load(index_dir=text_dir, embeddings=embeddings)
        caption_store = self._faiss_load(index_dir=captions_dir, embeddings=embeddings)
        return text_store, caption_store
