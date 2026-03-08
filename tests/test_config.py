"""Tests for etb_project.config."""

from pathlib import Path

import pytest

from etb_project.config import AppConfig, load_config


def test_load_config_missing_file_returns_defaults() -> None:
    """When config file does not exist, load_config returns default AppConfig."""
    result = load_config(Path("/nonexistent/settings.yaml"))
    assert result.pdf is None
    assert result.query == ""
    assert result.retriever_k == 10
    assert result.log_level == "INFO"


def test_load_config_valid_yaml(tmp_path: Path) -> None:
    """load_config parses valid YAML and returns AppConfig."""
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text(
        "pdf: /path/to/doc.pdf\nquery: hello\nretriever_k: 5\nlog_level: DEBUG\n"
    )
    result = load_config(yaml_path)
    assert result.pdf == "/path/to/doc.pdf"
    assert result.query == "hello"
    assert result.retriever_k == 5
    assert result.log_level == "DEBUG"


def test_load_config_empty_file_returns_defaults(tmp_path: Path) -> None:
    """Empty or invalid YAML returns default AppConfig."""
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text("")
    result = load_config(yaml_path)
    assert result.pdf is None
    assert result.retriever_k == 10


def test_load_config_partial_yaml(tmp_path: Path) -> None:
    """Partial YAML fills only given fields; rest are defaults."""
    yaml_path = tmp_path / "settings.yaml"
    yaml_path.write_text("retriever_k: 3\n")
    result = load_config(yaml_path)
    assert result.retriever_k == 3
    assert result.pdf is None
    assert result.log_level == "INFO"


def test_app_config_defaults() -> None:
    """AppConfig has expected default values."""
    cfg = AppConfig()
    assert cfg.pdf is None
    assert cfg.folder is None
    assert cfg.query == ""
    assert cfg.retriever_k == 10
    assert cfg.log_level == "INFO"


def test_load_config_uses_etb_config_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ETB_CONFIG is set, load_config uses that path."""
    yaml_path = tmp_path / "custom.yaml"
    yaml_path.write_text("pdf: /custom.pdf\n")
    monkeypatch.setenv("ETB_CONFIG", str(yaml_path))
    result = load_config(None)
    assert result.pdf == "/custom.pdf"
