#!/bin/bash

echo "Starting backend server on port 8000..."
uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
