"""Main entry point for ETB-project."""

import logging
from pathlib import Path

from etb_project.config import load_config
from etb_project.retrieval import load_pdf, process_documents

# Configure logging (level applied after config load in main())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
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
        return

    # Interactive query loop
    logger.info("Enter a query (empty line to exit).")
    while True:
        try:
            line = input("Query: ").strip()
        except EOFError:
            break
        if not line:
            break
        results = retriever.invoke(line)
        for i, doc in enumerate(results, 1):
            text = doc.page_content
            snippet = text[:300] + "..." if len(text) > 300 else text
            print(f"[{i}] {snippet}")
        print()


if __name__ == "__main__":
    main()
