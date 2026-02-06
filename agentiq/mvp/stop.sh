#!/bin/bash

# AgentIQ MVP - Stop all services

echo "🛑 Stopping AgentIQ MVP services..."

# Stop by PIDs if available
if [ -f ".pids" ]; then
    echo "📋 Found .pids file, stopping processes..."
    while read pid; do
        if ps -p $pid > /dev/null 2>&1; then
            echo "  Stopping PID: $pid"
            kill $pid 2>/dev/null
        fi
    done < .pids
    rm -f .pids
fi

# Fallback: kill by process name
echo "🔍 Checking for remaining processes..."

# Kill uvicorn
pkill -f "uvicorn backend.main:app" 2>/dev/null && echo "  ✅ Stopped FastAPI"

# Kill celery
pkill -f "celery -A backend.tasks.celery_app worker" 2>/dev/null && echo "  ✅ Stopped Celery"

# Kill SSH tunnel
pkill -f "ssh.*localhost.run" 2>/dev/null && echo "  ✅ Stopped SSH tunnel"

echo ""
echo "✅ All services stopped"
echo ""
echo "💡 To start again: ./start-with-tunnel.sh"
