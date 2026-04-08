"""Serialize LangChain messages for ``InMemorySessionStore`` (JSON-friendly dicts)."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import (
    BaseMessage,
    convert_to_messages,
    messages_from_dict,
    messages_to_dict,
)


def deserialize_messages(
    prior: list[dict[str, Any]] | None,
) -> list[BaseMessage]:
    """Restore LangChain messages from session dicts."""
    if not prior:
        return []
    return list(messages_from_dict(prior))


def serialize_messages(messages: list[Any] | None) -> list[dict[str, Any]]:
    """Convert LangGraph/LangChain message list to storable dicts."""
    if not messages:
        return []
    normalized: list[BaseMessage] = []
    for m in messages:
        if isinstance(m, BaseMessage):
            normalized.append(m)
        elif isinstance(m, dict):
            # LangGraph may emit either:
            # - "messages_to_dict" shaped dicts (with a "type" key), or
            # - raw message-like dicts accepted by LangChain's convert helpers.
            # We normalize both so the session store always contains the stable
            # messages_to_dict() format.
            if m.get("type"):
                normalized.extend(messages_from_dict([m]))
            else:
                normalized.extend(convert_to_messages([m]))
    return messages_to_dict(normalized)
