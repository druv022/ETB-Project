"""Public retrieval API for the ``etb_project`` package.

Exports the pieces most callers need: local dual retrieval, remote HTTP
retriever, PDF loading/splitting helpers, and FAISS store helpers used by CLI
and tests. Heavy retrieval policy (HyDE, BM25, RRF) lives in
``retrieval.pipeline`` and is used by the retriever service internally.
"""

from etb_project.retrieval.dual_retriever import DualRetriever
from etb_project.retrieval.loader import load_pdf
from etb_project.retrieval.process import (
    process_documents,
    process_pdf_to_vectorstores,
    split_documents,
    store_documents,
)
from etb_project.retrieval.remote_retriever import RemoteRetriever

__all__ = [
    "DualRetriever",
    "RemoteRetriever",
    "load_pdf",
    "process_pdf_to_vectorstores",
    "process_documents",
    "split_documents",
    "store_documents",
]
