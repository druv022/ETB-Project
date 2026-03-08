"""Application configuration. Loads from settings.yaml or ETB_CONFIG path."""

import os
from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration model."""

    pdf: str | None = None
    folder: str | None = None
    query: str = ""
    retriever_k: int = Field(default=10, ge=1, le=100)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file.

    Uses ETB_CONFIG env var if set; otherwise defaults to
    src/config/settings.yaml relative to current working directory.
    """
    if config_path is None:
        env_path = os.environ.get("ETB_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            path = Path.cwd() / "src" / "config" / "settings.yaml"
    else:
        path = Path(config_path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        data = yaml.safe_load(f)
    validated = AppConfig.model_validate(data if isinstance(data, dict) else {})
    return cast(AppConfig, validated)
