import requests

job_id = "0b70fafb-8b5e-4e8e-9bbe-ece7193fbbcd"
url = f"http://localhost:8000/v1/jobs/{job_id}"

response = requests.get(url, timeout=10)
data = response.json()

print(f"Status: {data.get('status')}")
print(f"Message: {data.get('message')}")
print(f"Error: {data.get('error')}")
print(f"\nFull response:")
print(data)
