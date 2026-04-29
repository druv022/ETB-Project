import requests
import json

# Test Orchestrator directly
url = "http://localhost:8001/v1/chat"

payload = {
    "message": "Based on the current workforce report, how many employees work at the Corporate Headquarters in West Lafayette, Indiana?",
    "session_id": "test-session-124"
}

print("Sending request to Orchestrator API...")
response = requests.post(url, json=payload, timeout=60)

print(f"\nStatus Code: {response.status_code}\n")

if response.status_code == 200:
    data = response.json()
    print(f"Full Response JSON:")
    print(json.dumps(data, indent=2))
    print(f"\n--- Extracted Answer ---")
    if 'response' in data:
        print(data['response'])
    elif 'message' in data:
        print(data['message'])
    else:
        print("Could not find response field")
else:
    print(f"Error: {response.text}")
