"""In-process dual FAISS state for the retriever API."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.models import get_ollama_embedding_model as get_embeddings
from etb_project.retrieval import DualRetriever
from etb_project.vectorstore.faiss_backend import FaissDualVectorStoreBackend

logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _serialize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key, val in meta.items():
        if isinstance(val, (str, int, float, bool)) or val is None:
            out[str(key)] = val
        else:
            out[str(key)] = str(val)
    return out


class RetrieverServiceState:
    """Loads dual FAISS stores and runs ``DualRetriever`` under a lock."""

    def __init__(self, vector_store_root: Path) -> None:
        self._vector_store_root = vector_store_root
        self._backend = FaissDualVectorStoreBackend()
        self._embeddings: Embeddings = get_embeddings()
        # RLock: indexing holds the lock across persist + reload in the same thread.
        self._lock = threading.RLock()
        self._text_vs: FAISS | None = None
        self._caption_vs: FAISS | None = None

    @property
    def vector_store_root(self) -> Path:
        return self._vector_store_root

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    def index_ready(self) -> bool:
        return self._backend.is_ready(self._vector_store_root)

    def embeddings_ping(self) -> bool:
        try:
            self._embeddings.embed_query("ping")
            return True
        except Exception as exc:
            logger.warning("Embeddings ping failed: %s", exc)
            return False

    def load_from_disk(self) -> None:
        """Load or reload FAISS stores from disk (caller should hold ``_lock``)."""
        if not self.index_ready():
            self._text_vs = None
            self._caption_vs = None
            return
        self._text_vs, self._caption_vs = self._backend.load(
            self._vector_store_root,
            embeddings=self._embeddings,
        )
        logger.info("Loaded dual FAISS from %s", self._vector_store_root)

    def ensure_loaded(self) -> None:
        with self._lock:
            if self._text_vs is not None and self._caption_vs is not None:
                return
            if not self.index_ready():
                raise FileNotFoundError(
                    f"Persisted vector index not found or incomplete at: {self._vector_store_root}"
                )
            self.load_from_disk()

    def retrieve(self, query: str, k: int) -> list[Document]:
        """Return merged documents for one query."""
        with self._lock:
            if self._text_vs is None or self._caption_vs is None:
                if not self.index_ready():
                    raise FileNotFoundError(
                        f"Persisted vector index not found or incomplete at: {self._vector_store_root}"
                    )
                self.load_from_disk()
            assert self._text_vs is not None and self._caption_vs is not None
            text_retriever = self._text_vs.as_retriever(search_kwargs={"k": k})
            caption_retriever = self._caption_vs.as_retriever(search_kwargs={"k": k})
            dual = DualRetriever(
                text_retriever=text_retriever,
                caption_retriever=caption_retriever,
                k_total=k,
            )
            return dual.invoke(query)

    def reload_after_index(self) -> None:
        """Call after persist to refresh in-memory stores."""
        with self._lock:
            self.load_from_disk()
