"""LangGraph agent orchestrator: tool-calling RAG with retrieve / clarify / finalize.

Graph shape: ``ingest`` (append user query, reset per-turn doc state) → ``before_agent``
(routing) → ``invoke_agent`` (LLM with bound tools) → ``execute_tools`` or
``handle_no_tools`` → loop or ``END``. Real retrieval uses ``retriever.invoke(query)``;
``@tool`` bodies below are placeholders for LangChain tool schemas only.
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any, Literal

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import tool
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from etb_project.orchestrator.agent_system_prompt import (
    AGENT_SYSTEM_PROMPT,
    STEP_LIMIT_DISCLAIMER,
    TOOL_RETRY_PROMPT,
)
from etb_project.orchestrator.llm_messages import (
    build_grounded_answer_human_message,
    extract_text_from_ai_message,
    truncate_documents_by_chars,
)

logger = logging.getLogger(__name__)


def _doc_dedupe_key(doc: Document) -> str:
    """Stable key for merge/dedupe across repeated retrieve calls."""
    md = doc.metadata or {}
    for k in ("chunk_id", "id", "source"):
        if k in md and md[k] is not None:
            return f"{k}:{md[k]}"
    text = (doc.page_content or "")[:200]
    return f"hash:{hash(text)}"


def _merge_documents(
    existing: list[Document], new_docs: list[Document]
) -> list[Document]:
    keys = {_doc_dedupe_key(d) for d in existing}
    out = list(existing)
    for d in new_docs:
        k = _doc_dedupe_key(d)
        if k not in keys:
            keys.add(k)
            out.append(d)
    return out


# Schemas for ``llm.bind_tools``; execution is implemented in ``execute_tools``.
@tool
def retrieve(query: str) -> str:
    """Search the internal document index for relevant passages."""
    return ""


@tool
def ask_clarify(message: str) -> str:
    """Ask the user one clarifying question and end this turn."""
    return ""


@tool
def finalize_answer() -> str:
    """Produce the final grounded answer using retrieved context."""
    return ""


AGENT_TOOLS = [retrieve, ask_clarify, finalize_answer]


class AgentOrchestratorState(TypedDict, total=False):
    """State for the agentic orchestrator graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    accumulated_docs: list[Document]
    context_docs: list[
        Document
    ]  # Documents fed into last grounded generation (may be truncated).
    route: (
        str | None
    )  # "clarify" | "answer" when ending early; else None until finalize.
    answer: str | None
    retrieve_calls_used: int
    clarify_used: bool
    agent_steps: int  # LLM invocations in the tool loop (distinct from retrieve count).
    no_tool_retry_used: bool
    context_truncated: bool
    tool_calls: list[dict[str, Any]]
    request_id: (
        str | None
    )  # For structured logs (HTTP request id or CLI per-line uuid).
    session_id: str | None  # For structured logs and multi-turn correlation.


def _append_tool_audit(
    state: AgentOrchestratorState,
    entry: dict[str, Any],
) -> list[dict[str, Any]]:
    tc = list(state.get("tool_calls") or [])
    tc.append(entry)
    return tc


def _log_tool(
    state: AgentOrchestratorState,
    tool: str,
    *,
    duration_ms: float,
    extra: str = "",
) -> None:
    logger.info(
        "agent_tool request_id=%s session_id=%s tool=%s retrieve_calls_used=%s "
        "agent_steps=%s duration_ms=%.2f %s",
        state.get("request_id"),
        state.get("session_id"),
        tool,
        state.get("retrieve_calls_used"),
        state.get("agent_steps"),
        duration_ms,
        extra,
    )


def _grounded_generation_update(
    *,
    state: AgentOrchestratorState,
    llm: BaseChatModel,
    query: str,
    documents: list[Document],
    max_context_chars: int,
    answer_prefix: str,
    audit_tool: str,
    tool_call_id: str | None = None,
) -> AgentOrchestratorState:
    """Run a non-tool LLM call with delimiter-wrapped context (finalize path).

    When ``tool_call_id`` is set, prepends a ToolMessage so the assistant turn follows
    OpenAI-style tool-result ordering after ``finalize_answer``.
    """
    docs_trunc, truncated = truncate_documents_by_chars(documents, max_context_chars)
    human = build_grounded_answer_human_message(
        question=query,
        documents=docs_trunc,
        context_truncated=truncated,
    )
    base = list(state.get("messages") or [])
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
    _log_tool(state, audit_tool, duration_ms=duration_ms, extra="invoke=generate")
    delta: list[AnyMessage] = prefix + [human]
    if isinstance(response, AIMessage):
        delta.append(response)
        answer_text = extract_text_from_ai_message(response)
    else:
        answer_text = str(response).strip()
    if answer_prefix:
        answer_text = f"{answer_prefix}\n{answer_text}"
    out: AgentOrchestratorState = {
        "messages": delta,
        "answer": answer_text,
        "route": "answer",
        "context_docs": docs_trunc,
        "context_truncated": truncated,
        "tool_calls": _append_tool_audit(
            state,
            {"tool": audit_tool, "query": query, "k": len(docs_trunc)},
        ),
    }
    return out


