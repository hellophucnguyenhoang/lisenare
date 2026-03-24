#!/bin/bash
echo "Starting model server..."
fastapi run ai_model_server/main.py --host 0.0.0.0 --port 8001 &

echo "Starting web app..."
fastapi dev app/main.py --host 0.0.0.0 --port 8000 &

wait
