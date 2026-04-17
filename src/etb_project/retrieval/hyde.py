"""HyDE passage generation for retrieval augmentation.

HyDE (Hypothetical Document Embeddings) works by asking an LLM to generate a short
"hypothetical" passage that *looks like* it could have come from the indexed
corpus. That passage is then embedded and used to retrieve documents that may be
relevant even when the original query is short or underspecified.

This module is intentionally scoped to the **retriever service**:
- It never answers the user; it only creates synthetic retrieval text.
- It uses the same shared chat LLM instance as other retriever-side features
  (e.g. reranking) to avoid per-request model construction overhead.
- If the LLM is unavailable, HyDE silently degrades to "no HyDE" instead of
  failing the whole retrieval request.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from etb_project.api.schemas import RetrieveRequest
from etb_project.api.settings import RetrieverAPISettings
from etb_project.models import get_chat_llm
from etb_project.prompts_config import load_prompts

logger = logging.getLogger(__name__)

HydeMode = Literal["off", "replace", "fuse"]

_hyde_llm_instance: BaseChatModel | None = None
_hyde_llm_init_attempted: bool = False


def reset_hyde_llm_cache_for_tests() -> None:
    """Clear lazy LLM singleton (tests only)."""
    global _hyde_llm_instance, _hyde_llm_init_attempted
    _hyde_llm_instance = None
    _hyde_llm_init_attempted = False


def get_retriever_chat_llm() -> BaseChatModel | None:
    """Shared lazy chat LLM for HyDE, LLM reranking, and similar retriever features."""
    return _get_lazy_chat_llm()


def _get_lazy_chat_llm() -> BaseChatModel | None:
    """Construct chat LLM once; on failure log and return None for all later calls."""
    global _hyde_llm_instance, _hyde_llm_init_attempted
    if _hyde_llm_init_attempted:
        return _hyde_llm_instance
    _hyde_llm_init_attempted = True
    try:
        _hyde_llm_instance = get_chat_llm()
    except Exception as exc:
        # Model initialization issues (missing key, misconfigured base URL, etc.)
        # should not repeatedly spam logs on every request. We log once, then
        # cache the failure as "LLM unavailable" until process restart (or tests
        # explicitly reset the cache).
        logger.error("HyDE: chat LLM initialization failed: %s", exc)
        _hyde_llm_instance = None
    return _hyde_llm_instance


def resolve_hyde_mode(
    request: RetrieveRequest, settings: RetrieverAPISettings
) -> HydeMode:
    """Resolve HyDE behavior from request override + server default.

    This keeps the API tolerant to clients sending unexpected values: anything
    outside the supported set becomes ``off`` (rather than 400'ing the request).
    """
    raw = (
        request.hyde_mode
        if request.hyde_mode is not None
        else settings.default_hyde_mode
    )
    if raw in ("off", "replace", "fuse"):
        return raw  # type: ignore[return-value]
    return "off"


def _extract_text_from_ai_message(message: AIMessage) -> str:
    """Extract plain text across common LangChain message content shapes.

    Some chat model integrations return ``message.content`` as a string while
    others return a structured list of blocks (e.g. ``[{type: "text", ...}]``).
    We normalize those variants into one trimmed string so downstream retrieval
    isn't coupled to any specific provider's response format.
    """
    content = message.content
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content).strip()


def _response_text(response: Any) -> str:
    if isinstance(response, AIMessage):
        return _extract_text_from_ai_message(response)
    return str(response).strip()


def generate_hypothetical_passage(
    query: str,
    settings: RetrieverAPISettings,
    *,
    request_id: str | None = None,
    llm: BaseChatModel | None = None,
) -> str | None:
    """Return hypothetical passage ``H`` or ``None`` on failure / empty output."""
    active = llm or _get_lazy_chat_llm()
    if active is None:
        return None

    p = load_prompts()
    user_content = p.hyde_user_template.format(query=query.strip())
    messages = [
        SystemMessage(content=p.hyde_system),
        HumanMessage(content=user_content),
    ]
    max_tok = settings.hyde_max_tokens
    try:
        try:
            # Not every BaseChatModel supports ``bind(max_tokens=...)``. When it
            # does, we prefer binding so tokens are enforced by the provider.
            bound = active.bind(max_tokens=max_tok)
            response = bound.invoke(messages)
        except (TypeError, ValueError, AttributeError):
            # Fallback path for providers that either don't implement bind() or
            # don't accept max_tokens as a bindable param.
            response = active.invoke(messages)
    except Exception as exc:
        rid = f" request_id={request_id}" if request_id else ""
        logger.warning("HyDE: LLM call failed%s: %s", rid, exc)
        return None

    text = _response_text(response)
    if not text:
        rid = f" request_id={request_id}" if request_id else ""
        logger.warning("HyDE: empty LLM output%s", rid)
        return None
    return text
