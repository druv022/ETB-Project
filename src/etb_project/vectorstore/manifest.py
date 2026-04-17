"""Manifest format for persisted indices.

The manifest is a small JSON file stored alongside the vector store folders.
It allows the runtime to:
- Detect whether an index is complete and loadable.
- Enforce invariants for append mode (chunking config, embedding model id).
- Advertise the presence/version of optional components (BM25 corpus, hierarchy sqlite).

This is intentionally forward-compatible: new optional fields can be added while
older manifests should still load with sensible defaults.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class IndexManifest:
    """Metadata that describes a persisted dual vector index."""

    backend: str
    pdf_path: str
    chunk_size: int
    chunk_overlap: int
    embedding_model_id: str
    created_at: str
    sparse_backend: str | None = None
    sparse_version: str | None = None
    hierarchy_backend: str | None = None
    hierarchy_schema_version: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def create(
        *,
        backend: str,
        pdf_path: str,
        chunk_size: int,
        chunk_overlap: int,
        embedding_model_id: str,
        sparse_backend: str | None = None,
        sparse_version: str | None = None,
        hierarchy_backend: str | None = None,
        hierarchy_schema_version: int | None = None,
    ) -> IndexManifest:
        return IndexManifest(
            backend=backend,
            pdf_path=pdf_path,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model_id=embedding_model_id,
            created_at=IndexManifest._now_iso(),
            sparse_backend=sparse_backend,
            sparse_version=sparse_version,
            hierarchy_backend=hierarchy_backend,
            hierarchy_schema_version=hierarchy_schema_version,
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @staticmethod
    def load(path: Path) -> IndexManifest:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        # Be resilient to missing fields if older manifests exist.
        hb = data.get("hierarchy_backend")
        hsv = data.get("hierarchy_schema_version")
        return IndexManifest(
            backend=str(data["backend"]),
            pdf_path=str(data["pdf_path"]),
            chunk_size=int(data["chunk_size"]),
            chunk_overlap=int(data["chunk_overlap"]),
            embedding_model_id=str(data["embedding_model_id"]),
            created_at=str(data.get("created_at", IndexManifest._now_iso())),
            sparse_backend=(
                str(data["sparse_backend"]) if data.get("sparse_backend") else None
            ),
            sparse_version=(
                str(data["sparse_version"]) if data.get("sparse_version") else None
            ),
            hierarchy_backend=str(hb) if hb else None,
            hierarchy_schema_version=int(hsv) if hsv is not None else None,
        )
