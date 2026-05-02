#!/usr/bin/env bash
# start.sh - Script to launch all Eureka components together

echo "🚀 Starting Eureka Background Services..."

# Start the Flask Backend (runs on port 8000)
echo "Starting Backend API..."
uv run python backend/app.py > backend.log 2>&1 &
BACKEND_PID=$!

# Start the Face Monitor (runs on port 5001)
echo "Starting Face Tracking..."
uv run python Face.py > face.log 2>&1 &
FACE_PID=$!

# Optional: Start the general distraction monitor
# echo "Starting Distraction Monitor..."
# uv run python monitor.py --focus > monitor.log 2>&1 &
# MONITOR_PID=$!

echo "⏳ Waiting for services to initialize..."
sleep 3

echo "✨ Launching Main Application..."
# Run the main Textual UI in the foreground
uv run python main.py

# When the main app closes (user quits), clean up the background processes
echo "🛑 Shutting down background services..."
kill $BACKEND_PID
kill $FACE_PID
# kill $MONITOR_PID

echo "Goodbye! 👋"
