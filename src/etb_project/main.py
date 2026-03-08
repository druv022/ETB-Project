"""Main entry point for ETB-project."""

import logging
from pathlib import Path
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.agents.middleware.types import Runtime
from langchain_core.messages import AIMessage, HumanMessage

from etb_project.config import load_config
from etb_project.models import get_ollama_llm as get_llm
from etb_project.retrieval import load_pdf, process_documents

# Configure logging (level applied after config load in main())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class State(AgentState):
    context: list[str]


class RetrieveDocumentsMiddleware(AgentMiddleware[State]):
    state_schema = State

    def before_model(
        self, state: State, runtime: Runtime[None]
    ) -> dict[str, Any] | None:
        messages = state.get("messages") or []
        if messages:
            last_message = messages[-1]
            query = getattr(last_message, "content", None) or getattr(
                last_message, "text", ""
            )
        else:
            logger.warning(
                "No messages in state; full state keys: %s", list(state.keys())
            )
            return None

        if not isinstance(query, str):
            query = str(query) if query else ""

        retrieved_docs = vectorstore.similarity_search(query)

        docs_content = "\n\n".join([doc.page_content for doc in retrieved_docs])
        context_strings = [doc.page_content for doc in retrieved_docs]

        augmented_message_content = (
            f"Question: {query}\n\n"
            "Use the following context to answer the query:\n"
            f"{docs_content}"
        )

        if messages:
            updated = messages[-1].model_copy(
                update={"content": augmented_message_content}
            )
            new_messages = [updated]
        else:
            new_messages = [HumanMessage(content=augmented_message_content)]

        return {
            "messages": new_messages,
            "context": context_strings,
        }


def _get_agent_reply(state: dict[str, Any]) -> str:
    """Extract the agent's final reply from invoke() state."""
    out = state.get("output")
    if isinstance(out, str) and out.strip():
        return out.strip()
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = getattr(msg, "content", None) or getattr(msg, "text", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = [
                    block.get("text", block) if isinstance(block, dict) else str(block)
                    for block in content
                ]
                text = " ".join(p for p in parts if isinstance(p, str) and p.strip())
                if text:
                    return text.strip()
    return ""


if __name__ == "__main__":
    """Load config, build retriever from PDF, run query or interactive loop."""
    config = load_config()
    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))
    logger.info("Starting ETB-project")

    pdf_path = config.pdf
    if not pdf_path or not Path(pdf_path).exists():
        logger.error(
            "Set a valid 'pdf' path in src/config/settings.yaml or ETB_CONFIG."
        )
        raise SystemExit(1)

    logger.info("Loading PDF and building vector store...")
    docs = load_pdf(pdf_path)
    vectorstore = process_documents(docs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": config.retriever_k})
    logger.info("Application started successfully")

    if config.query.strip():
        results = retriever.invoke(config.query)
        for i, doc in enumerate(results, 1):
            text = doc.page_content
            snippet = text[:200] + "..." if len(text) > 200 else text
            logger.info("Result %d: %s", i, snippet)
        exit(0)

    # Interactive query loop
    logger.info("Enter a query (empty line to exit).")
    agent = create_agent(
        model=get_llm(),
        tools=[],
        middleware=[RetrieveDocumentsMiddleware()],
    )
    while True:
        try:
            line = input("Query: ").strip()
        except EOFError:
            break
        if not line:
            exit(0)

        result = agent.invoke({"messages": [HumanMessage(content=line)]})
        reply = _get_agent_reply(result)
        if reply:
            print(reply)
        else:
            logger.warning(
                "No agent reply in result; full state keys: %s", list(result.keys())
            )
