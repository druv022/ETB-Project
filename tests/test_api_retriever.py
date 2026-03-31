"""Tests for the standalone retriever FastAPI app."""

from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from etb_project.api.app import create_app


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


@pytest.fixture
def client(tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    # Avoid loading real FAISS in lifespan when index not ready
    with TestClient(create_app()) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_without_index(client: TestClient) -> None:
    r = client.get("/v1/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["index_ready"] is False
    assert data["ready"] is False


def test_retrieve_index_not_ready(client: TestClient) -> None:
    r = client.post("/v1/retrieve", json={"query": "hello"})
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "INDEX_NOT_READY"


def test_retrieve_with_mock_docs(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))

    mock_doc = MagicMock()
    mock_doc.page_content = "chunk text"
    mock_doc.metadata = {"source": "x.pdf", "page": 1}

    with patch(
        "etb_project.api.state.RetrieverServiceState.retrieve",
        return_value=[mock_doc],
    ):
        with TestClient(create_app()) as client:
            r = client.post("/v1/retrieve", json={"query": "q", "k": 5})
    assert r.status_code == 200
    data = r.json()
    assert len(data["chunks"]) == 1
    assert data["chunks"][0]["content"] == "chunk text"
    assert data["chunks"][0]["metadata"]["source"] == "x.pdf"


def test_retrieve_requires_auth_when_key_set(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("RETRIEVER_API_KEY", "secret")
    with TestClient(create_app()) as client:
        r = client.post("/v1/retrieve", json={"query": "q"})
        assert r.status_code == 401
        r2 = client.post(
            "/v1/retrieve",
            json={"query": "q"},
            headers={"Authorization": "Bearer secret"},
        )
        assert r2.status_code == 503


def test_rate_limit_retrieve(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_RATE_LIMIT_PER_MINUTE", "2")
    with TestClient(create_app()) as client:
        client.get("/v1/health")
        c1 = client.post("/v1/retrieve", json={"query": "a"})
        c2 = client.post("/v1/retrieve", json={"query": "b"})
        c3 = client.post("/v1/retrieve", json={"query": "c"})
    assert c1.status_code == 503
    assert c2.status_code == 503
    assert c3.status_code == 429


def test_index_no_files(client: TestClient) -> None:
    # Multipart with no files may 422 from FastAPI before our handler
    r = client.post("/v1/index/documents?reset=false")
    assert r.status_code in (400, 422)


def test_index_busy_returns_423(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_INDEX_ASYNC", "false")
    from etb_project.api import app as app_module

    lock = app_module._index_exclusive

    class Hold:
        def __enter__(self) -> None:
            acquired = lock.acquire(blocking=False)
            assert acquired

        def __exit__(self, *args: object) -> None:
            lock.release()

    pdf_bytes = b"%PDF-1.4 minimal"
    files = {"files": ("a.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    with patch("etb_project.api.app._run_index_sync"):
        with Hold():
            with TestClient(create_app()) as client:
                r = client.post(
                    "/v1/index/documents",
                    files=files,
                    data={"reset": "false"},
                )
    assert r.status_code == 423
    assert r.json()["code"] == "INDEX_BUSY"


def test_job_not_found(client: TestClient) -> None:
    r = client.get("/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["code"] == "JOB_NOT_FOUND"


def test_retrieve_response_schema_contract(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Contract: each chunk has string content and object metadata."""
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    mock_doc = MagicMock()
    mock_doc.page_content = "x"
    mock_doc.metadata = {}
    with patch(
        "etb_project.api.state.RetrieverServiceState.retrieve",
        return_value=[mock_doc],
    ):
        with TestClient(create_app()) as client:
            r = client.post("/v1/retrieve", json={"query": "q"})
    assert r.status_code == 200
    ch = r.json()["chunks"][0]
    assert "content" in ch and isinstance(ch["content"], str)
    assert "metadata" in ch and isinstance(ch["metadata"], dict)
