"""Tests for Orion READY TO RETRIEVE parsing."""

from __future__ import annotations

from etb_project.orchestrator.orion_parse import parse_orion_response


def test_parse_no_marker() -> None:
    r = parse_orion_response("Which quarter do you mean?")
    assert not r.ready
    assert r.refined_query is None
    assert r.display_text == "Which quarter do you mean?"


def test_parse_ready_case_insensitive() -> None:
    r = parse_orion_response(
        "Confirmed. ready to retrieve: Net sales for FY2023 by region."
    )
    assert r.ready
    assert r.refined_query == "Net sales for FY2023 by region."
    assert "ready to retrieve" in r.display_text.lower()


def test_parse_ready_fallback_query() -> None:
    r = parse_orion_response("READY TO RETRIEVE:", fallback_query="fallback q")
    assert r.ready
    assert r.refined_query == "fallback q"


def test_parse_empty() -> None:
    r = parse_orion_response("   ")
    assert not r.ready
    assert r.refined_query is None
    assert r.display_text == ""
