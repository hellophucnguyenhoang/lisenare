#!/bin/bash

set -e

echo "🔒 Launching applications in PRODUCTION mode..."

if [ "$1" = "--build" ]; then
    echo "🧹 Removing existing application images..."
    docker compose down --rmi local

    echo "🔨 Rebuilding all images from scratch..."
    docker compose build --no-cache

    echo "🚀 Starting all services..."
    docker compose up -d
else
    echo "🚀 Starting all services... (--build to build build from scratch)"
    docker compose up -d
fi

echo "✅ Production server is running in the background."
