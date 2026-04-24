"""Enhanced table extraction from PDFs using PyMuPDF's table detection.

This module provides table-aware text extraction that preserves table structure
in a format that's more easily understood by LLMs.
"""

from __future__ import annotations

from pathlib import Path

import fitz


def extract_tables_from_page(page: fitz.Page) -> list[dict]:
    """Extract tables from a PDF page using PyMuPDF's table finder.
    
    Returns a list of tables, each represented as a dict with:
    - rows: list of rows, where each row is a list of cell values
    - bbox: bounding box coordinates
    - markdown: markdown representation of the table
    """
    tables = []
    try:
        # Use PyMuPDF's table finder
        table_finder = page.find_tables()
        
        if not table_finder.tables:
            return []
        
        for table_index, table in enumerate(table_finder.tables):
            # Extract table data
            table_data = table.extract()
            
            # Convert to markdown for better LLM understanding
            markdown = _table_to_markdown(table_data)
            
            tables.append({
                "index": table_index,
                "rows": table_data,
                "bbox": table.bbox,
                "markdown": markdown,
            })
    except Exception:
        # If table detection fails, return empty list
        # This ensures the pipeline continues even if table extraction has issues
        pass
    
    return tables


def _table_to_markdown(table_data: list[list]) -> str:
    """Convert a table (list of rows) to markdown format.
    
    Args:
        table_data: List of rows, where each row is a list of cell values
        
    Returns:
        Markdown-formatted table string
    """
    if not table_data or not table_data[0]:
        return ""
    
    lines = []
    
    # Header row
    header = table_data[0]
    lines.append("| " + " | ".join(str(cell or "").strip() for cell in header) + " |")
    
    # Separator row
    lines.append("| " + " | ".join("---" for _ in header) + " |")
    
    # Data rows
    for row in table_data[1:]:
        # Pad row if it's shorter than header
        padded_row = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(str(cell or "").strip() for cell in padded_row) + " |")
    
    return "\n".join(lines)


def extract_page_text_with_tables(page: fitz.Page) -> str:
    """Extract text from a page, with tables formatted as markdown.
    
    This function:
    1. Extracts all tables from the page
    2. Gets the regular text
    3. Attempts to insert markdown tables in appropriate positions
    
    Returns:
        Combined text with tables formatted as markdown
    """
    # Extract tables
    tables = extract_tables_from_page(page)
    
    if not tables:
        # No tables found, return regular text
        return page.get_text() or ""
    
    # Get regular text
    text = page.get_text() or ""
    
    # For now, append tables at the end of the page text
    # This ensures they're included even if positioning is imperfect
    if tables:
        text += "\n\n## Tables on this page:\n\n"
        for table in tables:
            text += f"\n### Table {table['index'] + 1}\n\n"
            text += table['markdown']
            text += "\n\n"
    
    return text


def extract_page_documents_with_tables(pdf_path: str | Path):
    """Extract page-level documents with enhanced table extraction.
    
    This is an enhanced version of extract_page_documents that preserves
    table structure by converting tables to markdown.
    
    Returns:
        list[Document]: LangChain Document objects with table-aware text
    """
    from langchain_core.documents import Document
    
    pdf_path_obj = Path(pdf_path)
    documents: list[Document] = []
    
    doc = fitz.open(pdf_path_obj)
    try:
        total_pages = len(doc)
        for page_index in range(total_pages):
            page = doc[page_index]
            
            # Extract text with tables
            text = extract_page_text_with_tables(page)
            
            metadata = {
                "source": str(pdf_path_obj),
                "page": page_index + 1,
                "total_pages": total_pages,
            }
            documents.append(Document(page_content=text, metadata=metadata))
    finally:
        close = getattr(doc, "close", None)
        if callable(close):
            close()
    
    return documents


__all__ = [
    "extract_tables_from_page",
    "extract_page_text_with_tables",
    "extract_page_documents_with_tables",
]
