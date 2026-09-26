#!/bin/bash

# Ensure script stops if a command fails
set -e

echo "🔒 Launching applications in PRODUCTION mode..."

if [ "$1" = "--no-build" ]; then
    docker compose up -d
else
    docker compose up -d --build
fi

echo "✅ Production server is running in the background."

