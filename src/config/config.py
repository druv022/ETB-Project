from pathlib import Path
from typing import cast

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    pdf: str | None = None
    folder: str | None = None
    query: str = ""
    retriever_k: int = Field(default=10, ge=1, le=100)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")


def load_config(config_path: str | Path = "src/config/settings.yaml") -> AppConfig:
    path = Path(config_path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        data = yaml.safe_load(f)
    validated = AppConfig.model_validate(data if isinstance(data, dict) else {})
    return cast(AppConfig, validated)
