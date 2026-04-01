"""LangGraph tool loop for the grounded writer subagent."""

from __future__ import annotations

import logging
import time
from typing import Any, Literal

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from etb_project.grounded_subagent.direct import run_direct_grounded_finalize
from etb_project.grounded_subagent.session_merge import merge_writer_messages_for_parent
from etb_project.grounded_subagent.state import WriterState
from etb_project.grounded_subagent.templates import (
    WRITER_FORCE_DIRECT_DISCLAIMER,
    WRITER_TOOL_RETRY_PROMPT,
    build_writer_system_prompt,
)
from etb_project.grounded_subagent.tools import WRITER_TOOLS
from etb_project.grounded_subagent.types import WriterSessionMessagesPolicy
from etb_project.orchestrator.llm_messages import (
    build_grounded_answer_human_message,
    strip_llm_tool_markup,
    truncate_documents_by_chars,
)
from etb_project.rag_document_merge import merge_documents

logger = logging.getLogger(__name__)


def _cap_chat_messages(msgs: list[AnyMessage], max_messages: int) -> list[AnyMessage]:
    if max_messages <= 0 or len(msgs) <= max_messages:
        return msgs
    return msgs[-max_messages:]


def _log_writer(
    state: WriterState,
    tool: str,
    *,
    duration_ms: float,
    writer_step: int,
    extra: str = "",
) -> None:
    logger.info(
        "writer_subagent request_id=%s session_id=%s tool=%s writer_step=%s "
        "writer_retrieve_used=%s duration_ms=%.2f %s",
        state.get("request_id"),
        state.get("session_id"),
        tool,
        writer_step,
        state.get("writer_retrieve_used"),
        duration_ms,
        extra,
    )


def _writer_force_direct_update(
    state: WriterState,
    llm: BaseChatModel,
    *,
    max_steps_eff: int,
    audit_suffix: str = "writer_force_direct",
) -> dict[str, Any]:
    base_prefix = (state.get("answer_prefix") or "").strip()
    disc = WRITER_FORCE_DIRECT_DISCLAIMER
    combined = f"{base_prefix}\n{disc}".strip() if base_prefix else disc
    prior = list(state.get("writer_tool_calls") or [])
    log_ctx = {
        "request_id": state.get("request_id"),
        "session_id": state.get("session_id"),
        "retrieve_calls_used": state.get("writer_retrieve_used"),
        "agent_steps": state.get("writer_steps"),
    }
    out = run_direct_grounded_finalize(
        messages_base=list(state.get("parent_messages") or []),
        llm=llm,
        query=state.get("query") or "",
        documents=list(state.get("working_docs") or []),
        max_context_chars=int(state.get("max_context_chars") or 48_000),
        answer_prefix=combined,
        audit_tool=audit_suffix,
        tool_call_id=None,
        prior_tool_calls=prior,
        log_context=log_ctx,
    )
    return {
        "writer_route": "done",
        "final_answer": out.get("answer"),
        "context_docs": out.get("context_docs") or [],
        "context_truncated": bool(out.get("context_truncated")),
        "writer_tool_calls": out.get("tool_calls") or prior,
    }


