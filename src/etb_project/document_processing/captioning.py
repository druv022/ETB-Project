"""Abstractions and helpers for image captioning.

This module defines a small, provider-agnostic interface for generating
captions for extracted images, along with simple concrete implementations:

* ``MockImageCaptioner`` – returns deterministic placeholder captions, useful
  for tests and local development.
* ``ChatCompletionImageCaptioner`` – shared OpenAI SDK implementation for
  OpenAI-compatible chat completions (vision).
* ``OpenRouterImageCaptioner`` – OpenRouter preset (custom ``base_url`` and
  config model field).
* ``OpenAIImageCaptioner`` – direct OpenAI API preset (default endpoint and
  config model field).
"""

from __future__ import annotations

import base64
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from openai import OpenAI, OpenAIError

from etb_project.config import load_config
from etb_project.prompts_config import load_prompts

logger = logging.getLogger(__name__)

_MAX_ERROR_BODY_LOG: Final[int] = 2000

# Re-exported for ``from ... import SYSTEM_PROMPT``; captioning uses load_prompts() per call
# so edits to prompts.yaml take effect without relying on these import-time snapshots.
_pp = load_prompts()
SYSTEM_PROMPT = _pp.image_caption_system
USER_PROMPT = _pp.image_caption_user


def _image_data_url_for_path(path: Path) -> str:
    # OpenAI-compatible vision APIs accept images as a URL or as a data URL.
    # Using a data URL keeps this self-contained (no separate asset hosting).
    image_bytes = path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    ext = path.suffix.lstrip(".").lower()
    mime_type = "image/png" if ext == "png" else f"image/{ext or 'png'}"
    return f"data:{mime_type};base64,{image_b64}"


def _string_from_completion(response: Any) -> str | None:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return None
    message = getattr(choices[0], "message", None)
    if message is None:
        return None
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip() or None
    return None


def _log_openai_error(provider_label: str, exc: BaseException) -> None:
    body: str | None = None
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            text = getattr(response, "text", None)
            if callable(text):
                text = text()
            if isinstance(text, str):
                body = text[:_MAX_ERROR_BODY_LOG]
        except Exception:  # noqa: BLE001 — best-effort logging only
            body = None
    if body:
        logger.warning(
            "%s caption request failed: %s (body: %s)", provider_label, exc, body
        )
    else:
        logger.warning("%s caption request failed: %s", provider_label, exc)


class ImageCaptioner(ABC):
    """Abstract base class for image captioning backends."""

    @abstractmethod
    def caption_image(self, path: Path) -> str | None:
        """Generate a caption for the image at ``path``.

        Implementations should return ``None`` if no caption can be produced
        (for example, due to an upstream error).
        """


@dataclass(slots=True)
class MockImageCaptioner(ImageCaptioner):
    """Simple captioner that returns deterministic placeholder captions.

    This implementation is intended for tests and local development where
    calling a real VLM would be undesirable.
    """

    prefix: str = "Caption for"

    def caption_image(self, path: Path) -> str:
        return f"{self.prefix} {path.name}"


@dataclass(slots=True)
class ChatCompletionImageCaptioner(ImageCaptioner):
    """Image captioner using the OpenAI Python SDK (OpenAI-compatible APIs).

    Parameters
    ----------
    api_key:
        API key. If not provided, ``api_key_env`` is read from the environment.
    model:
        Vision-capable model id. If not provided, ``_default_model()`` is used
        (subclasses resolve from config).
    base_url:
        OpenAI-compatible API base URL. ``None`` uses the default OpenAI API.
    api_key_env:
        Environment variable name when ``api_key`` is omitted.
    timeout:
        Request timeout in seconds.
    default_headers:
        Optional extra headers (for example OpenRouter attribution).
    """

    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key_env: str = "OPENAI_API_KEY"
    timeout: float = 30.0
    default_headers: dict[str, str] | None = None

    def _default_model(self) -> str | None:
        return None

    def _provider_label(self) -> str:
        return "Chat completion"

    def _build_client(self, api_key: str) -> OpenAI:
        kwargs: dict[str, Any] = {
            "api_key": api_key,
            "timeout": self.timeout,
        }
        if self.base_url is not None:
            kwargs["base_url"] = self.base_url
        if self.default_headers:
            kwargs["default_headers"] = self.default_headers
        return OpenAI(**kwargs)

    def caption_image(self, path: Path) -> str | None:
        api_key = self.api_key or os.environ.get(self.api_key_env)
        model = self.model or self._default_model()
        if not api_key or not model:
            # Captioning is optional; if the user didn't configure credentials/model,
            # we degrade to "no captions" rather than failing indexing.
            return None

        data_url = _image_data_url_for_path(path)
        client = self._build_client(api_key)
        label = self._provider_label()
        cap = load_prompts()

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": cap.image_caption_system},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": cap.image_caption_user},
                            {
                                "type": "image_url",
                                "image_url": {"url": data_url},
                            },
                        ],
                    },
                ],
            )
        except OpenAIError as exc:
            _log_openai_error(label, exc)
            return None

        return _string_from_completion(response)


@dataclass(slots=True)
class OpenRouterImageCaptioner(ChatCompletionImageCaptioner):
    """Image captioner backed by the OpenRouter API."""

    base_url: str = "https://openrouter.ai/api/v1"
    api_key_env: str = "OPENROUTER_API_KEY"

    def _default_model(self) -> str | None:
        return load_config().openrouter_image_caption_model

    def _provider_label(self) -> str:
        return "OpenRouter"


@dataclass(slots=True)
class OpenAIImageCaptioner(ChatCompletionImageCaptioner):
    """Image captioner backed by the OpenAI API (default endpoint)."""

    api_key_env: str = "OPENAI_API_KEY"

    def _default_model(self) -> str | None:
        return load_config().openai_image_caption_model

    def _provider_label(self) -> str:
        return "OpenAI"


__all__ = [
    "ImageCaptioner",
    "MockImageCaptioner",
    "ChatCompletionImageCaptioner",
    "OpenRouterImageCaptioner",
    "OpenAIImageCaptioner",
    "SYSTEM_PROMPT",
    "USER_PROMPT",
]
