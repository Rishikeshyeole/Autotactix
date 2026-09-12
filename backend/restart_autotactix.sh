#!/bin/bash
echo "Stopping and removing existing autotactix container..."
docker rm -f autotactix 2>/dev/null

echo "Rebuilding and starting container..."
docker compose up -d --build

echo "Waiting for services to be ready..."
sleep 3

echo "AutoTactix is running at http://localhost:8000"