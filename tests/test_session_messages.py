"""Round-trip tests for orchestrator session message serialization."""

from __future__ import annotations

import pytest

pytest.importorskip("langchain_core")
from langchain_core.messages import AIMessage, HumanMessage

from etb_project.orchestrator.session_messages import (
    deserialize_messages,
    serialize_messages,
)


def test_serialize_deserialize_round_trip() -> None:
    original = [
        HumanMessage(content="hello"),
        AIMessage(content="hi there"),
    ]
    data = serialize_messages(original)
    assert isinstance(data, list)
    restored = deserialize_messages(data)
    assert len(restored) == 2
    assert restored[0].content == "hello"
    assert restored[1].content == "hi there"


def test_deserialize_empty() -> None:
    assert deserialize_messages([]) == []
    assert deserialize_messages(None) == []
