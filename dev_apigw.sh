#!/bin/bash

echo "Starting API Gateway..."
cd apigw

export PYTHONPATH="."

uv run fastapi run main.py --host 0.0.0.0 --port 8000
