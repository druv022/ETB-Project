"""Single-shot grounded generation (original finalize path)."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from typing import Any

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, ToolMessage

from etb_project.orchestrator.llm_messages import (
    build_grounded_answer_human_message,
    extract_text_from_ai_message,
    strip_llm_tool_markup,
    truncate_documents_by_chars,
)

logger = logging.getLogger(__name__)


def _append_audit(
    prior: list[dict[str, Any]], entry: dict[str, Any]
) -> list[dict[str, Any]]:
    out = list(prior)
    out.append(entry)
    return out


def run_direct_grounded_finalize(
    *,
    messages_base: list[AnyMessage],
    llm: BaseChatModel,
    query: str,
    documents: list[Document],
    max_context_chars: int,
    answer_prefix: str,
    audit_tool: str,
    tool_call_id: str | None,
    prior_tool_calls: list[dict[str, Any]],
    log_context: Mapping[str, Any],
) -> dict[str, Any]:
    """Run one non-tool LLM call with delimiter-wrapped context.

    ``log_context`` should include optional keys: request_id, session_id,
    retrieve_calls_used, agent_steps (for structured logging parity).
    Returns a dict suitable for merging into ``AgentOrchestratorState``.
    """
    docs_trunc, truncated = truncate_documents_by_chars(documents, max_context_chars)
    human = build_grounded_answer_human_message(
        question=query,
        documents=docs_trunc,
        context_truncated=truncated,
    )
    base = list(messages_base)
    prefix: list[AnyMessage] = []
    if tool_call_id is not None:
        prefix.append(
            ToolMessage(
                content="Proceeding to grounded generation.",
                tool_call_id=tool_call_id,
            )
        )
    msgs_for_invoke = base + prefix + [human]
    t0 = time.monotonic()
    response = llm.invoke(msgs_for_invoke)
    duration_ms = (time.monotonic() - t0) * 1000
    logger.info(
        "agent_tool request_id=%s session_id=%s tool=%s retrieve_calls_used=%s "
        "agent_steps=%s duration_ms=%.2f %s",
        log_context.get("request_id"),
        log_context.get("session_id"),
        audit_tool,
        log_context.get("retrieve_calls_used"),
        log_context.get("agent_steps"),
        duration_ms,
        "invoke=generate",
    )
    delta: list[AnyMessage] = prefix + [human]
    if isinstance(response, AIMessage):
        delta.append(response)
        answer_text = extract_text_from_ai_message(response)
    else:
        answer_text = strip_llm_tool_markup(str(response).strip())
    if answer_prefix:
        answer_text = f"{answer_prefix}\n{answer_text}"
    return {
        "messages": delta,
        "answer": answer_text,
        "route": "answer",
        "context_docs": docs_trunc,
        "context_truncated": truncated,
        "tool_calls": _append_audit(
            prior_tool_calls,
            {"tool": audit_tool, "query": query, "k": len(docs_trunc)},
        ),
    }


__all__ = ["run_direct_grounded_finalize"]
