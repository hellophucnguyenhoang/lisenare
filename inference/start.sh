#!/bin/bash
set -e

echo "🧠 Starting Ollama Background Daemon..."
ollama serve &

echo "⏳ Waiting for Ollama to initialize..."
until curl -sf http://127.0.0.1:11434/api/tags > /dev/null; do
    sleep 1
done

echo "✅ Ollama is ready! Launching AI Inference Server..."

exec uv run fastapi run main.py --host 0.0.0.0 --port 8001