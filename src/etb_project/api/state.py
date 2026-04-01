"""In-process dual FAISS state for the retriever API."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Literal

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from etb_project.api.schemas import RetrieveRequest
from etb_project.api.settings import RetrieverAPISettings
from etb_project.models import get_ollama_embedding_model as get_embeddings
from etb_project.retrieval.exceptions import HybridSparseUnavailableError
from etb_project.retrieval.pipeline import run_retrieval
from etb_project.retrieval.sparse_retriever import Bm25DualSparseRetriever
from etb_project.vectorstore.faiss_backend import FaissDualVectorStoreBackend
from etb_project.vectorstore.manifest import IndexManifest

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


# Internal tracing keys — omit from API JSON (see retrieval-hyde plan).
_METADATA_STRIP_KEYS = frozenset({"ensemble_head"})


def _serialize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    return {
        str(k): _json_safe(v) for k, v in meta.items() if k not in _METADATA_STRIP_KEYS
    }


class RetrieverServiceState:
    """Loads dual FAISS stores and runs the retrieval pipeline under a lock."""

    def __init__(self, vector_store_root: Path) -> None:
        self._vector_store_root = vector_store_root
        self._backend = FaissDualVectorStoreBackend()
        self._embeddings: Embeddings = get_embeddings()
        # RLock: indexing holds the lock across persist + reload in the same thread.
        self._lock = threading.RLock()
        self._text_vs: FAISS | None = None
        self._caption_vs: FAISS | None = None
        self._bm25: Bm25DualSparseRetriever | None = None

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
            self._bm25 = None
            return
        self._text_vs, self._caption_vs = self._backend.load(
            self._vector_store_root,
            embeddings=self._embeddings,
        )
        self._bm25 = None
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

    def _resolve_strategy(
        self, request: RetrieveRequest, settings: RetrieverAPISettings
    ) -> Literal["dense", "hybrid"]:
        raw = request.strategy or settings.default_retrieve_strategy
        if raw == "hybrid":
            return "hybrid"
        return "dense"

    def _ensure_bm25(self) -> Bm25DualSparseRetriever:
        if self._bm25 is not None:
            return self._bm25
        manifest_path = self._vector_store_root / "manifest.json"
        manifest = IndexManifest.load(manifest_path)
        if not manifest.sparse_backend:
            raise HybridSparseUnavailableError(
                "This index was built without a sparse corpus. Rebuild the index to use hybrid."
            )
        try:
            self._bm25 = Bm25DualSparseRetriever.load(self._vector_store_root)
        except Exception as exc:
            raise HybridSparseUnavailableError(
                f"Sparse index missing or corrupt: {exc}"
            ) from exc
        return self._bm25

    def retrieve(
        self,
        request: RetrieveRequest,
        k: int,
        settings: RetrieverAPISettings,
        *,
        request_id: str | None = None,
    ) -> list[Document]:
        """Return top-``k`` documents for the retrieval request."""
        with self._lock:
            if self._text_vs is None or self._caption_vs is None:
                if not self.index_ready():
                    raise FileNotFoundError(
                        f"Persisted vector index not found or incomplete at: {self._vector_store_root}"
                    )
                self.load_from_disk()
            assert self._text_vs is not None and self._caption_vs is not None

            strategy = self._resolve_strategy(request, settings)
            bm25: Bm25DualSparseRetriever | None = None
            if strategy == "hybrid":
                bm25 = self._ensure_bm25()

            return run_retrieval(
                request=request,
                k=k,
                strategy=strategy,
                text_vs=self._text_vs,
                caption_vs=self._caption_vs,
                bm25=bm25,
                embeddings=self._embeddings,
                settings=settings,
                request_id=request_id,
            )

    def reload_after_index(self) -> None:
        """Call after persist to refresh in-memory stores."""
        with self._lock:
            self._bm25 = None
            self.load_from_disk()
