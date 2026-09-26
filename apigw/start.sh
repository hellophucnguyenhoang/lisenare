#!/bin/bash
# Exit immediately if any command fails
set -e

echo "🚀 Launching API Gateway in production mode..."

# 'exec' replaces the shell process with FastAPI, making it PID 1
exec uv run fastapi run main.py --host 0.0.0.0 --port 8000
