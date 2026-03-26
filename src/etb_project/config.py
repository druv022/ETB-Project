"""Application configuration. Loads from settings.yaml or ETB_CONFIG path."""

import os
from pathlib import Path

# PyYAML has no stubs in some envs (CI, pre-commit); types-PyYAML in requirements.txt when available
import yaml  # type: ignore[import-untyped,import-not-found]
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Application configuration model."""

    pdf: str | None = None
    folder: str | None = None
    query: str = ""
    retriever_k: int = Field(default=10, ge=1, le=100)
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR)$")

    # Persisted dual vector store settings.
    # When `main` runs, it will load the vector DB from `vector_store_path`
    # instead of rebuilding it from the PDF (unless you explicitly run the
    # indexing/build CLI).
    vector_store_backend: str = "faiss"
    vector_store_path: str | None = None

    # Vision-language model selection for image captioning backends.
    # Used by ``OpenRouterImageCaptioner`` / ``OpenAIImageCaptioner`` when
    # instantiated without an explicit ``model`` argument.
    openrouter_image_caption_model: str | None = None
    openai_image_caption_model: str | None = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


def resolve_artifact_path(path: str | Path | None) -> Path | None:
    """Resolve an artifact path so relative values land under ``data/``.

    This keeps generated artifacts (FAISS indices, extracted pages/chunks/images)
    out of the project root and consistently under the top-level ``data/`` folder.
    """

    if path is None:
        return None

    p = Path(path).expanduser()
    if p.is_absolute():
        return p

    # Normalize leading "./" to avoid double-prefixing.
    parts = [part for part in p.parts if part not in ("", ".")]
    if not parts:
        return DATA_DIR

    # If the caller already provided "data/..." keep it anchored under project root.
    if parts[0] == "data":
        return PROJECT_ROOT / Path(*parts)

    return DATA_DIR / Path(*parts)


def _default_config_path() -> Path:
    """Resolve default config path: try cwd-relative, then package-relative."""
    cwd_path = Path.cwd() / "src" / "config" / "settings.yaml"
    if cwd_path.exists():
        return cwd_path
    # Fallback: relative to this package (works when run from src/ or any cwd)
    package_dir = Path(__file__).resolve().parent
    return package_dir.parent / "config" / "settings.yaml"


def load_config(config_path: str | Path | None = None) -> AppConfig:
    """Load configuration from YAML file.

    Uses ETB_CONFIG env var if set; otherwise defaults to
    src/config/settings.yaml (cwd-relative or package-relative).
    """
    if config_path is None:
        env_path = os.environ.get("ETB_CONFIG")
        if env_path:
            path = Path(env_path)
        else:
            path = _default_config_path()
    else:
        path = Path(config_path)
    if not path.exists():
        return AppConfig()
    with open(path) as f:
        data = yaml.safe_load(f)
    cfg = AppConfig.model_validate(data if isinstance(data, dict) else {})
    if cfg.vector_store_path:
        # Store persisted indexes under ``data/`` by default.
        cfg.vector_store_path = str(resolve_artifact_path(cfg.vector_store_path))
    return cfg
