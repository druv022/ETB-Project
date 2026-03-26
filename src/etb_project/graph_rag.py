"""LangGraph-based RAG graph with an extensible state."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class RAGState(TypedDict, total=False):
    """Shared graph state for RAG.

    Designed to be easily extendable with future nodes such as query rewriting,
    routing, SQL/tool calls, reasoning, and response post-processing.
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


def build_rag_graph(
    llm: BaseChatModel,
    retriever: Any,
) -> Any:
    """Build and compile the LangGraph StateGraph for the RAG pipeline.

    Parameters
    ----------
    llm:
        Chat model used to generate the final answer.
    retriever:
        Object with an ``invoke(query: str) -> list[Document]`` method, typically
        the FAISS retriever returned from ``vectorstore.as_retriever(...)``.
    """

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
            # Initialize commonly used fields to predictable defaults
            "rewritten_query": state.get("rewritten_query"),
            "context_docs": state.get("context_docs") or [],
            "reasoning_steps": state.get("reasoning_steps") or [],
            "tool_calls": state.get("tool_calls") or [],
            "route": state.get("route"),
            "answer": state.get("answer"),
        }

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
            system_instruction = (
                "Use the following context to answer the user's question as accurately "
                "as possible. If the context is insufficient, you may answer from your "
                "general knowledge but indicate that the answer is not fully grounded "
                "in the provided document."
            )
        else:
            system_instruction = (
                "No relevant context could be retrieved from the document. Answer the "
                "user's question as best as you can from your general knowledge, and "
                "state clearly that the answer is not grounded in the document."
            )

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
    graph.add_edge("ingest_query", "retrieve_rag")
    graph.add_edge("retrieve_rag", "generate_answer")
    graph.add_edge("generate_answer", END)

    return graph.compile()


__all__ = ["RAGState", "build_rag_graph"]