def build_agent_orchestrator_graph(
    llm: BaseChatModel,
    retriever: Any,
    *,
    max_retrieve: int,
    max_steps: int,
    max_context_chars: int,
) -> Any:
    """Compile the agent graph. ``retriever`` must implement ``.invoke(query) -> list[Document]``."""
    max_steps_eff = max(1, max_steps)

    llm_tools = llm.bind_tools(AGENT_TOOLS)

    def ingest_node(state: AgentOrchestratorState) -> AgentOrchestratorState:
        raw = state.get("query", "") or ""
        # Session/history from the caller, then this turn's user text as a new HumanMessage.
        prior = list(state.get("messages") or [])
        msgs = list(prior)
        if raw:
            msgs.append(HumanMessage(content=raw))
        return {
            "messages": msgs,
            "query": raw,
            "accumulated_docs": [],
            "context_docs": [],
            "retrieve_calls_used": 0,
            "clarify_used": False,
            "agent_steps": 0,
            "no_tool_retry_used": False,
            "route": None,
            "answer": None,
            "context_truncated": False,
            "tool_calls": [],
            "request_id": state.get("request_id"),
            "session_id": state.get("session_id"),
        }

    def route_before_invoke(
        state: AgentOrchestratorState,
    ) -> Literal["force_finalize", "invoke_agent"]:
        # Step count is incremented inside ``invoke_agent``; compare *before* next LLM call.
        if state.get("agent_steps", 0) >= max_steps_eff:
            return "force_finalize"
        return "invoke_agent"

    def invoke_agent(state: AgentOrchestratorState) -> AgentOrchestratorState:
        step = int(state.get("agent_steps", 0)) + 1
        # System prompt is not persisted in ``messages``; it is prepended each LLM call only.
        messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT)] + list(
            state.get("messages") or []
        )
        t0 = time.monotonic()
        response = llm_tools.invoke(messages)
        duration_ms = (time.monotonic() - t0) * 1000
        _log_tool(state, "agent_llm", duration_ms=duration_ms, extra=f"step={step}")
        if not isinstance(response, AIMessage):
            response = AIMessage(content=str(response))
        return {
            "messages": [response],
            "agent_steps": step,
        }

    def route_after_invoke(
        state: AgentOrchestratorState,
    ) -> Literal["execute_tools", "handle_no_tools"]:
        msgs = state.get("messages") or []
        if not msgs:
            return "handle_no_tools"
        last = msgs[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "execute_tools"
        return "handle_no_tools"

    def execute_tools(state: AgentOrchestratorState) -> AgentOrchestratorState:
        # Implements retrieve / ask_clarify / finalize_answer; unknown tools get ToolMessage errors.
        msgs = list(state.get("messages") or [])
        last = msgs[-1]
        if not isinstance(last, AIMessage) or not last.tool_calls:
            return {}
        query_text = state.get("query", "") or ""
        accumulated = list(state.get("accumulated_docs") or [])
        retrieve_used = int(state.get("retrieve_calls_used", 0))
        clarify_used = bool(state.get("clarify_used", False))
        out_messages: list[AnyMessage] = []
        audit = list(state.get("tool_calls") or [])

        for tc in last.tool_calls:
            name = str(tc.get("name") or "")
            tid = str(tc.get("id") or "call")
            args = tc.get("args") if isinstance(tc.get("args"), dict) else {}
            t0 = time.monotonic()

            if name == "ask_clarify":
                msg_text = str(args.get("message", "")).strip()
                if clarify_used:
                    out_messages.append(
                        ToolMessage(
                            content=(
                                "Clarify already used this turn; use retrieve or finalize_answer."
                            ),
                            tool_call_id=tid,
                        )
                    )
                    _log_tool(
                        state, "ask_clarify", duration_ms=0, extra="blocked=duplicate"
                    )
                    continue
                clarify_used = True
                body = msg_text or "Could you clarify your request?"
                audit.append({"tool": "ask_clarify", "query": query_text, "k": 0})
                tm = ToolMessage(
                    content="Clarifying question recorded.", tool_call_id=tid
                )
                _log_tool(
                    state,
                    "ask_clarify",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    extra="",
                )
                return {
                    "messages": [tm, AIMessage(content=body)],
                    "route": "clarify",
                    "answer": body,
                    "clarify_used": True,
                    "tool_calls": audit,
                }

            if name == "finalize_answer":
                gen = _grounded_generation_update(
                    state=state,
                    llm=llm,
                    query=query_text,
                    documents=accumulated,
                    max_context_chars=max_context_chars,
                    answer_prefix="",
                    audit_tool="finalize_answer",
                    tool_call_id=tid,
                )
                _log_tool(state, "finalize_answer", duration_ms=0, extra="")
                return gen

            if name == "retrieve":
                q = str(args.get("query", "")).strip()
                if retrieve_used >= max_retrieve:
                    out_messages.append(
                        ToolMessage(
                            content=(
                                "Max retrieve calls reached for this turn; "
                                "call finalize_answer or ask_clarify."
                            ),
                            tool_call_id=tid,
                        )
                    )
                    _log_tool(state, "retrieve", duration_ms=0, extra="blocked=max")
                    continue
                new_docs: list[Document] = []
                if q:
                    new_docs = retriever.invoke(q)
                merged = _merge_documents(accumulated, new_docs)
                retrieve_used += 1
                accumulated = merged
                summary = (
                    f"Retrieved {len(new_docs)} chunk(s); "
                    f"{len(merged)} total after merge/dedupe."
                )
                out_messages.append(ToolMessage(content=summary, tool_call_id=tid))
                audit.append({"tool": "retrieve", "query": q, "k": len(new_docs)})
                _log_tool(
                    state,
                    "retrieve",
                    duration_ms=(time.monotonic() - t0) * 1000,
                    extra=f"k={len(new_docs)}",
                )
                continue

            out_messages.append(
                ToolMessage(content=f"Unknown tool: {name}", tool_call_id=tid)
            )

        return {
            "messages": out_messages,
            "retrieve_calls_used": retrieve_used,
            "accumulated_docs": accumulated,
            "clarify_used": clarify_used,
            "tool_calls": audit,
        }

    def handle_no_tools(state: AgentOrchestratorState) -> AgentOrchestratorState:
        # Model replied without tool_calls: nudge once, then grounded fallback with whatever docs exist.
        if not state.get("no_tool_retry_used"):
            logger.info(
                "agent_tool_fallback request_id=%s session_id=%s phase=retry_prompt",
                state.get("request_id"),
                state.get("session_id"),
            )
            return {
                "messages": [SystemMessage(content=TOOL_RETRY_PROMPT)],
                "no_tool_retry_used": True,
            }
        logger.warning(
            "agent_tool_fallback request_id=%s session_id=%s phase=force_finalize",
            state.get("request_id"),
            state.get("session_id"),
        )
        return _grounded_generation_update(
            state=state,
            llm=llm,
            query=state.get("query", "") or "",
            documents=list(state.get("accumulated_docs") or []),
            max_context_chars=max_context_chars,
            answer_prefix="",
            audit_tool="finalize_fallback",
            tool_call_id=None,
        )

    def route_after_handle_no_tools(
        state: AgentOrchestratorState,
    ) -> Literal["before_agent", "end"]:
        if state.get("route") == "answer":
            return "end"
        return "before_agent"

    def force_finalize_node(state: AgentOrchestratorState) -> AgentOrchestratorState:
        # Invoked when ``agent_steps`` hits ``max_steps``; still grounded on ``accumulated_docs``.
        return _grounded_generation_update(
            state=state,
            llm=llm,
            query=state.get("query", "") or "",
            documents=list(state.get("accumulated_docs") or []),
            max_context_chars=max_context_chars,
            answer_prefix=STEP_LIMIT_DISCLAIMER,
            audit_tool="force_finalize",
            tool_call_id=None,
        )

    def route_after_tools(
        state: AgentOrchestratorState,
    ) -> Literal["before_agent", "end"]:
        r = state.get("route")
        if r in ("clarify", "answer"):
            return "end"
        return "before_agent"

    graph = StateGraph(AgentOrchestratorState)
    graph.add_node("ingest", ingest_node)
    # No-op node so ``before_agent`` can host conditional_edges from a single id (LangGraph pattern).
    graph.add_node("before_agent", lambda _s: {})
    graph.add_node("invoke_agent", invoke_agent)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("handle_no_tools", handle_no_tools)
    graph.add_node("force_finalize", force_finalize_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "before_agent")
    graph.add_conditional_edges(
        "before_agent",
        route_before_invoke,
        {"force_finalize": "force_finalize", "invoke_agent": "invoke_agent"},
    )
    graph.add_conditional_edges(
        "invoke_agent",
        route_after_invoke,
        {"execute_tools": "execute_tools", "handle_no_tools": "handle_no_tools"},
    )
    graph.add_conditional_edges(
        "handle_no_tools",
        route_after_handle_no_tools,
        {"before_agent": "before_agent", "end": END},
    )
    graph.add_conditional_edges(
        "execute_tools",
        route_after_tools,
        {"before_agent": "before_agent", "end": END},
    )
    graph.add_edge("force_finalize", END)

    return graph.compile()


__all__ = ["AgentOrchestratorState", "build_agent_orchestrator_graph"]
