"""LangGraph-based RAG graph with an extensible state.

This is the core "reasoning + orchestration" pipeline used by:
- The Orchestrator API (primary production path: UI → Orchestrator → Retriever).
- The local CLI entrypoint for interactive demos.

The graph is intentionally minimal but structured for growth:
- ``ingest_query``: normalize input into a consistent message/state shape.
- ``data_router`` (orchestrator): classify documents vs transactions vs both.
- ``transaction_gate``: clarify vs READY TO QUERY + JSON params for SQLite.
- ``orion_gate`` (optional): clarify vs READY TO RETRIEVE for document retrieval
  (skipped on the transaction-only path when ``enable_data_router`` is on).
- ``retrieve_rag``: fetch documents from a retriever interface.
- ``generate_answer``: produce a final answer from PDF context and/or a bounded
  transaction row sample; when neither context nor SQL is available, prompts still
  instruct the model to say so explicitly (ungrounded answer).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated, Any, Literal

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from etb_project import transaction_queries
from etb_project.orchestrator.orion_parse import parse_orion_response
from etb_project.orchestrator.transaction_parse import (
    parse_data_router_response,
    parse_transaction_gate_response,
)
from etb_project.prompts_config import load_prompts

logger = logging.getLogger(__name__)


class RAGState(TypedDict, total=False):
    """Shared graph state for RAG.

    Designed to be easily extendable with future nodes such as query rewriting,
    routing, SQL/tool calls, reasoning, and response post-processing.

    ``route`` is set by gates that participate in the clarify-vs-continue flow:
    ``\"clarify\"`` ends the graph with assistant text only; ``\"retrieve\"`` means
    Orion approved document retrieval (vector search). The transaction gate does
    not use ``route`` for \"ready\"; it uses ``pending_transaction_params`` and
    proceeds to ``fetch_transactions``.

    ``data_route`` is set only when ``enable_data_router`` is True: ``\"documents\"``
    (RAG path), ``\"transactions\"`` (SQL-only after fetch), or ``\"both\"``
    (fetch then Orion then retrieve). ``clarify_gate`` tells API clients which
    gate asked for clarification when ``route`` is ``\"clarify\"``.

    ``sql_meta_out`` is a JSON-serializable summary (counts, truncation) for
    ``ChatResponse.sql_meta``; ``sql_result`` holds the prompt-facing row sample.
    """

    # Core conversation state
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    rewritten_query: str | None

    # Retrieval, SQL, and orchestrator routing
    context_docs: list[Document]
    sql_result: dict[str, Any] | None
    sql_meta_out: dict[str, Any] | None
    pending_transaction_params: dict[str, Any] | None

    data_route: Literal["documents", "transactions", "both"] | None
    clarify_gate: Literal["documents", "transactions"] | None
    request_id: str | None

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
    enable_data_router: bool = False,
) -> Any:
    """Build and compile the LangGraph StateGraph for the RAG pipeline.

    Parameters
    ----------
    llm:
        Chat model used for routing/gates (when enabled) and for the final answer.
    retriever:
        Object with an ``invoke(query: str) -> list[Document]`` method, typically
        the FAISS retriever returned from ``vectorstore.as_retriever(...)``.
    enable_orion_gate:
        If ``True``, run Orion clarification before retrieval on the document path.
        If ``False``, skip directly to retrieval. If ``None``, use ``ETB_ORION_CLARIFY``
        (default ``1`` = enabled). Ignored for the transaction-only branch when
        ``enable_data_router`` is True (fetch goes straight to ``generate_answer``).
    enable_data_router:
        If ``True`` (orchestrator ``/v1/chat``), run ``data_router`` then branch to
        documents / transaction gate / hybrid. If ``False`` (CLI default), legacy
        ingest → Orion? → retrieve → generate without SQLite.
    """
    orion_on = _orion_gate_enabled(enable_orion_gate)
    prompts = load_prompts()

    def ingest_query(state: RAGState) -> RAGState:
        """Convert raw query text into initial message state.

        Expects ``state["query"]`` to contain the raw user query string (the
        orchestrator passes the latest user turn here; prior turns live in
        ``messages`` when resuming a session).
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
            "sql_result": None,
            "sql_meta_out": None,
            "pending_transaction_params": None,
            "data_route": None,
            "clarify_gate": None,
        }

    def data_router(state: RAGState) -> RAGState:
        """LLM classification: PDFs only, SQLite only, or hybrid (both)."""
        messages = list(state.get("messages") or [])
        llm_messages = [SystemMessage(content=prompts.data_router_system)] + messages
        response = llm.invoke(llm_messages)
        if isinstance(response, AIMessage):
            text = _extract_text_from_ai_message(response)
        else:
            text = str(response).strip()
        parsed = parse_data_router_response(text)
        rid = state.get("request_id")
        logger.info(
            "graph_node data_router request_id=%s data_route=%s",
            rid or "-",
            parsed.data_route,
        )
        return {"data_route": parsed.data_route}

    def route_after_data_router(state: RAGState) -> str:
        """Map ``data_route`` to the next node (``both`` uses the transaction arm first)."""
        dr = state.get("data_route") or "documents"
        if dr == "documents":
            return "documents"
        return "transactions"

    def transaction_gate(state: RAGState) -> RAGState:
        """Clarify missing dates/filters or emit READY TO QUERY + structured params."""
        messages = list(state.get("messages") or [])
        llm_messages = [
            SystemMessage(content=prompts.transaction_gate_system)
        ] + messages
        response = llm.invoke(llm_messages)
        if isinstance(response, AIMessage):
            text = _extract_text_from_ai_message(response)
            ai_msg = response
        else:
            text = str(response).strip()
            ai_msg = AIMessage(content=text)

        parsed = parse_transaction_gate_response(text)
        rid = state.get("request_id")
        if not parsed.ready or parsed.params is None:
            logger.info(
                "graph_node transaction_gate request_id=%s outcome=clarify",
                rid or "-",
            )
            return {
                "messages": messages + [ai_msg],
                "answer": parsed.clarify_text or text,
                "route": "clarify",
                "clarify_gate": "transactions",
            }

        display_ai = AIMessage(content=parsed.display_text)
        logger.info(
            "graph_node transaction_gate request_id=%s outcome=fetch",
            rid or "-",
        )
        return {
            "messages": messages + [display_ai],
            "pending_transaction_params": parsed.params.model_dump(),
        }

    def route_after_transaction_gate(state: RAGState) -> str:
        """End on clarify; otherwise run parameterized ``load_transactions``."""
        if state.get("route") == "clarify":
            return "clarify"
        return "fetch"

    def fetch_transactions(state: RAGState) -> RAGState:
        """Call ``transaction_queries.load_transactions``; fill ``sql_result`` / ``sql_meta_out``."""
        params = state.get("pending_transaction_params") or {}
        rid = state.get("request_id")
        tool_calls = list(state.get("tool_calls") or [])
        tool_calls.append(
            {
                "tool": "transaction_load",
                "start_date": params.get("start_date"),
                "end_date": params.get("end_date"),
                "limit": params.get("limit"),
            }
        )
        empty_meta = {
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "detail": None,
        }
        try:
            result = transaction_queries.load_transactions(
                start_date=params.get("start_date"),
                end_date=params.get("end_date"),
                filters=params.get("filters"),
                limit=int(params.get("limit") or 500),
                include_catalog=bool(params.get("include_catalog", True)),
            )
        except ValueError as exc:
            logger.warning(
                "graph_node fetch_transactions request_id=%s validation_error=%s",
                rid or "-",
                exc,
            )
            sql_result = {
                **empty_meta,
                "detail": str(exc)[:500],
            }
            return {
                "sql_result": sql_result,
                "sql_meta_out": {
                    "row_count": 0,
                    "truncated": False,
                    "detail": str(exc)[:500],
                },
                "pending_transaction_params": None,
                "tool_calls": tool_calls,
            }
        except Exception as exc:
            logger.exception(
                "graph_node fetch_transactions request_id=%s failed",
                rid or "-",
            )
            sql_result = {**empty_meta, "detail": str(exc)[:500]}
            return {
                "sql_result": sql_result,
                "sql_meta_out": {
                    "row_count": 0,
                    "truncated": False,
                    "detail": str(exc)[:500],
                },
                "pending_transaction_params": None,
                "tool_calls": tool_calls,
            }

        rows_full = transaction_queries.dataframe_to_json_rows(result.dataframe)
        max_prompt = int(os.environ.get("ETB_SQL_PROMPT_MAX_ROWS", "50"))
        prompt_rows = rows_full[:max_prompt]
        prompt_truncated = len(rows_full) > len(prompt_rows)
        sql_result = {
            "rows": prompt_rows,
            "row_count": len(rows_full),
            "truncated": result.truncated or prompt_truncated,
            "detail": result.detail,
        }
        detail_parts: list[str] = []
        if result.detail:
            detail_parts.append(result.detail)
        if prompt_truncated:
            detail_parts.append(
                f"Prompt sample limited to {max_prompt} rows ({len(rows_full)} loaded)."
            )
        sql_meta_detail = " ".join(detail_parts) if detail_parts else None

        logger.info(
            "graph_node fetch_transactions request_id=%s row_count=%s truncated=%s",
            rid or "-",
            len(rows_full),
            sql_result["truncated"],
        )
        return {
            "sql_result": sql_result,
            "sql_meta_out": {
                "row_count": len(rows_full),
                "truncated": bool(sql_result["truncated"]),
                "detail": sql_meta_detail,
            },
            "pending_transaction_params": None,
            "tool_calls": tool_calls,
        }

    def route_after_fetch(state: RAGState) -> str:
        """Transaction-only answers skip Orion and retrieval; hybrid continues to Orion."""
        if state.get("data_route") == "transactions":
            return "generate"
        return "orion"

    def orion_gate(state: RAGState) -> RAGState:
        """Orion: clarify or emit READY TO RETRIEVE with refined query (document path)."""
        if not orion_on:
            q = state.get("query", "") or ""
            return {
                "rewritten_query": q,
                "route": "retrieve",
            }
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
        rid = state.get("request_id")

        if not parsed.ready:
            logger.info(
                "graph_node orion_gate request_id=%s outcome=clarify",
                rid or "-",
            )
            return {
                "messages": messages + [ai_msg],
                "answer": text,
                "route": "clarify",
                "clarify_gate": "documents",
            }

        refined = parsed.refined_query or raw_query
        # Persist full Orion reply (including READY line) for session continuity
        display_ai = AIMessage(content=parsed.display_text)
        logger.info(
            "graph_node orion_gate request_id=%s outcome=retrieve",
            rid or "-",
        )
        return {
            "messages": messages + [display_ai],
            "rewritten_query": refined,
            "route": "retrieve",
        }

    def route_after_orion(state: RAGState) -> str:
        """``retrieve`` continues to vector search; ``clarify`` ends the turn."""
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
        rid = state.get("request_id")
        logger.info(
            "graph_node retrieve_rag request_id=%s k=%s",
            rid or "-",
            len(docs),
        )
        return {
            "context_docs": docs,
            "tool_calls": tool_calls,
        }

    def generate_answer(state: RAGState) -> RAGState:
        """Generate the final answer from PDF context and/or SQL row samples.

        Chooses one of four system prompts (docs+SQL, SQL-only, docs-only, neither)
        so the model does not mix modalities incorrectly. Rows embedded in the
        prompt are capped by ``ETB_SQL_PROMPT_MAX_ROWS`` upstream in
        ``fetch_transactions``.
        """
        query = state.get("rewritten_query") or state.get("query") or ""
        docs = state.get("context_docs") or []
        sql = state.get("sql_result")

        context_text = "\n\n".join(doc.page_content for doc in docs)
        has_docs = bool(context_text.strip())
        sql_rows = (sql or {}).get("rows") if isinstance(sql, dict) else None
        has_sql = bool(sql_rows)

        txn_block = ""
        if isinstance(sql, dict):
            txn_block = json.dumps(
                {
                    "row_count": sql.get("row_count", 0),
                    "truncated": sql.get("truncated", False),
                    "detail": sql.get("detail"),
                    "sample_rows": sql.get("rows") or [],
                },
                indent=2,
                default=str,
            )[:120000]

        if has_docs and has_sql:
            system_instruction = prompts.rag_answer_with_context_and_sql
            prompt = (
                f"{system_instruction}\n\nQuestion:\n{query}\n\n"
                f"Document_context:\n{context_text}\n\nTransaction_sample:\n{txn_block}"
            )
        elif has_sql:
            system_instruction = prompts.rag_answer_sql_only
            prompt = (
                f"{system_instruction}\n\nQuestion:\n{query}\n\n"
                f"Transaction_sample:\n{txn_block}"
            )
        elif has_docs:
            system_instruction = prompts.rag_answer_with_context
            prompt = f"{system_instruction}\n\nQuestion:\n{query}\n\nContext:\n{context_text}"
        else:
            system_instruction = prompts.rag_answer_no_context
            prompt = f"{system_instruction}\n\nQuestion:\n{query}\n\nContext:\n{context_text}"

        # Collapse question + context (+ transaction JSON) into a single user
        # message so provider backends treat the turn consistently; some APIs
        # behave differently when system vs. multiple user messages are chained.
        messages = list(state.get("messages") or [])
        messages.append(HumanMessage(content=prompt))
        response = llm.invoke(messages)

        if isinstance(response, AIMessage):
            messages.append(response)
            answer_text = _extract_text_from_ai_message(response)
        else:
            answer_text = str(response).strip()

        rid = state.get("request_id")
        logger.info(
            "graph_node generate_answer request_id=%s has_docs=%s has_sql=%s",
            rid or "-",
            has_docs,
            has_sql,
        )
        return {
            "messages": messages,
            "answer": answer_text,
        }

    graph = StateGraph(RAGState)
    graph.add_node("ingest_query", ingest_query)
    graph.add_node("retrieve_rag", retrieve_rag)
    graph.add_node("generate_answer", generate_answer)

    if not enable_data_router:
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

    graph.add_node("data_router", data_router)
    graph.add_node("transaction_gate", transaction_gate)
    graph.add_node("fetch_transactions", fetch_transactions)
    graph.add_node("orion_gate", orion_gate)

    graph.set_entry_point("ingest_query")
    graph.add_edge("ingest_query", "data_router")
    graph.add_conditional_edges(
        "data_router",
        route_after_data_router,
        {
            "documents": "orion_gate",
            "transactions": "transaction_gate",
        },
    )

    graph.add_conditional_edges(
        "transaction_gate",
        route_after_transaction_gate,
        {"clarify": END, "fetch": "fetch_transactions"},
    )
    graph.add_conditional_edges(
        "fetch_transactions",
        route_after_fetch,
        {"generate": "generate_answer", "orion": "orion_gate"},
    )

    graph.add_conditional_edges(
        "orion_gate",
        route_after_orion,
        {"clarify": END, "retrieve": "retrieve_rag"},
    )
    graph.add_edge("retrieve_rag", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


__all__ = ["RAGState", "build_rag_graph"]
