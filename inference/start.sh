#!/bin/bash
set -e

echo "🧠 Starting Ollama Background Daemon..."
OLLAMA_HOST=0.0.0.0:11434 ollama serve &
OLLAMA_PID=$!

echo "⏳ Waiting for Ollama to initialize..."
until curl -sf http://127.0.0.1:11434/api/tags > /dev/null; do
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
        echo "❌ Ollama failed to start."
        exit 1
    fi
    sleep 2
done

echo "✅ Ollama is ready!"

echo "🚀 Launching AI Inference Server..."
exec /app/.venv/bin/fastapi run main.py --host 0.0.0.0 --port 8001