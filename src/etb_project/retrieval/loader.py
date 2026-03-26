import pprint

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document


def load_pdf(file_path: str) -> list[Document]:
    loader = PyPDFLoader(file_path, mode="page", extract_images=True)
    return loader.load()  # type: ignore[no-any-return]


if __name__ == "__main__":
    file_path = "/Users/dhrubapujary/z_EDUCATION/MBT/Mod 3/Emerging Tech/Project/ETB-Project/data/Introduction to Agents.pdf"

    docs = load_pdf(file_path)
    pprint.pprint(docs[13].page_content)
    pprint.pprint(docs[13].metadata)
