"""Types for grounded subagent session policy."""

from __future__ import annotations

from typing import Literal

WriterSessionMessagesPolicy = Literal["answer_only", "full"]

__all__ = ["WriterSessionMessagesPolicy"]
