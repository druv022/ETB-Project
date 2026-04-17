"""Orchestrator chat API key and admin log routes."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from etb_project.orchestrator.app import create_app


@pytest.fixture
def base_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER_BASE_URL", "http://retriever:8000")
    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_MODEL", "stepfun/step-3.5-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")


def test_chat_401_without_bearer_when_key_set(
    base_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ETB_ORCHESTRATOR_API_KEY", "chat-secret")
    with TestClient(create_app()) as c:
        r = c.post(
            "/v1/chat",
            json={"session_id": "s1", "message": "hi", "return_sources": False},
        )
    assert r.status_code == 401


def test_chat_401_wrong_bearer_when_key_set(
    base_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_ORCHESTRATOR_API_KEY", "chat-secret")
    with TestClient(create_app()) as c:
        r = c.post(
            "/v1/chat",
            json={"session_id": "s1", "message": "hi", "return_sources": False},
            headers={"Authorization": "Bearer wrong"},
        )
    assert r.status_code == 401


def test_chat_ok_with_bearer_when_key_set(
    base_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_ORCHESTRATOR_API_KEY", "chat-secret")

    def fake_build_graph(*args: object, **kwargs: object) -> object:
        class G:
            def invoke(self, _state: dict, **_kwargs: object) -> dict:
                return {
                    "answer": "ok",
                    "context_docs": [],
                    "messages": [],
                }

        return G()

    with patch(
        "etb_project.orchestrator.app.build_rag_graph", side_effect=fake_build_graph
    ):
        with TestClient(create_app()) as c:
            r = c.post(
                "/v1/chat",
                json={"session_id": "s1", "message": "hi", "return_sources": False},
                headers={"Authorization": "Bearer chat-secret"},
            )
    assert r.status_code == 200
    assert r.json().get("answer") == "ok"


def test_admin_logs_disabled_when_token_unset(
    base_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ETB_ADMIN_API_TOKEN", raising=False)
    with TestClient(create_app()) as c:
        r = c.get("/v1/admin/recent-logs")
    assert r.status_code == 404


def test_admin_logs_401_without_bearer(
    base_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm-token")
    with TestClient(create_app()) as c:
        r = c.get("/v1/admin/recent-logs")
    assert r.status_code == 401


def test_admin_logs_200_with_bearer(
    base_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm-token")
    with TestClient(create_app()) as c:
        c.get("/v1/health")
        r = c.get(
            "/v1/admin/recent-logs",
            headers={"Authorization": "Bearer adm-token"},
        )
    assert r.status_code == 200
    data = r.json()
    assert "lines" in data
    assert isinstance(data["lines"], list)
