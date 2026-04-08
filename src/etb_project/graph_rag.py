"""LangGraph-based RAG graph with an extensible state.

This is the core "reasoning + orchestration" pipeline used by:
- The Orchestrator API (primary production path: UI → Orchestrator → Retriever).
- The local CLI entrypoint for interactive demos.

The graph is intentionally minimal but structured for growth:
- ``ingest_query``: normalize input into a consistent message/state shape.
- ``orion_gate`` (optional): decide whether to ask clarifying questions before
  retrieval, or proceed with a refined query.
- ``retrieve_rag``: fetch documents from a retriever interface.
- ``generate_answer``: generate an answer grounded in retrieved context when
  available, and explicitly state when an answer is ungrounded.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from etb_project.orchestrator.orion_parse import parse_orion_response
from etb_project.prompts_config import load_prompts


class RAGState(TypedDict, total=False):
    """Shared graph state for RAG.

    Designed to be easily extendable with future nodes such as query rewriting,
    routing, SQL/tool calls, reasoning, and response post-processing.

    ``route`` is set by ``orion_gate`` when Orion pre-retrieval clarification is enabled:
    ``\"clarify\"`` (return clarification only) or ``\"retrieve\"`` (run retrieval + answer).
    """

    # Core conversation state
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    rewritten_query: str | None

    # Retrieval and tool outputs
    context_docs: list[Document]
    sql_result: dict[str, Any] | None

    # Reasoning and tooling traces
    reasoning_steps: list[str]
    tool_calls: list[dict[str, Any]]
    route: str | None

    # Final user-facing answer text
    answer: str | None


def _extract_text_from_ai_message(message: AIMessage) -> str:
    """Extract plain text from an AIMessage, handling list-based content."""
    content = getattr(message, "content", None) or getattr(message, "text", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
            else:
                text = str(block).strip()
                if text:
                    parts.append(text)
        return " ".join(parts).strip()
    return str(content).strip()


def _orion_gate_enabled(explicit: bool | None) -> bool:
    """Resolve Orion gate from explicit flag or ``ETB_ORION_CLARIFY`` (default: on)."""
    if explicit is not None:
        return explicit
    v = os.environ.get("ETB_ORION_CLARIFY", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def build_rag_graph(
    llm: BaseChatModel,
    retriever: Any,
    *,
    enable_orion_gate: bool | None = None,
) -> Any:
    """Build and compile the LangGraph StateGraph for the RAG pipeline.

    Parameters
    ----------
    llm:
        Chat model used for Orion (when enabled) and for the final grounded answer.
    retriever:
        Object with an ``invoke(query: str) -> list[Document]`` method, typically
        the FAISS retriever returned from ``vectorstore.as_retriever(...)``.
    enable_orion_gate:
        If ``True``, run Orion clarification before retrieval. If ``False``, skip
        directly to retrieval. If ``None``, use environment variable
        ``ETB_ORION_CLARIFY`` (default ``1`` = enabled).
    """
    orion_on = _orion_gate_enabled(enable_orion_gate)
    prompts = load_prompts()

    def ingest_query(state: RAGState) -> RAGState:
        """Convert raw query text into initial message state.

        Expects ``state["query"]`` to contain the raw user query string.
        """
        raw_query = state.get("query", "") or ""
        existing_messages = list(state.get("messages") or [])
        if raw_query:
            existing_messages.append(HumanMessage(content=raw_query))

        return {
            "messages": existing_messages,
            "query": raw_query,
            "rewritten_query": None,
            "context_docs": [],
            "reasoning_steps": [],
            "tool_calls": [],
            "route": None,
            "answer": None,
        }

    def orion_gate(state: RAGState) -> RAGState:
        """Orion: clarify or emit READY TO RETRIEVE with refined query."""
        messages = list(state.get("messages") or [])
        llm_messages = [SystemMessage(content=prompts.orion_system)] + messages
        response = llm.invoke(llm_messages)
        if isinstance(response, AIMessage):
            text = _extract_text_from_ai_message(response)
            ai_msg = response
        else:
            text = str(response).strip()
            ai_msg = AIMessage(content=text)

        raw_query = state.get("query", "") or ""
        parsed = parse_orion_response(text, fallback_query=raw_query)

        if not parsed.ready:
            return {
                "messages": messages + [ai_msg],
                "answer": text,
                "route": "clarify",
            }

        refined = parsed.refined_query or raw_query
        # Persist full Orion reply (including READY line) for session continuity
        display_ai = AIMessage(content=parsed.display_text)
        return {
            "messages": messages + [display_ai],
            "rewritten_query": refined,
            "route": "retrieve",
        }

    def route_after_orion(state: RAGState) -> str:
        if state.get("route") == "retrieve":
            return "retrieve"
        return "clarify"

    def retrieve_rag(state: RAGState) -> RAGState:
        """Retrieve context documents from the vector store retriever."""
        query = state.get("rewritten_query") or state.get("query") or ""
        docs: list[Document] = retriever.invoke(query) if query else []

        tool_calls = list(state.get("tool_calls") or [])
        tool_calls.append(
            {
                "tool": "vector_retriever",
                "query": query,
                "k": len(docs),
            }
        )

        return {
            "context_docs": docs,
            "tool_calls": tool_calls,
        }

    def generate_answer(state: RAGState) -> RAGState:
        """Generate a final answer from the query and retrieved context."""
        query = state.get("rewritten_query") or state.get("query") or ""
        docs = state.get("context_docs") or []

        context_text = "\n\n".join(doc.page_content for doc in docs)
        if context_text.strip():
            system_instruction = prompts.rag_answer_with_context
        else:
            system_instruction = prompts.rag_answer_no_context

        # We collapse the "question + context" into a single user message to keep
        # provider behavior consistent: some chat backends treat separate messages
        # (system+user+user) differently for safety/formatting. This form keeps
        # the state graph stable across providers.
        prompt = (
            f"{system_instruction}\n\nQuestion:\n{query}\n\nContext:\n{context_text}"
        )

        messages = list(state.get("messages") or [])
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)

        if isinstance(response, AIMessage):
            messages.append(response)
            answer_text = _extract_text_from_ai_message(response)
        else:
            answer_text = str(response).strip()

        return {
            "messages": messages,
            "answer": answer_text,
        }

    graph = StateGraph(RAGState)
    graph.add_node("ingest_query", ingest_query)
    graph.add_node("retrieve_rag", retrieve_rag)
    graph.add_node("generate_answer", generate_answer)

    graph.set_entry_point("ingest_query")
    if orion_on:
        graph.add_node("orion_gate", orion_gate)
        graph.add_edge("ingest_query", "orion_gate")
        graph.add_conditional_edges(
            "orion_gate",
            route_after_orion,
            {"clarify": END, "retrieve": "retrieve_rag"},
        )
    else:
        graph.add_edge("ingest_query", "retrieve_rag")

    graph.add_edge("retrieve_rag", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


__all__ = ["RAGState", "build_rag_graph"]
