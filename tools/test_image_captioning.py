#!/usr/bin/env python3
"""Standalone script: caption a single image using ``etb_project`` captioning backends.

**Default for this tool:** OpenRouter’s HTTP API via the **OpenAI Python SDK** (same as
``OpenRouterImageCaptioner`` in ``captioning.py``): ``OpenAI(base_url=…/openrouter…/v1)`` and
``chat.completions.create`` with a vision model. Set ``OPENROUTER_API_KEY`` and optionally
``openrouter_image_caption_model`` in ``settings.yaml`` (or pass ``--model``).

Use the project Conda environment **etb** (recommended)::

    conda activate etb
    pip install -e .

Requires the package importable (editable install or ``PYTHONPATH=src`` if you skip install).

Examples::

    export OPENROUTER_API_KEY=…
    conda activate etb
    pip install -e .
    python tools/test_image_captioning.py path/to/screenshot.png

    # No API keys — deterministic placeholder caption
    python tools/test_image_captioning.py --backend mock path/to/image.png

    # Direct OpenAI API (not OpenRouter)
    python tools/test_image_captioning.py --backend openai --model gpt-4o-mini path/to/image.png

    # Same as default — OpenRouter + OpenAI SDK
    python tools/test_image_captioning.py --backend openrouter path/to/image.png
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from etb_project.document_processing.captioning import ImageCaptioner


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _ensure_src_on_path() -> None:
    src = _project_root() / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _select_captioner(backend: str) -> ImageCaptioner:
    from etb_project.config import load_config
    from etb_project.document_processing.captioning import (
        MockImageCaptioner,
        OpenAIImageCaptioner,
        OpenRouterImageCaptioner,
    )

    if backend == "mock":
        return MockImageCaptioner()
    if backend == "openrouter":
        return OpenRouterImageCaptioner()
    if backend == "openai":
        return OpenAIImageCaptioner()

    cfg = load_config()
    if cfg.openrouter_image_caption_model:
        return OpenRouterImageCaptioner()
    if cfg.openai_image_caption_model:
        return OpenAIImageCaptioner()

    print(
        "No caption backend configured in settings.yaml "
        "(openrouter_image_caption_model / openai_image_caption_model). "
        "Use --backend openrouter|openai|mock, or set models in config.",
        file=sys.stderr,
    )
    sys.exit(2)


def main() -> None:
    _ensure_src_on_path()

    parser = argparse.ArgumentParser(
        description="Generate a caption for one image via etb_project ImageCaptioner backends.",
    )
    parser.add_argument(
        "image",
        type=Path,
        help="Path to an image file (e.g. PNG, JPEG, WebP).",
    )
    parser.add_argument(
        "--backend",
        choices=("auto", "openrouter", "openai", "mock"),
        default="openrouter",
        help=(
            "Default: openrouter — OpenRouter API using the OpenAI Python SDK "
            "(OPENROUTER_API_KEY; model from settings or --model). "
            "auto matches document_processor_cli (OpenRouter config first, else OpenAI). "
            "mock uses MockImageCaptioner (no network)."
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override the vision model id (otherwise from settings / captioner defaults).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Logging level (default: INFO).",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )

    image_path = args.image.expanduser().resolve()
    if not image_path.is_file():
        print(f"Not a file: {image_path}", file=sys.stderr)
        sys.exit(1)

    if args.backend == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "OPENROUTER_API_KEY is not set. Export it for OpenRouter testing, "
            "or use --backend mock for a local placeholder caption.",
            file=sys.stderr,
        )
        sys.exit(2)

    if args.backend == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set. Export it, or use --backend mock.",
            file=sys.stderr,
        )
        sys.exit(2)

    captioner = _select_captioner(args.backend)
    if args.model is not None:
        captioner.model = args.model

    caption = captioner.caption_image(image_path)
    if caption is None:
        print("No caption returned (check API keys, model, and logs).", file=sys.stderr)
        sys.exit(1)

    print(caption)


if __name__ == "__main__":
    main()
