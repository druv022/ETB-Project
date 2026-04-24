import requests
from pathlib import Path

pdf_dir = Path("data/indmex_pdfs")
url = "http://localhost:8000/v1/index/documents"

pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"Found {len(pdf_files)} PDF files to upload")

files = []
for pdf_path in pdf_files:
    files.append(('files', (pdf_path.name, open(pdf_path, 'rb'), 'application/pdf')))
    print(f"  - {pdf_path.name}")

print(f"\nUploading to {url}...")
response = requests.post(url, files=files, timeout=300)

for f in files:
    f[1][1].close()

print(f"\nStatus Code: {response.status_code}")
print(f"Response: {response.json()}")

if response.status_code == 202:
    job_id = response.json().get('job_id')
    print(f"\nIndexing started! Job ID: {job_id}")
    print(f"Check status with: python check_job.py (update job_id to {job_id})")
