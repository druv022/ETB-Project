"""Load application LLM prompts from ``src/config/prompts.yaml``.

See :func:`resolve_prompts_path` for ``ETB_PROMPTS`` and placement next to
``ETB_CONFIG`` / default ``settings.yaml``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from etb_project.config import resolve_settings_yaml_path


class AppPrompts(BaseModel):
    """All chat/vision prompts used by ``etb_project`` (not tools/)."""

    orion_system: str = Field(min_length=1)
    rag_answer_with_context: str = Field(min_length=1)
    rag_answer_no_context: str = Field(min_length=1)
    hyde_system: str = Field(min_length=1)
    hyde_user_template: str = Field(min_length=1)
    rerank_llm_system: str = Field(min_length=1)
    rerank_user_template: str = Field(min_length=1)
    image_caption_system: str = Field(min_length=1)
    image_caption_user: str = Field(min_length=1)


def resolve_prompts_path(config_path: str | Path | None = None) -> Path:
    """Path to ``prompts.yaml``.

    Precedence:
    - ``ETB_PROMPTS`` if set (absolute or relative path).
    - Else ``prompts.yaml`` in the same directory as the resolved settings YAML
      (see :func:`etb_project.config.resolve_settings_yaml_path`).
    """
    env = os.environ.get("ETB_PROMPTS")
    if env:
        return Path(env).expanduser()
    settings = resolve_settings_yaml_path(config_path)
    return settings.parent / "prompts.yaml"


@lru_cache(maxsize=16)
def _load_prompts_cached(path_str: str, mtime: float) -> AppPrompts:
    path = Path(path_str)
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Prompts file must contain a mapping: {path}")
    return AppPrompts.model_validate(data)


def load_prompts(config_path: str | Path | None = None) -> AppPrompts:
    """Load and validate prompts; re-reads when the file changes (mtime in cache key)."""
    path = resolve_prompts_path(config_path)
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompts file not found: {path}. Set ETB_PROMPTS or add prompts.yaml "
            "next to settings.yaml."
        )
    mtime = path.stat().st_mtime
    return _load_prompts_cached(str(path.resolve()), mtime)


__all__ = ["AppPrompts", "load_prompts", "resolve_prompts_path"]
