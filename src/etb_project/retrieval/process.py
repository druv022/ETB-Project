import pprint
from typing import cast

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

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
    return cast(list[Document], text_splitter.split_documents(documents))


def embed_documents(documents: list[Document]) -> list[list[float]]:
    embeddings = get_embedding_model()
    return cast(list[list[float]], embeddings.embed_documents(documents))


def embed_query(query: str) -> list[float]:
    embeddings = get_embedding_model()
    return cast(list[float], embeddings.embed_query(query))


def store_documents(documents: list[Document], embeddings: Embeddings) -> FAISS:
    embedding_dim = len(embeddings.embed_query("Hello, world!"))
    index = faiss.IndexFlatL2(embedding_dim)

    vectorstore = FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore(),
        index_to_docstore_id={},
    )
    vectorstore.add_documents(documents)
    return vectorstore


def process_documents(documents: list[Document]) -> FAISS:
    split_docs = split_documents(documents)
    vectorstore = store_documents(split_docs, get_embedding_model())
    return vectorstore


if __name__ == "__main__":
    file_path = "/Users/dhrubapujary/z_EDUCATION/MBT/Mod 3/Emerging Tech/Project/ETB-Project/data/Introduction to Agents.pdf"
    docs = load_pdf(file_path)
    vectorstore = process_documents(docs)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 10})
    results = retriever.invoke("What is an agent?")
    pprint.pprint(results)
