"""Tests for mapping LangChain provider errors to orchestrator API errors."""

from __future__ import annotations

from etb_project.orchestrator.exceptions import OrchestratorAPIError
from etb_project.orchestrator.llm_provider_errors import map_provider_invoke_error


def test_map_provider_none_for_non_value_error() -> None:
    assert map_provider_invoke_error(RuntimeError("x")) is None


def test_map_provider_none_for_value_error_without_dict() -> None:
    assert map_provider_invoke_error(ValueError("plain")) is None


def test_map_524_to_upstream_timeout() -> None:
    exc = ValueError({"message": "Provider returned error", "code": 524})
    out = map_provider_invoke_error(exc)
    assert isinstance(out, OrchestratorAPIError)
    assert out.status_code == 502
    assert out.code == "LLM_UPSTREAM_TIMEOUT"
    assert "524" in out.message


def test_map_generic_provider_dict() -> None:
    exc = ValueError({"message": "Rate limited", "code": 429})
    out = map_provider_invoke_error(exc)
    assert isinstance(out, OrchestratorAPIError)
    assert out.code == "LLM_PROVIDER_ERROR"
    assert out.message == "Rate limited"
