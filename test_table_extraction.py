"""Test script to verify table extraction from IndMex PDFs."""

from pathlib import Path

from etb_project.document_processing.table_extractor import extract_page_documents_with_tables

# Test with the first IndMex report
pdf_path = Path("data/indmex_pdfs/Report1_IndMex_Store_HQ_Overview.pdf")

print(f"Testing table extraction on: {pdf_path.name}\n")
print("=" * 80)

# Extract documents with table-aware extraction
documents = extract_page_documents_with_tables(pdf_path)

print(f"\nExtracted {len(documents)} pages\n")

# Show first 3 pages with some content
for i, doc in enumerate(documents[:3]):
    print(f"\n{'=' * 80}")
    print(f"PAGE {doc.metadata['page']} of {doc.metadata['total_pages']}")
    print(f"{'=' * 80}")
    content = doc.page_content
    # Show first 1000 chars of each page
    if len(content) > 1000:
        print(content[:1000] + "\n...(truncated)")
    else:
        print(content)
    
    # Check if tables were found
    if "## Tables on this page:" in content:
        print("\n[TABLE DETECTED ON THIS PAGE]")

print(f"\n{'=' * 80}")
print("Test complete!")
