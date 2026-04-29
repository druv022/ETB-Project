import requests
import json

# Test Orchestrator directly
url = "http://localhost:8001/v1/chat"

payload = {
    "message": "The current headcount as of April 2026.",
    "session_id": "debug-hq-test-123"
}

print("Testing Orchestrator API...")
response = requests.post(url, json=payload, timeout=60)

print(f"\nStatus Code: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    print(f"Answer: {data.get('answer', 'N/A')}\n")
    
    sources = data.get('sources', [])
    print(f"Number of sources used: {len(sources)}")
    
    if sources:
        print("\nSources retrieved:")
        for i, src in enumerate(sources[:3], 1):
            print(f"  {i}. {src.get('metadata', {}).get('source', 'Unknown')} (Page {src.get('metadata', {}).get('page', '?')})")
    else:
        print("WARNING: No sources were used!")
else:
    print(f"Error: {response.text}")
