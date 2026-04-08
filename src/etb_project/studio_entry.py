"""LangGraph Studio / ``langgraph dev`` entrypoint.

Builds a minimal RAG graph from config: load PDF → chunk/embed → FAISS retriever.
This path is for local Studio debugging, not production (which uses the
orchestrator + remote retriever). Orion is disabled to keep Studio runs
predictable.
"""

from etb_project.config import load_config
from etb_project.graph_rag import build_rag_graph
from etb_project.models import get_ollama_llm as get_llm
from etb_project.retrieval import load_pdf, process_documents


def rag_app() -> object:
    """
    LangGraph entrypoint for Studio / langgraph dev.
    `inputs` can contain keys like {"query": "..."}.
    """
    config = load_config()
    if config.pdf is None:
        raise ValueError("Configuration missing 'pdf' path; cannot initialize RAG app.")

    docs = load_pdf(config.pdf)

    # Blocking: embed + FAISS build (Studio invokes this at graph load time).
    vectorstore = process_documents(docs)

    retriever = vectorstore.as_retriever(search_kwargs={"k": config.retriever_k})

    llm = get_llm()
    return build_rag_graph(llm=llm, retriever=retriever, enable_orion_gate=False)
