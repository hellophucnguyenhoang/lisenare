#!/bin/bash

echo "🛑 Stopping and removing containers..."

# Stops the stack safely
docker compose down

echo "✨ All services stopped successfully."
