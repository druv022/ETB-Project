import pprint
from typing import cast

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf(file_path: str) -> list[Document]:
    loader = PyPDFLoader(file_path, mode="page", extract_images=True)
    return cast(list[Document], loader.load())


if __name__ == "__main__":
    file_path = "/Users/dhrubapujary/z_EDUCATION/MBT/Mod 3/Emerging Tech/Project/ETB-Project/data/Introduction to Agents.pdf"

    docs = load_pdf(file_path)
    pprint.pprint(docs[13].page_content)
    pprint.pprint(docs[13].metadata)
