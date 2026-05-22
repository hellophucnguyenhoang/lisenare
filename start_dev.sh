#!/bin/bash

echo "Starting backend server..."
fastapi dev app/main.py --host 0.0.0.0 --port 8000 &


echo "Starting model server..."
fastapi run ai_model_server/main.py --host 0.0.0.0 --port 8001 &

wait -n
