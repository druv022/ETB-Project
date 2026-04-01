import pprint
from pathlib import Path

import faiss
import numpy as np
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from etb_project.document_processing import ImageCaptioner
from etb_project.document_processing.processor import (
    ChunkingConfig,
    process_pdf_to_hierarchical_text_and_caption_docs,
)
from etb_project.models import _normalize_embed_documents_for_faiss
from etb_project.models import get_ollama_embedding_model as get_embedding_model
from etb_project.retrieval.loader import load_pdf


def split_documents(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        add_start_index=True,
        separators=["\n\n", "\n", " ", ""],
        keep_separator=True,
        strip_whitespace=True,
    )
    return text_splitter.split_documents(documents)  # type: ignore[no-any-return]


def embed_documents(documents: list[Document]) -> list[list[float]]:
    embeddings = get_embedding_model()
    texts = [doc.page_content for doc in documents]
    return embeddings.embed_documents(texts)  # type: ignore[no-any-return]


def embed_query(query: str) -> list[float]:
    embeddings = get_embedding_model()
    return embeddings.embed_query(query)  # type: ignore[no-any-return]


def store_documents(documents: list[Document], embeddings: Embeddings) -> FAISS:
    """Persist documents into a new FAISS store.

    Embeddings are stacked explicitly before ``index.add`` so a single-document
    batch cannot become a 1D array (which breaks FAISS).
    """
    if not documents:
        embedding_dim = len(embeddings.embed_query("Hello, world!"))
        index = faiss.IndexFlatL2(embedding_dim)
        return FAISS(
            embedding_function=embeddings,
            index=index,
            docstore=InMemoryDocstore(),
            index_to_docstore_id={},
        )

    texts = [d.page_content for d in documents]
    raw = embeddings.embed_documents(texts)
    mat = _normalize_embed_documents_for_faiss(raw, len(texts))
    arr = np.asarray(mat, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise ValueError(
            f"Expected a 2D embedding matrix for FAISS, got shape {arr.shape}"
        )
    if arr.shape[0] != len(texts):
        raise ValueError(
            f"Embedding rows ({arr.shape[0]}) do not match texts ({len(texts)})"
        )

    embedding_dim = arr.shape[1]
    index = faiss.IndexFlatL2(embedding_dim)
    vectorstore = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )
    vectorstore.add_embeddings(
        list(zip(texts, arr.tolist(), strict=True)),
        metadatas=[d.metadata for d in documents],
    )
    return vectorstore


def append_documents_to_faiss(vectorstore: FAISS, documents: list[Document]) -> None:
    """Append documents using pre-stacked embeddings (same rules as :func:`store_documents`)."""
    if not documents:
        return
    texts = [d.page_content for d in documents]
    emb = vectorstore.embedding_function
    if not isinstance(emb, Embeddings):
        raise TypeError("FAISS vectorstore must use a LangChain Embeddings instance")
    raw = emb.embed_documents(texts)
    mat = _normalize_embed_documents_for_faiss(raw, len(texts))
    arr = np.asarray(mat, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    if arr.ndim != 2:
        raise ValueError(
            f"Expected a 2D embedding matrix for FAISS, got shape {arr.shape}"
        )
    if arr.shape[0] != len(texts):
        raise ValueError(
            f"Embedding rows ({arr.shape[0]}) do not match texts ({len(texts)})"
        )
    vectorstore.add_embeddings(
        list(zip(texts, arr.tolist(), strict=True)),
        metadatas=[d.metadata for d in documents],
    )


def process_documents(documents: list[Document]) -> FAISS:
    split_docs = split_documents(documents)
    vectorstore = store_documents(split_docs, get_embedding_model())
    return vectorstore


def process_prechunked_documents(documents: list[Document]) -> FAISS:
    """Store pre-split ``Document`` objects into a FAISS vector store.

    This is a thin adapter around :func:`store_documents` that assumes the
    input documents are already chunked (for example, by a standalone document
    processor). It reuses the default embedding model configuration.
    """
    embeddings = get_embedding_model()
    return store_documents(documents, embeddings)


def build_two_vectorstores(
    text_docs: list[Document],
    caption_docs: list[Document],
) -> tuple[FAISS, FAISS]:
    """Build separate FAISS indices for text chunks and image captions."""
    text_vectorstore = process_prechunked_documents(text_docs)

    # Always build the caption vectorstore via the same code path so the
    # behavior is deterministic and easier to test. If there are no caption
    # documents, the returned store is simply empty.
    caption_vectorstore = process_prechunked_documents(caption_docs)

    return text_vectorstore, caption_vectorstore


def process_pdf_to_vectorstores(
    pdf_path: str | Path,
    output_dir: str | Path,
    chunking_config: ChunkingConfig | None = None,
    image_captioner: ImageCaptioner | None = None,
) -> tuple[FAISS, FAISS]:
    """End-to-end dual-index pipeline for standalone processing."""
    text_docs, caption_docs, _parents = (
        process_pdf_to_hierarchical_text_and_caption_docs(
            pdf_path=pdf_path,
            output_dir=output_dir,
            chunking_config=chunking_config,
            image_captioner=image_captioner,
            asset_path_root=Path(output_dir),
        )
    )
    return build_two_vectorstores(text_docs, caption_docs)


if __name__ == "__main__":
    from etb_project.config import load_config

    cfg = load_config()
    file_path = cfg.pdf or "data/Introduction to Agents.pdf"
    if not file_path or not Path(file_path).exists():
        raise SystemExit("Set pdf path in settings.yaml or ETB_CONFIG YAML.")
    docs = load_pdf(file_path)
    vectorstore = process_documents(docs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": cfg.retriever_k})
    query = cfg.query or "What is an agent?"
    results = retriever.invoke(query)
    pprint.pprint(results)
