"""Tests for transaction / data-router LLM output parsers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from etb_project.orchestrator.transaction_parse import (
    TransactionFetchParams,
    parse_data_router_response,
    parse_transaction_gate_response,
)


def test_parse_data_router_json() -> None:
    text = '{"data_route": "transactions", "rationale": "sales"}'
    r = parse_data_router_response(text)
    assert r.data_route == "transactions"


def test_parse_data_router_defaults_to_documents() -> None:
    r = parse_data_router_response("not json")
    assert r.data_route == "documents"


def test_parse_data_router_both() -> None:
    r = parse_data_router_response('{"data_route": "both"}')
    assert r.data_route == "both"


def test_parse_transaction_gate_clarify() -> None:
    r = parse_transaction_gate_response("Which quarter do you mean?")
    assert not r.ready
    assert "quarter" in r.clarify_text.lower()


def test_parse_transaction_gate_ready_with_json() -> None:
    text = """OK.
READY TO QUERY:
{"start_date": "2024-01-01", "end_date": "2024-03-31", "limit": 100}
"""
    r = parse_transaction_gate_response(text)
    assert r.ready
    assert r.params is not None
    assert r.params.start_date == "2024-01-01"
    assert r.params.end_date == "2024-03-31"
    assert r.params.limit == 100


def test_transaction_fetch_params_rejects_bad_filter_column() -> None:
    with pytest.raises(ValidationError):
        TransactionFetchParams(
            filters={"NotAColumn": ["x"]},
        )