def build_writer_graph(
    llm: BaseChatModel,
    retriever: Any,
    *,
    max_steps: int,
    max_retrieve: int,
    max_context_chars: int,
    max_messages: int,
) -> Any:
    """Compile the writer subgraph. ``retriever`` must implement ``.invoke(query)``."""
    max_steps_eff = max(1, max_steps)
    max_retrieve_eff = max(0, max_retrieve)
    writer_llm = llm.bind_tools(WRITER_TOOLS)
    system_prompt = build_writer_system_prompt(
        max_steps=max_steps_eff, max_retrieve=max_retrieve_eff
    )

    def route_writer_start(
        state: WriterState,
    ) -> Literal["writer_force_direct", "writer_invoke"]:
        if int(state.get("writer_steps", 0)) >= max_steps_eff:
            return "writer_force_direct"
        return "writer_invoke"

    def writer_invoke(state: WriterState) -> dict[str, Any]:
        step = int(state.get("writer_steps", 0)) + 1
        raw_msgs = list(state.get("messages") or [])
        capped = _cap_chat_messages(raw_msgs, max_messages)
        messages = [SystemMessage(content=system_prompt)] + capped
        t0 = time.monotonic()
        response = writer_llm.invoke(messages)
        duration_ms = (time.monotonic() - t0) * 1000
        _log_writer(
            state,
            "writer_llm",
            duration_ms=duration_ms,
            writer_step=step,
            extra=f"step={step}",
        )
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(response))
        return {
            "messages": [response],
            "writer_steps": step,
        }

    def route_after_writer_invoke(
        state: WriterState,
    ) -> Literal["writer_execute_tools", "writer_handle_no_tools"]:
        msgs = state.get("messages") or []
        if not msgs:
            return "writer_handle_no_tools"
        last = msgs[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "writer_execute_tools"
        return "writer_handle_no_tools"

    def writer_execute_tools(state: WriterState) -> dict[str, Any]:
        msgs = list(state.get("messages") or [])
        last = msgs[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}
        audit = list(state.get("writer_tool_calls") or [])
        working = list(state.get("working_docs") or [])
        retrieve_used = int(state.get("writer_retrieve_used", 0))
        out_messages: list[AnyMessage] = []
        max_cc = int(state.get("max_context_chars") or max_context_chars)

        for tc in last.tool_calls:
            name = str(tc.get("name") or "")
            tid = str(tc.get("id") or "call")
            args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
            t0 = time.monotonic()

            if name == "submit_final_answer":
                raw = str(args.get("answer", "")).strip()
                ans = strip_llm_tool_markup(raw)
                if not ans:
                    out_messages.append(
                        ToolMessage(
                            content="Answer text must be non-empty. Call submit_final_answer again.",
                            tool_call_id=tid,
                        )
                    )
                    _log_writer(
                        state,
                        "writer_submit_final_answer",
                        duration_ms=0,
                        writer_step=int(state.get("writer_steps", 0)),
                        extra="blocked=empty",
                    )
                    continue
                docs_trunc, trunc = truncate_documents_by_chars(working, max_cc)
                audit.append(
                    {
                        "tool": "writer_submit_final_answer",
                        "query": state.get("query") or "",
                        "k": len(docs_trunc),
                    }
                )
                out_messages.append(
                    ToolMessage(content="Final answer recorded.", tool_call_id=tid)
                )
                _log_writer(
                    state,
                    "writer_submit_final_answer",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    writer_step=int(state.get("writer_steps", 0)),
                    extra="",
                )
                return {
                    "messages": out_messages,
                    "writer_route": "done",
                    "final_answer": ans,
                    "context_docs": docs_trunc,
                    "context_truncated": trunc,
                    "writer_tool_calls": audit,
                    "working_docs": working,
                }

            if name == "retrieve_more":
                q = str(args.get("query", "")).strip()
                if retrieve_used >= max_retrieve_eff:
                    out_messages.append(
                        ToolMessage(
                            content=(
                                "Max writer retrieve calls reached; use submit_final_answer "
                                "with the best answer from current context."
                            ),
                            tool_call_id=tid,
                        )
                    )
                    _log_writer(
                        state,
                        "writer_retrieve_more",
                        duration_ms=0,
                        writer_step=int(state.get("writer_steps", 0)),
                        extra="blocked=max",
                    )
                    continue
                new_docs: list[Document] = []
                if q:
                    new_docs = retriever.invoke(q)
                merged = merge_documents(working, new_docs)
                retrieve_used += 1
                working = merged
                summary = (
                    f"Retrieved {len(new_docs)} chunk(s); "
                    f"{len(merged)} total after merge/dedupe."
                )
                out_messages.append(ToolMessage(content=summary, tool_call_id=tid))
                audit.append(
                    {"tool": "writer_retrieve_more", "query": q, "k": len(new_docs)}
                )
                _log_writer(
                    state,
                    "writer_retrieve_more",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    writer_step=int(state.get("writer_steps", 0)),
                    extra=f"k={len(new_docs)}",
                )
                continue

            if name == "record_thought":
                out_messages.append(
                    ToolMessage(content="Thought recorded.", tool_call_id=tid)
                )
                audit.append(
                    {
                        "tool": "writer_record_thought",
                        "query": str(args.get("thought", ""))[:200],
                        "k": 0,
                    }
                )
                _log_writer(
                    state,
                    "writer_record_thought",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    writer_step=int(state.get("writer_steps", 0)),
                    extra="",
                )
                continue

            if name == "submit_plan":
                out_messages.append(
                    ToolMessage(content="Plan recorded.", tool_call_id=tid)
                )
                audit.append(
                    {
                        "tool": "writer_submit_plan",
                        "query": str(args.get("steps", ""))[:500],
                        "k": 0,
                    }
                )
                _log_writer(
                    state,
                    "writer_submit_plan",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    writer_step=int(state.get("writer_steps", 0)),
                    extra="",
                )
                continue

            if name == "draft_code_hook":
                out_messages.append(
                    ToolMessage(
                        content=(
                            "Code execution is not enabled in this deployment. "
                            "Proceed with submit_final_answer using reasoning only."
                        ),
                        tool_call_id=tid,
                    )
                )
                audit.append({"tool": "writer_draft_code_hook", "query": "", "k": 0})
                _log_writer(
                    state,
                    "writer_draft_code_hook",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    writer_step=int(state.get("writer_steps", 0)),
                    extra="",
                )
                continue

            out_messages.append(
                ToolMessage(content=f"Unknown writer tool: {name}", tool_call_id=tid)
            )

        return {
            "messages": out_messages,
            "working_docs": working,
            "writer_retrieve_used": retrieve_used,
            "writer_tool_calls": audit,
        }

    def writer_handle_no_tools(state: WriterState) -> dict[str, Any]:
        if not state.get("no_tool_retry_used"):
            return {
                "messages": [SystemMessage(content=WRITER_TOOL_RETRY_PROMPT)],
                "no_tool_retry_used": True,
            }
        return _writer_force_direct_update(
            state,
            llm,
            max_steps_eff=max_steps_eff,
            audit_suffix="writer_no_tool_fallback",
        )

    def route_after_writer_execute(
        state: WriterState,
    ) -> Literal["writer_start", "end"]:
        if state.get("writer_route") == "done":
            return "end"
        return "writer_start"

    def route_after_writer_no_tools(
        state: WriterState,
    ) -> Literal["writer_start", "end"]:
        if state.get("writer_route") == "done":
            return "end"
        return "writer_start"

    def writer_force_direct(state: WriterState) -> dict[str, Any]:
        return _writer_force_direct_update(
            state,
            llm,
            max_steps_eff=max_steps_eff,
            audit_suffix="writer_step_limit",
        )

    graph = StateGraph(WriterState)
    graph.add_node("writer_start", lambda _s: {})
    graph.add_node("writer_invoke", writer_invoke)
    graph.add_node("writer_execute_tools", writer_execute_tools)
    graph.add_node("writer_handle_no_tools", writer_handle_no_tools)
    graph.add_node("writer_force_direct", writer_force_direct)

    graph.set_entry_point("writer_start")
    graph.add_conditional_edges(
        "writer_start",
        route_writer_start,
        {
            "writer_force_direct": "writer_force_direct",
            "writer_invoke": "writer_invoke",
        },
    )
    graph.add_conditional_edges(
        "writer_invoke",
        route_after_writer_invoke,
        {
            "writer_execute_tools": "writer_execute_tools",
            "writer_handle_no_tools": "writer_handle_no_tools",
        },
    )
    graph.add_conditional_edges(
        "writer_execute_tools",
        route_after_writer_execute,
        {"writer_start": "writer_start", "end": END},
    )
    graph.add_conditional_edges(
        "writer_handle_no_tools",
        route_after_writer_no_tools,
        {"writer_start": "writer_start", "end": END},
    )
    graph.add_edge("writer_force_direct", END)

    return graph.compile()


def run_writer_subgraph_for_orchestrator(
    *,
    parent_messages: list[AnyMessage],
    query: str,
    accumulated_docs: list[Document],
    llm: BaseChatModel,
    retriever: Any,
    max_context_chars: int,
    writer_max_steps: int,
    writer_max_retrieve: int,
    writer_max_messages: int,
    answer_prefix: str,
    tool_call_id: str | None,
    request_id: str | None,
    session_id: str | None,
    orchestrator_tool_calls: list[dict[str, Any]],
    session_policy: WriterSessionMessagesPolicy,
) -> dict[str, Any]:
    """Run the writer subgraph and return an orchestrator state delta (like direct finalize)."""
    docs_trunc, trunc = truncate_documents_by_chars(accumulated_docs, max_context_chars)
    human = build_grounded_answer_human_message(
        question=query,
        documents=docs_trunc,
        context_truncated=trunc,
    )
    graph = build_writer_graph(
        llm,
        retriever,
        max_steps=writer_max_steps,
        max_retrieve=writer_max_retrieve,
        max_context_chars=max_context_chars,
        max_messages=writer_max_messages,
    )
    initial: WriterState = {
        "messages": [human],
        "parent_messages": list(parent_messages),
        "query": query,
        "working_docs": list(accumulated_docs),
        "context_truncated_initial": trunc,
        "writer_steps": 0,
        "writer_retrieve_used": 0,
        "writer_route": None,
        "final_answer": None,
        "context_docs": [],
        "context_truncated": False,
        "writer_tool_calls": [],
        "no_tool_retry_used": False,
        "request_id": request_id,
        "session_id": session_id,
        "answer_prefix": answer_prefix,
        "max_context_chars": max_context_chars,
    }
    result = graph.invoke(initial)
    fa = strip_llm_tool_markup((result.get("final_answer") or "").strip())
    writer_tc = list(result.get("writer_tool_calls") or [])
    ctx_docs = list(result.get("context_docs") or [])
    ctx_trunc = bool(result.get("context_truncated"))
    log_ctx = {
        "request_id": request_id,
        "session_id": session_id,
        "retrieve_calls_used": None,
        "agent_steps": None,
    }
    if not fa:
        prior_fb = (
            list(orchestrator_tool_calls)
            + [{"tool": "finalize_answer", "query": query, "k": len(accumulated_docs)}]
            + writer_tc
        )
        fb = run_direct_grounded_finalize(
            messages_base=list(parent_messages),
            llm=llm,
            query=query,
            documents=list(accumulated_docs),
            max_context_chars=max_context_chars,
            answer_prefix=answer_prefix,
            audit_tool="writer_empty_answer_fallback",
            tool_call_id=None,
            prior_tool_calls=prior_fb,
            log_context=log_ctx,
        )
        fa = strip_llm_tool_markup((fb.get("answer") or "").strip())
        ctx_docs = list(fb.get("context_docs") or ctx_docs)
        ctx_trunc = bool(fb.get("context_truncated"))
        merged_tc = list(fb.get("tool_calls") or prior_fb)
        msg_delta = merge_writer_messages_for_parent(
            policy=session_policy,
            tool_call_id=tool_call_id,
            final_answer=fa,
            writer_messages=list(result.get("messages") or []),
        )
    else:
        ap = (answer_prefix or "").strip()
        if ap:
            fa = f"{ap}\n{fa}"
        msg_delta = merge_writer_messages_for_parent(
            policy=session_policy,
            tool_call_id=tool_call_id,
            final_answer=fa,
            writer_messages=list(result.get("messages") or []),
        )
        merged_tc = list(orchestrator_tool_calls) + [
            {"tool": "finalize_answer", "query": query, "k": len(accumulated_docs)}
        ]
        merged_tc.extend(writer_tc)
    return {
        "messages": msg_delta,
        "answer": fa,
        "route": "answer",
        "context_docs": ctx_docs,
        "context_truncated": ctx_trunc,
        "tool_calls": merged_tc,
    }


__all__ = ["build_writer_graph", "run_writer_subgraph_for_orchestrator"]
