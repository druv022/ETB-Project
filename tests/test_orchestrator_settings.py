"""Tests for orchestrator environment settings."""

from __future__ import annotations

import pytest

from etb_project.orchestrator.settings import load_orchestrator_settings


def test_retriever_timeout_default_60(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER_BASE_URL", "http://retriever:8000")
    monkeypatch.delenv("RETRIEVER_TIMEOUT_S", raising=False)
    s = load_orchestrator_settings()
    assert s.retriever_timeout_s == 60.0


def test_retriever_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETRIEVER_BASE_URL", "http://retriever:8000")
    monkeypatch.setenv("RETRIEVER_TIMEOUT_S", "300")
    s = load_orchestrator_settings()
    assert s.retriever_timeout_s == 300.0
