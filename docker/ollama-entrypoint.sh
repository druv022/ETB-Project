#!/bin/sh
# Start Ollama, wait until the API accepts requests, pull the embedding model once, then
# block on the server process. Models persist in the mounted volume; subsequent starts are fast.
set -eu

MODEL="${OLLAMA_EMBEDDING_MODEL:-qwen3-embedding:0.6b}"

ollama serve &
pid=$!

i=0
while [ "$i" -lt 120 ]; do
  if ollama list >/dev/null 2>&1; then
    break
  fi
  i=$((i + 1))
  sleep 1
done

if ollama list 2>/dev/null | grep -qF "${MODEL}"; then
  echo "Embedding model already present: ${MODEL}"
else
  echo "Pulling embedding model: ${MODEL}"
  ollama pull "${MODEL}"
fi

echo "Ollama ready (model ${MODEL})."
wait "$pid"
