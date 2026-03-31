#!/bin/sh
# Used by docker-compose healthcheck; model name must match OLLAMA_EMBEDDING_MODEL / entrypoint pull.
set -eu
MODEL="${OLLAMA_EMBEDDING_MODEL:-qwen3-embedding:0.6b}"
ollama list 2>/dev/null | grep -qF "${MODEL}"
