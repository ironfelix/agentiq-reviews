#!/bin/bash

# AgentIQ MVP Startup Script
# This script helps you start all necessary services

set -e

echo "🚀 AgentIQ MVP Startup"
echo "====================="
echo ""

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found."
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv (for env vars / python path), but don't rely on its console
# script entrypoints: venvs are not relocatable, and their shebangs can break
# after moving the project directory. We'll run via `python -m ...`.
source venv/bin/activate

PY="./venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "❌ Python not found at $PY"
    echo "Recreate venv: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

UVICORN_CMD=("$PY" -m uvicorn)
CELERY_CMD=("$PY" -m celery)

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found."
    echo "Run: cp .env.example .env"
    echo "Then edit .env with your credentials."
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running."
    echo "Start Redis with: brew services start redis (macOS) or sudo systemctl start redis (Linux)"
    exit 1
fi

echo "✅ Checks passed!"
echo ""

# Ask user which component to start
echo "Which component do you want to start?"
echo "1) FastAPI server (web)"
echo "2) Celery worker (background jobs)"
echo "3) Both (in background)"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "🌐 Starting FastAPI server..."
        echo "Open: http://localhost:8000"
        echo ""
        "${UVICORN_CMD[@]}" backend.main:app --reload --port 8000
        ;;
    2)
        echo ""
        echo "⚙️  Starting Celery worker..."
        echo ""
        "${CELERY_CMD[@]}" -A backend.tasks.celery_app worker --loglevel=info
        ;;
    3)
        echo ""
        echo "🌐 Starting FastAPI server in background..."
        "${UVICORN_CMD[@]}" backend.main:app --port 8000 > logs/fastapi.log 2>&1 &
        echo "FastAPI PID: $!"

        echo "⚙️  Starting Celery worker in background..."
        "${CELERY_CMD[@]}" -A backend.tasks.celery_app worker --loglevel=info > logs/celery.log 2>&1 &
        echo "Celery PID: $!"

        echo ""
        echo "✅ All services started!"
        echo "📊 Open: http://localhost:8000"
        echo "📝 Logs: logs/fastapi.log, logs/celery.log"
        echo ""
        echo "To stop: pkill -f uvicorn && pkill -f celery"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac
