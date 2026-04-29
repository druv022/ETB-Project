import requests
import json

# Test Retriever directly
url = "http://localhost:8000/v1/retrieve"

payload = {
    "query": "What is the employee count at the West Lafayette headquarters?",
    "k": 10
}

print("Testing Retriever API with product query...")
response = requests.post(url, json=payload, timeout=10)

print(f"\nStatus Code: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    chunks = data.get('chunks', [])
    print(f"Found {len(chunks)} chunks\n")
    
    if chunks:
        print("First 3 results:")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n--- Chunk {i} ---")
            print(f"Source: {chunk.get('metadata', {}).get('source', 'Unknown')}")
            print(f"Page: {chunk.get('metadata', {}).get('page', 'Unknown')}")
            print(f"Content preview: {chunk.get('content', '')[:300]}...")
    else:
        print("NO CHUNKS RETURNED - Retriever found nothing!")
else:
    print(f"Error: {response.text}")
