#!/bin/bash

# Kill background FastAPI jobs AND tear down Docker infrastructure automatically on the user exits (Ctrl+C)
trap 'echo "🛑 Stopping local servers and infrastructure..."; kill $(jobs -p) 2>/dev/null; docker compose -f docker-compose.dev.yml down; exit' SIGINT SIGTERM


echo "🧹 Checking for active infrastructure services..."
# 1. Start the Docker Infrastructure (Database & Redis Cache)
# --remove-orphans keeps the environment clean if the services change
docker compose -f docker-compose.dev.yml up -d --remove-orphans

export TARGET_ENV=".env.dev"

echo "------------------------------------------------"

# 3. Launch the API Gateway Server in the background
echo "🚀 Starting API Gateway Server..."
(
    cd apigw
    export PYTHONPATH="."
    exec uv run fastapi dev main.py --host 0.0.0.0 --port 8000
) &

# 4. Launch the AI Inference Server in the background
echo "🧠 Starting AI Inference Server..."
(
    cd inference
    export ESPEAK_DATA_PATH="/usr/lib/x86_64-linux-gnu/espeak-ng-data"
    export PHONEMIZER_ESPEAK_PATH="/usr/bin/espeak-ng"
    export PHONEMIZER_ESPEAK_LIBRARY="/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1"
    export PYTHONPATH="."
    exec uv run fastapi dev main.py --host 0.0.0.0 --port 8001
) &

echo "------------------------------------------------"
echo "✨ Both development servers are running cleanly!"
echo "👉 API Gateway:   http://localhost:8000"
echo "👉 Inference:     http://localhost:8001"
echo "💡 Press Ctrl+C at any time to tear down both local servers."

# Keep the shell process open and streaming terminal updates until interrupted
wait
