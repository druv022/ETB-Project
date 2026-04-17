"""Tests for LangSmith-oriented tracing toggles and HTTP control plane."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from etb_project.api.app import create_app as create_retriever_app
from etb_project.orchestrator.app import create_app as create_orchestrator_app
from etb_project.tracing.settings import TracingStore, get_tracing_store


@pytest.fixture
def tmp_settings_yaml(tmp_path: Path) -> Path:
    vs = tmp_path / "data" / "vector_index"
    vs.mkdir(parents=True)
    p = tmp_path / "settings.yaml"
    p.write_text(
        f'vector_store_path: "{vs.as_posix()}"\nretriever_k: 10\nlog_level: INFO\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture(autouse=True)
def _reset_tracing_store() -> None:
    """Restore shared tracing state after tests."""
    store = get_tracing_store()
    store.apply_partial(enabled=True, log_queries=True)
    yield
    store.apply_partial(enabled=True, log_queries=True)


def test_tracing_store_defaults_true_when_env_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ETB_TRACE_ENABLED", raising=False)
    monkeypatch.delenv("ETB_TRACE_LOG_QUERIES", raising=False)
    s = TracingStore()
    assert s.enabled is True
    assert s.log_queries is True


def test_tracing_store_env_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ETB_TRACE_ENABLED", "false")
    monkeypatch.setenv("ETB_TRACE_LOG_QUERIES", "0")
    s = TracingStore()
    assert s.enabled is False
    assert s.log_queries is False


def test_get_put_tracing_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER_BASE_URL", "http://retriever:8000")
    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_MODEL", "m")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.com/v1")
    with TestClient(create_orchestrator_app()) as client:
        r = client.get("/v1/tracing")
        assert r.status_code == 200
        data = r.json()
        assert data["service"] == "etb-orchestrator"
        assert data["enabled"] is True
        r2 = client.put("/v1/tracing", json={"log_queries": False})
        assert r2.status_code == 200
        assert r2.json()["log_queries"] is False


def test_put_tracing_retriever_requires_bearer_when_api_key_set(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("RETRIEVER_API_KEY", "secret-token")
    with TestClient(create_retriever_app()) as client:
        r = client.put("/v1/tracing", json={"enabled": False})
        assert r.status_code == 401
        r2 = client.put(
            "/v1/tracing",
            json={"enabled": False},
            headers={"Authorization": "Bearer secret-token"},
        )
        assert r2.status_code == 200
        assert r2.json()["enabled"] is False


def test_query_stats_respects_log_queries_flag() -> None:
    from etb_project.tracing import query_stats as qs_mod

    get_tracing_store().apply_partial(log_queries=True)
    s = qs_mod.query_stats_for_trace("hello world")
    assert "preview" in s

    get_tracing_store().apply_partial(log_queries=False)
    s2 = qs_mod.query_stats_for_trace("hello world")
    assert "sha256_prefix" in s2
    assert "preview" not in s2
