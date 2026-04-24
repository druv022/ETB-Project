import requests
import json

# Test the Retriever API directly
url = "http://localhost:8000/v1/retrieve"

payload = {
    "query": "What is the cheapest product sold at IndMex stores?",
    "k": 5
}

response = requests.post(url, json=payload, timeout=10)

print(f"Status Code: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    print(f"Found {len(data.get('chunks', []))} documents\n")
    
    for i, doc in enumerate(data.get('chunks', [])[:3], 1):
        print(f"--- Document {i} ---")
        print(f"Source: {doc.get('metadata', {}).get('source', 'Unknown')}")
        print(f"Page: {doc.get('metadata', {}).get('page', 'Unknown')}")
        print(f"Content preview: {doc.get('content', '')[:200]}...")
        print()
else:
    print(f"Error: {response.text}")
