"""Merge writer subgraph output into parent orchestrator message lists."""

from __future__ import annotations

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

from etb_project.grounded_subagent.types import WriterSessionMessagesPolicy


def merge_writer_messages_for_parent(
    *,
    policy: WriterSessionMessagesPolicy,
    tool_call_id: str | None,
    final_answer: str,
    writer_messages: list[AnyMessage],
) -> list[AnyMessage]:
    """Build ``messages`` delta for the parent graph (session persistence).

    ``answer_only`` stores only the tool handshake (if any) and the final assistant
    reply. ``full`` appends the entire writer scratchpad (thoughts, tools, etc.).
    """
    prefix: list[AnyMessage] = []
    if tool_call_id is not None:
        prefix.append(
            ToolMessage(
                content="Proceeding to grounded generation.",
                tool_call_id=tool_call_id,
            )
        )
    if policy == "full":
        return prefix + list(writer_messages)
    return prefix + [AIMessage(content=final_answer)]


__all__ = ["merge_writer_messages_for_parent"]
