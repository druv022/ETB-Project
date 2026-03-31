"""Serialize LangChain messages for ``InMemorySessionStore`` (JSON-friendly dicts).

HTTP chat loads ``prior`` via ``deserialize_messages``, runs the graph, then
``serialize_messages`` on the result for the next request. Same message types are
used by the interactive CLI when it passes prior ``messages`` between stdin lines.
"""

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
            # LangChain dict rows include "type"; bare dicts may come from older clients.
            if m.get("type"):
                normalized.extend(messages_from_dict([m]))
            else:
                normalized.extend(convert_to_messages([m]))
    return messages_to_dict(normalized)
