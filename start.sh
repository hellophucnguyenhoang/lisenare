#!/bin/bash

# start Ollama in the background and wait a moment for services to warm up
ollama serve &
sleep 5

ollama pull mahonzhan/all-MiniLM-L6-v2
ollama pull gemma3:1b

# Start the AI model server in the background
# Port (8001) is internal only
fastapi run ai_model_server/main.py --host 0.0.0.0 --port 8001 &

# Start the main app server in the foreground
# Cloud Run injects $PORT (usually 8080), which should map to the public app
fastapi run app/main.py --host 0.0.0.0 --port ${PORT:-8000}

# Wait for any process to exit
wait -n
