"""CLI entry point for ETB-project.

This module provides a minimal local developer experience:
- Load configuration from YAML / env.
- Choose a retrieval mode:
  - ``local``: load persisted vector indices from disk (FAISS) and query them.
  - ``remote``: call the standalone Retriever HTTP API via ``RemoteRetriever``.
- Either run a single query (when ``config.query`` is set) or an interactive loop
  backed by the LangGraph RAG pipeline.

Design notes (why it is structured this way):
- The retriever can be run as a separate service (Docker compose) or in-process.
  This CLI supports both to make debugging and CI tests simpler.
- The CLI disables Orion clarification by default in the interactive loop to
  keep the terminal UX deterministic; the orchestrator enables it by default.
"""

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from etb_project.config import load_config
from etb_project.graph_rag import build_rag_graph
from etb_project.models import get_ollama_embedding_model as get_embeddings
from etb_project.models import get_ollama_llm as get_llm
from etb_project.retrieval import DualRetriever, RemoteRetriever
from etb_project.vectorstore.faiss_backend import FaissDualVectorStoreBackend

# Configure logging (level applied after config load in main())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_agent_reply(state: dict[str, Any]) -> str:
    """Extract the final reply from the LangGraph state."""
    answer = state.get("answer")
    if isinstance(answer, str) and answer.strip():
        return answer.strip()

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


def _build_local_retriever(config: Any) -> DualRetriever:
    """Load persisted dual FAISS and return a ``DualRetriever``."""
    vector_store_path = config.vector_store_path
    if not vector_store_path:
        logger.error(
            "Set 'vector_store_path' in src/config/settings.yaml or ETB_CONFIG."
        )
        raise SystemExit(1)

    vector_store_root = Path(vector_store_path)
    backend_name = getattr(config, "vector_store_backend", "faiss")
    if backend_name != "faiss":
        raise SystemExit(
            f"Unsupported vector store backend: {backend_name}. Only 'faiss' is implemented."
        )

    backend = FaissDualVectorStoreBackend()
    if not backend.is_ready(vector_store_root):
        pdf_path = config.pdf
        if not pdf_path or not Path(pdf_path).exists():
            logger.error(
                "Vector index not found, and 'pdf' is not configured or missing. "
                "Set a valid 'pdf' path in src/config/settings.yaml or ETB_CONFIG."
            )
            raise SystemExit(1)

        logger.error(
            "Vector index not found or incomplete at: %s\n"
            "Build it with:\n"
            "  python -m etb_project.document_processor_cli "
            "--pdf %s --output-dir ./document_output "
            "--persist-index --vector-store-dir %s",
            vector_store_root,
            pdf_path,
            vector_store_root,
        )
        raise SystemExit(1)

    logger.info("Loading persisted text + caption vector stores...")
    embeddings = get_embeddings()
    text_vectorstore, caption_vectorstore = backend.load(
        vector_store_root, embeddings=embeddings
    )

    text_retriever = text_vectorstore.as_retriever(
        search_kwargs={"k": config.retriever_k}
    )
    caption_retriever = caption_vectorstore.as_retriever(
        search_kwargs={"k": config.retriever_k}
    )
    return DualRetriever(
        text_retriever=text_retriever,
        caption_retriever=caption_retriever,
        k_total=config.retriever_k,
    )


def main() -> None:
    """Load config, load persisted dual vector DB, run query or loop."""
    config = load_config()
    logging.getLogger().setLevel(getattr(logging, config.log_level, logging.INFO))
    logger.info("Starting ETB-project")

    mode = os.environ.get("ETB_RETRIEVER_MODE", "local").strip().lower()
    if mode == "remote":
        # Remote mode is used when running the retriever as a standalone service
        # (e.g. Docker compose). The orchestrator and UI typically use this mode.
        base = os.environ.get("RETRIEVER_BASE_URL", "").strip().rstrip("/")
        if not base:
            logger.error(
                "ETB_RETRIEVER_MODE=remote requires RETRIEVER_BASE_URL "
                "(e.g. http://localhost:8000)."
            )
            raise SystemExit(1)
        timeout_s = float(os.environ.get("RETRIEVER_TIMEOUT_S", "60"))
        retriever: Any = RemoteRetriever(
            base,
            k=config.retriever_k,
            timeout_s=timeout_s,
        )
        logger.info("Using remote retriever at %s", base)
    else:
        # Local mode is intended for quick experiments when indices exist on disk.
        retriever = _build_local_retriever(config)
        logger.info("Dual vector retrieval active (text + captions)")
    logger.info("Application started successfully")

    if config.query.strip():
        results = retriever.invoke(config.query)
        for i, doc in enumerate(results, 1):
            text = doc.page_content
            snippet = text[:200] + "..." if len(text) > 200 else text
            logger.info("Result %d: %s", i, snippet)
        return

    # Interactive query loop using LangGraph.
    # Orion is disabled here so the CLI always "answers" rather than sometimes
    # returning a clarification message depending on the model's judgement.
    logger.info("Enter a query (empty line to exit).")
    agent_llm = get_llm()
    rag_graph = build_rag_graph(
        llm=agent_llm, retriever=retriever, enable_orion_gate=False
    )

    while True:
        try:
            line = input("Query: ").strip()
        except EOFError:
            break
        if not line:
            return

        result = rag_graph.invoke({"query": line})
        reply = _get_agent_reply(result)
        if reply:
            print(reply)
        else:
            logger.warning(
                "No agent reply in result; full state keys: %s", list(result.keys())
            )


if __name__ == "__main__":
    main()
