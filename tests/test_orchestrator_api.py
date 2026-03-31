"""Tests for the Orchestrator FastAPI app (no network)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from etb_project.orchestrator.app import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("RETRIEVER_BASE_URL", "http://retriever:8000")
    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_MODEL", "stepfun/step-3.5-flash")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    with TestClient(create_app()) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_requires_retriever_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETRIEVER_BASE_URL", raising=False)
    monkeypatch.setenv("ETB_LLM_PROVIDER", "openai_compat")
    monkeypatch.setenv("OPENAI_MODEL", "stepfun/step-3.5-flash")
    with TestClient(create_app()) as c:
        r = c.get("/v1/ready")
        assert r.status_code == 200
        assert r.json()["ready"] is False


def test_chat_happy_path_returns_answer_and_sources(client: TestClient) -> None:
    mock_doc = MagicMock()
    mock_doc.page_content = "chunk"
    mock_doc.metadata = {"source": "x.pdf", "page": 1}

    def fake_build_graph(*args: object, **kwargs: object) -> object:
        class G:
            def invoke(self, _state: dict) -> dict:
                return {
                    "answer": "hello",
                    "context_docs": [mock_doc],
                    "messages": [{"role": "assistant", "content": "hello"}],
                }

        return G()

    with patch(
        "etb_project.orchestrator.app.build_rag_graph", side_effect=fake_build_graph
    ):
        r = client.post(
            "/v1/chat",
            json={"session_id": "s1", "message": "q", "return_sources": True},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "hello"
    assert len(data["sources"]) == 1
    assert data["sources"][0]["metadata"]["source"] == "x.pdf"


def test_chat_returns_502_on_empty_answer(client: TestClient) -> None:
    def fake_build_graph(*args: object, **kwargs: object) -> object:
        class G:
            def invoke(self, _state: dict) -> dict:
                return {"answer": "   "}

        return G()

    with patch(
        "etb_project.orchestrator.app.build_rag_graph", side_effect=fake_build_graph
    ):
        r = client.post("/v1/chat", json={"session_id": "s1", "message": "q"})
    assert r.status_code == 502
    assert r.json()["code"] == "EMPTY_ANSWER"
