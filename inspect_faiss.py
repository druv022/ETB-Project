"""Debug script to inspect FAISS index directly."""

from pathlib import Path
from langchain_community.vectorstores import FAISS
from etb_project.models import get_ollama_embedding_model

# Load FAISS index directly
text_dir = Path("data/vector_index/text")
embeddings = get_ollama_embedding_model()

print("Loading FAISS index...")
text_store = FAISS.load_local(
    str(text_dir),
    embeddings,
    allow_dangerous_deserialization=True
)

print(f"FAISS index loaded successfully")
print(f"Index type: {type(text_store.index)}")
print(f"Number of vectors in index: {text_store.index.ntotal}")
print(f"Docstore type: {type(text_store.docstore)}")
print(f"Number of docs in docstore: {len(text_store.docstore._dict)}")

# Try a test search
print("\nTesting similarity search...")
results = text_store.similarity_search("cheapest product IndMex", k=3)
print(f"Found {len(results)} results")

if results:
    for i, doc in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"Source: {doc.metadata.get('source')}")
        print(f"Content preview: {doc.page_content[:200]}...")
else:
    print("No results found!")
    
# Check docstore contents
print(f"\nFirst few doc IDs in docstore:")
for i, doc_id in enumerate(list(text_store.docstore._dict.keys())[:5]):
    print(f"  {i+1}. {doc_id}")
