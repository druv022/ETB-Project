"""HTTP-backed retriever that calls ``POST /v1/retrieve`` on the standalone API."""

from __future__ import annotations

import logging
import os
from typing import Any, cast

import httpx
from langchain_core.documents import Document
from langsmith import traceable

from etb_project.tracing.query_stats import query_stats_for_trace
from etb_project.tracing.settings import get_tracing_store

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
        expand: bool | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._k = k
        self._timeout = timeout_s
        self._strategy = strategy
        self._hyde_mode = hyde_mode
        self._expand = expand
        headers: dict[str, str] = {}
        key = api_key or os.environ.get("RETRIEVER_API_KEY")
        if key:
            # The retriever API uses an optional static bearer token. The
            # orchestrator and CLI both forward this to support locked-down
            # deployments without teaching the UI multiple auth mechanisms.
            headers["Authorization"] = f"Bearer {key}"
        self._client = httpx.Client(timeout=timeout_s, headers=headers)

    def _build_payload(self, query: str) -> dict[str, Any]:
        payload: dict[str, Any] = {"query": query, "k": self._k}
        if self._strategy in ("dense", "hybrid"):
            payload["strategy"] = self._strategy
        if self._hyde_mode in ("off", "replace", "fuse"):
            payload["hyde_mode"] = self._hyde_mode
        if self._expand is not None:
            payload["expand"] = self._expand
        return payload

    def invoke(self, query: str) -> list[Document]:
        """One HTTP round-trip per ``invoke`` (option A in deployment docs)."""
        payload = self._build_payload(query)
        if not get_tracing_store().enabled:
            return self._post_and_parse(payload)
        out = _remote_retriever_http_trace(
            base_url=self._base,
            path="/v1/retrieve",
            timeout_s=self._timeout,
            payload_keys=sorted(payload.keys()),
            strategy_sent=payload.get("strategy"),
            hyde_mode_sent=payload.get("hyde_mode"),
            expand_sent=payload.get("expand"),
            query_stats=query_stats_for_trace(query),
            full_url=f"{self._base}/v1/retrieve",
            payload=payload,
            _client=self._client,
        )
        return cast(list[Document], out["documents"])

    def _post_and_parse(self, payload: dict[str, Any]) -> list[Document]:
        url = f"{self._base}/v1/retrieve"
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


@traceable(name="remote_retriever_http", run_type="retriever")
def _remote_retriever_http_trace(
    *,
    base_url: str,
    path: str,
    timeout_s: float,
    payload_keys: list[str],
    strategy_sent: str | None,
    hyde_mode_sent: str | None,
    expand_sent: bool | None,
    query_stats: dict[str, Any],
    full_url: str,
    payload: dict[str, Any],
    _client: httpx.Client,
) -> dict[str, Any]:
    """LangSmith run for the HTTP retriever (explicit inputs; outputs include status)."""
    try:
        response = _client.post(full_url, json=payload)
    except httpx.RequestError as exc:
        logger.error("Remote retriever request failed: %s", exc)
        raise RuntimeError(f"Retriever service unreachable: {exc}") from exc

    sc = response.status_code
    if sc == 503:
        raise RuntimeError(
            "Retriever index not ready (503). Build the index or wait for readiness."
        )
    if sc == 401:
        raise RuntimeError("Retriever API rejected credentials (401).")
    response.raise_for_status()
    data = response.json()
    chunks = data.get("chunks") or []
    documents = [
        Document(
            page_content=str(c.get("content", "")),
            metadata=dict(c.get("metadata") or {}),
        )
        for c in chunks
    ]
    return {
        "status_code": sc,
        "chunk_count": len(documents),
        "ok": True,
        "documents": documents,
    }
