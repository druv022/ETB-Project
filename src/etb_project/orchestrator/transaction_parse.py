"""Parse data-router and transaction-gate LLM outputs.

The router returns a small JSON object with ``data_route``. The transaction gate
either asks a clarification (no ``READY TO QUERY`` marker) or marks readiness
with ``READY TO QUERY:`` followed by JSON that validates as
:class:`TransactionFetchParams` (allowlisted filter columns, date strings, row cap).

Used only by :mod:`etb_project.graph_rag` when ``enable_data_router`` is enabled;
Orion parsing remains in :mod:`etb_project.orchestrator.orion_parse`.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from etb_project.transaction_queries import (
    ALLOWED_FILTER_COLUMNS,
    MAX_QUERY_LIMIT,
)

DataRoute = Literal["documents", "transactions", "both"]

_READY_TXN_PATTERN = re.compile(
    r"READY\s+TO\s+QUERY\s*:",
    re.IGNORECASE | re.MULTILINE,
)


class TransactionFetchParams(BaseModel):
    """Validated parameters for ``transaction_queries.load_transactions``."""

    start_date: str | None = None
    end_date: str | None = None
    filters: dict[str, list[str]] | None = None
    limit: int = Field(default=500, ge=1, le=MAX_QUERY_LIMIT)
    include_catalog: bool = True

    @field_validator("filters")
    @classmethod
    def filters_columns(
        cls, v: dict[str, list[str]] | None
    ) -> dict[str, list[str]] | None:
        if not v:
            return v
        for key in v:
            if key not in ALLOWED_FILTER_COLUMNS:
                raise ValueError(f"Filter column not allowed: {key!r}")
        return v


@dataclass(frozen=True)
class DataRouterParseResult:
    data_route: DataRoute
    raw_text: str


@dataclass(frozen=True)
class TransactionGateParseResult:
    ready: bool
    clarify_text: str
    params: TransactionFetchParams | None
    display_text: str


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object extraction from model output (brace-balanced)."""
    stripped = (text or "").strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    if start < 0:
        return None
    depth = 0
    for j in range(start, len(stripped)):
        if stripped[j] == "{":
            depth += 1
        elif stripped[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(stripped[start : j + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def parse_data_router_response(text: str) -> DataRouterParseResult:
    """Parse ``{"data_route": "documents"|"transactions"|"both"}`` from LLM text."""
    stripped = (text or "").strip()
    obj = _extract_json_object(stripped)
    route: DataRoute = "documents"
    if obj and "data_route" in obj:
        raw = str(obj["data_route"]).strip().lower()
        if raw in ("documents", "document", "docs", "rag"):
            route = "documents"
        elif raw in ("transactions", "transaction", "sql", "data", "db"):
            route = "transactions"
        elif raw in ("both", "all", "hybrid"):
            route = "both"
    return DataRouterParseResult(data_route=route, raw_text=stripped)


def parse_transaction_gate_response(
    text: str,
) -> TransactionGateParseResult:
    """Parse READY TO QUERY vs clarification; extract ``TransactionFetchParams`` JSON."""
    stripped = (text or "").strip()
    if not stripped:
        return TransactionGateParseResult(
            ready=False,
            clarify_text="",
            params=None,
            display_text="",
        )

    m = _READY_TXN_PATTERN.search(stripped)
    if not m:
        return TransactionGateParseResult(
            ready=False,
            clarify_text=stripped,
            params=None,
            display_text=stripped,
        )

    after = stripped[m.end() :].strip()
    params: TransactionFetchParams | None = None
    obj = _extract_json_object(after)
    if obj:
        try:
            params = TransactionFetchParams.model_validate(
                {
                    "start_date": obj.get("start_date"),
                    "end_date": obj.get("end_date"),
                    "filters": obj.get("filters"),
                    "limit": obj.get("limit", 500),
                    "include_catalog": obj.get("include_catalog", True),
                }
            )
        except ValueError:
            params = None

    if params is not None:
        return TransactionGateParseResult(
            ready=True,
            clarify_text="",
            params=params,
            display_text=stripped,
        )

    return TransactionGateParseResult(
        ready=False,
        clarify_text=stripped,
        params=None,
        display_text=stripped,
    )


def validate_transaction_params(params: TransactionFetchParams) -> None:
    """Re-raise Pydantic/ValueError for callers that build dicts manually."""
    TransactionFetchParams.model_validate(params.model_dump())


__all__ = [
    "DataRoute",
    "DataRouterParseResult",
    "TransactionFetchParams",
    "TransactionGateParseResult",
    "parse_data_router_response",
    "parse_transaction_gate_response",
    "validate_transaction_params",
]
