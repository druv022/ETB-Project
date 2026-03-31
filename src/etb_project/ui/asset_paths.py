"""Helpers for resolving image paths for the orchestrator ``/v1/assets/...`` proxy."""

from __future__ import annotations

import os
from typing import Final

_MARKERS: Final[tuple[str, ...]] = (
    "document_output/",
    "document_output\\",
    "/document_output/",
)


def asset_request_headers() -> dict[str, str]:
    """Headers for asset GET requests (forwards retriever auth via orchestrator)."""
    headers: dict[str, str] = {}
    key = os.getenv("RETRIEVER_API_KEY") or os.getenv("ORCHESTRATOR_ASSET_BEARER_TOKEN")
    if key and str(key).strip():
        headers["Authorization"] = f"Bearer {str(key).strip()}"
    return headers


def derive_asset_path_from_stored_path(path_str: str) -> str | None:
    """Best-effort: turn an absolute on-disk path into a retriever ``asset_path``.

    Indexing may persist a developer-machine path (e.g. ``/Users/.../document_output/images/x.png``).
    The retriever serves files under ``ETB_DOCUMENT_OUTPUT_DIR``; the UI must request
    ``/v1/assets/<relative path>`` from that root (e.g. ``images/x.png`` or ``mypdf/images/x.png``).

    Returns a relative path using forward slashes, or ``None`` if no reliable suffix is found.
    """
    if not isinstance(path_str, str) or not path_str.strip():
        return None
    norm = path_str.replace("\\", "/")
    for marker in _MARKERS:
        if marker in norm:
            idx = norm.index(marker) + len(marker)
            suffix = norm[idx:].lstrip("/")
            return suffix if suffix else None
    # e.g. .../data/document_output/images/foo.png without "document_output/" match above
    im = "/images/"
    j = norm.find(im)
    if j != -1:
        return norm[j + 1 :]  # "images/..."
    return None
