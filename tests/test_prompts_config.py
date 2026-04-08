"""Tests for ``etb_project.prompts_config``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from etb_project.prompts_config import AppPrompts, load_prompts, resolve_prompts_path


def test_load_prompts_returns_app_prompts() -> None:
    """Default repo prompts.yaml loads and validates."""
    p = load_prompts()
    assert isinstance(p, AppPrompts)
    assert "Orion" in p.orion_system
    assert "{query}" in p.hyde_user_template
    assert "{passages_block}" in p.rerank_user_template


def test_load_prompts_from_custom_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ETB_PROMPTS overrides location; file must contain all keys."""
    yaml_path = tmp_path / "custom.yaml"
    data = {
        "orion_system": "x",
        "rag_answer_with_context": "x",
        "rag_answer_no_context": "x",
        "hyde_system": "x",
        "hyde_user_template": "{query}",
        "rerank_llm_system": "x",
        "rerank_user_template": "{query}",
        "image_caption_system": "x",
        "image_caption_user": "x",
    }
    yaml_path.write_text(yaml.dump(data), encoding="utf-8")
    monkeypatch.setenv("ETB_PROMPTS", str(yaml_path))
    p = load_prompts()
    assert p.orion_system == "x"


def test_load_prompts_missing_file_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ETB_PROMPTS", str(tmp_path / "nope.yaml"))
    with pytest.raises(FileNotFoundError):
        load_prompts()


def test_resolve_prompts_path_respects_etb_prompts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = tmp_path / "p.yaml"
    p.write_text("x: 1\n", encoding="utf-8")
    monkeypatch.setenv("ETB_PROMPTS", str(p))
    assert resolve_prompts_path() == p.expanduser()


def test_resolve_prompts_path_next_to_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "settings.yaml"
    cfg.write_text("query: ''\n", encoding="utf-8")
    monkeypatch.setenv("ETB_CONFIG", str(cfg))
    monkeypatch.delenv("ETB_PROMPTS", raising=False)
    expected = cfg.parent / "prompts.yaml"
    assert resolve_prompts_path() == expected
