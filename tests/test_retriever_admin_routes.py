"""Retriever admin HTTP routes (uploads, logs, reindex)."""

from __future__ import annotations

from pathlib import Path

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


def test_admin_uploads_404_when_token_unset(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.delenv("ETB_ADMIN_API_TOKEN", raising=False)
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        r = c.get("/v1/admin/uploads")
    assert r.status_code == 404


def test_admin_uploads_401_without_bearer(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm")
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        r = c.get("/v1/admin/uploads")
    assert r.status_code == 401


def test_admin_uploads_200_empty(
    tmp_settings_yaml: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    upl = tmp_path / "empty_uploads"
    upl.mkdir()
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_UPLOAD_DIR", str(upl))
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm")
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        r = c.get("/v1/admin/uploads", headers={"Authorization": "Bearer adm"})
    assert r.status_code == 200
    assert r.json().get("files") == []


def test_admin_delete_rejects_dotdot(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm")
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        # Path ``..`` must be encoded or the client normalizes away ``uploads``.
        r = c.delete(
            "/v1/admin/uploads/%2e%2e",
            headers={"Authorization": "Bearer adm"},
        )
    assert r.status_code == 400


def test_admin_recent_logs_200(
    tmp_settings_yaml: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_CONFIG", str(tmp_settings_yaml))
    monkeypatch.setenv("ETB_ADMIN_API_TOKEN", "adm")
    monkeypatch.delenv("RETRIEVER_API_KEY", raising=False)
    with TestClient(create_app()) as c:
        c.get("/v1/health")
        r = c.get(
            "/v1/admin/recent-logs",
            headers={"Authorization": "Bearer adm"},
        )
    assert r.status_code == 200
    assert "lines" in r.json()
