"""HTTP-backed retriever that calls ``POST /v1/retrieve`` on the standalone API."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class RemoteRetriever:
    """Implements ``invoke(query) -> list[Document]`` for ``build_rag_graph``."""

    def __init__(
        self,
        base_url: str,
        *,
        k: int = 10,
        timeout_s: float = 60.0,
        api_key: str | None = None,
        strategy: str | None = None,
        hyde_mode: str | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._k = k
        self._timeout = timeout_s
        self._strategy = strategy
        self._hyde_mode = hyde_mode
        headers: dict[str, str] = {}
        key = api_key or os.environ.get("RETRIEVER_API_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        self._client = httpx.Client(timeout=timeout_s, headers=headers)

    def invoke(self, query: str) -> list[Document]:
        """One HTTP round-trip per ``invoke`` (option A in deployment docs)."""
        url = f"{self._base}/v1/retrieve"
        payload: dict[str, Any] = {"query": query, "k": self._k}
        if self._strategy in ("dense", "hybrid"):
            payload["strategy"] = self._strategy
        if self._hyde_mode in ("off", "replace", "fuse"):
            payload["hyde_mode"] = self._hyde_mode
        try:
            response = self._client.post(url, json=payload)
        except httpx.RequestError as exc:
            logger.error("Remote retriever request failed: %s", exc)
            raise RuntimeError(f"Retriever service unreachable: {exc}") from exc

        if response.status_code == 503:
            raise RuntimeError(
                "Retriever index not ready (503). Build the index or wait for readiness."
            )
        if response.status_code == 401:
            raise RuntimeError("Retriever API rejected credentials (401).")
        response.raise_for_status()
        data = response.json()
        chunks = data.get("chunks") or []
        return [
            Document(
                page_content=str(c.get("content", "")),
                metadata=dict(c.get("metadata") or {}),
            )
            for c in chunks
        ]

    def close(self) -> None:
        self._client.close()
