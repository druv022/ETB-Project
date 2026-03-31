"""Helpers for resolving image paths for the orchestrator ``/v1/assets/...`` proxy."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Final

# Retriever saves uploads as ``{uuid.uuid4().hex}_{original_filename}`` (see ``api/app.py``).
_UPLOAD_UUID_PREFIX: Final[re.Pattern[str]] = re.compile(
    r"^[0-9a-f]{32}_", flags=re.IGNORECASE
)

_MARKERS: Final[tuple[str, ...]] = (
    "document_output/",
    "document_output\\",
    "/document_output/",
)


def display_name_for_source_file(path_or_name: str) -> str:
    """Basename for UI labels: drop upload prefix ``<32-hex>_<original>.pdf``.

    Absolute paths and bare filenames are accepted. If stripping would yield an
    empty string, the original basename is returned.
    """
    raw = (path_or_name or "").strip()
    if not raw:
        return ""
    name = Path(raw).name
    stripped = _UPLOAD_UUID_PREFIX.sub("", name, count=1)
    return stripped if stripped else name


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
