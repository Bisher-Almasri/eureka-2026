#!/usr/bin/env bash
# start.sh - Script to launch Eureka Backend Services

echo "🚀 Starting Eureka Combined Backend Service..."

echo "Starting combined API (ai + face) on port 8000..."
python3 combined_api.py > combined_api.log 2>&1 &
API_PID=$!

echo "⏳ Service initializing..."
echo "Combined API PID: $API_PID (Port 8000)"

# Ensure background process is killed when the script exits
trap "kill $API_PID; exit" SIGINT SIGTERM

wait $API_PID
