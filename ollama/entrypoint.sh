#!/bin/bash
set -e

ollama serve &
SERVER_PID=$!

echo "Waiting for Ollama server..."
until ollama list >/dev/null 2>&1; do sleep 1; done

for model in "$LLM_MODEL" "$EMBED_MODEL"; do
  echo "Pulling $model ..."
  ollama pull "$model"
done
echo "Models ready."

wait $SERVER_PID
