# Use Python 3.11 slim image as base
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Editable install so ``etb_project`` resolves (src layout)
RUN pip install --no-cache-dir -e .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Embeddings use the Ollama HTTP API. When running via docker-compose, set OLLAMA_HOST to the
# ollama service (see docker-compose.yml). The official ollama-python client reads OLLAMA_HOST,
# not OLLAMA_BASE_URL.

# Expose port (adjust as needed)
EXPOSE 8000

# Retriever HTTP API (see README). Override to run CLI RAG: python -m etb_project.main
CMD ["python", "-m", "uvicorn", "etb_project.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
