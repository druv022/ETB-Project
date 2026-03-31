"""Parse Orion model output for READY TO RETRIEVE vs clarification."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Flexible whitespace after READY TO RETRIEVE
_READY_PATTERN = re.compile(
    r"READY\s+TO\s+RETRIEVE\s*:",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class OrionParseResult:
    """Result of parsing a single Orion assistant turn."""

    ready: bool
    refined_query: str | None
    display_text: str


def parse_orion_response(text: str, *, fallback_query: str = "") -> OrionParseResult:
    """Detect READY TO RETRIEVE and extract the refined query.

    Parameters
    ----------
    text:
        Full assistant message text.
    fallback_query:
        If the marker is present but extraction yields empty, use this (e.g. raw user query).
    """
    stripped = (text or "").strip()
    if not stripped:
        return OrionParseResult(False, None, "")

    m = _READY_PATTERN.search(stripped)
    if not m:
        return OrionParseResult(False, None, stripped)

    after = stripped[m.end() :].strip()
    # Prefer first line / sentence fragment as the refined query
    first_line = after.split("\n", 1)[0].strip()
    refined = first_line or after
    if not refined and fallback_query.strip():
        refined = fallback_query.strip()

    if refined:
        return OrionParseResult(True, refined, stripped)
    return OrionParseResult(False, None, stripped)


__all__ = ["OrionParseResult", "parse_orion_response"]
