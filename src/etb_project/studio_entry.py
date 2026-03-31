# src/etb_project/studio_entry.py
# import asyncio


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

    # Build retriever
    docs = load_pdf(config.pdf)

    # Run blocking embedding work in a background thread via async helper.
    vectorstore = process_documents(docs)

    retriever = vectorstore.as_retriever(search_kwargs={"k": config.retriever_k})

    llm = get_llm()
    return build_rag_graph(llm=llm, retriever=retriever, enable_orion_gate=False)
