import requests
import json
import time

# Test with multiple questions in the same session
url = "http://localhost:8001/v1/chat"
session_id = "multi-question-test"

questions = [
    "According to the April 2026 product catalog, what is the cheapest product?",
    "How many employees work at the West Lafayette headquarters based on current reports?",
    "What is the price range of products in the catalog?"
]

print("Testing multiple questions in same session...\n")

for i, question in enumerate(questions, 1):
    print(f"=== Question {i} ===")
    print(f"Q: {question}")
    
    payload = {
        "message": question,
        "session_id": session_id
    }
    
    try:
        response = requests.post(url, json=payload, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', 'N/A')[:200] + "..." if len(data.get('answer', '')) > 200 else data.get('answer', 'N/A')
            sources = len(data.get('sources', []))
            
            print(f"Status: {response.status_code}")
            print(f"Answer preview: {answer}")
            print(f"Sources used: {sources}")
        else:
            print(f"ERROR: Status {response.status_code}")
            print(f"Response: {response.text[:200]}")
    
    except requests.exceptions.Timeout:
        print(f"ERROR: Request timed out after 120 seconds!")
    except Exception as e:
        print(f"ERROR: {str(e)}")
    
    print()
    time.sleep(2)  # Small delay between requests

print("Test complete!")
