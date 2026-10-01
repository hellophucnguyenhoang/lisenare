#!/bin/bash

echo "🛑 Stopping and removing containers..."

# Stops and tears down the stack safely
docker compose down --rmi local

echo "✨ All services stopped successfully."
