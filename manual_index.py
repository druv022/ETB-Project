"""Manually create and save FAISS index from processed documents."""

from pathlib import Path
from etb_project.document_processing.processor import process_pdf
from etb_project.vectorstore.store import build_dual_faiss_store, persist_dual_faiss_store

# Process all PDFs
pdf_dir = Path("data/indmex_pdfs")
output_dir = Path("data/document_output")
vector_store_dir = Path("data/vector_index")

pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"Processing {len(pdf_files)} PDFs...")

all_docs = []
for pdf in sorted(pdf_files):
    print(f"  Processing: {pdf.name}")
    docs = process_pdf(pdf, output_dir)
    all_docs.extend(docs)
    print(f"    Added {len(docs)} chunks")

print(f"\nTotal chunks: {len(all_docs)}")

# Build FAISS stores
print("Building FAISS stores...")
text_store, caption_store = build_dual_faiss_store(all_docs, [])

print(f"Text store built with {text_store.index.ntotal} vectors")
print(f"Caption store built with {caption_store.index.ntotal if caption_store else 0} vectors")

# Persist
print(f"Saving to {vector_store_dir}...")
persist_dual_faiss_store(
    text_vectorstore=text_store,
    caption_vectorstore=caption_store,
    output_dir=vector_store_dir,
    pdf_path=", ".join([str(p) for p in pdf_files]),
    chunk_size=1000,
    chunk_overlap=200,
)

print("✅ Done!")
