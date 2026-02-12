#!/bin/bash

# AgentIQ MVP - Запуск с localhost.run туннелем
# Этот скрипт запускает FastAPI, Celery и создаёт публичный URL

set -e

echo "🚀 AgentIQ MVP - Starting with localhost.run tunnel"
echo "=================================================="

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Проверка виртуального окружения
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found!${NC}"
    echo "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Проверка Redis
echo -e "\n${YELLOW}📊 Checking Redis...${NC}"
if ! redis-cli ping > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Redis not running, starting...${NC}"
    brew services start redis
    sleep 2
    if ! redis-cli ping > /dev/null 2>&1; then
        echo -e "${RED}❌ Failed to start Redis!${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ Redis is running${NC}"

# Проверка базы данных
if [ ! -f "agentiq.db" ]; then
    echo -e "\n${YELLOW}📦 Database not found, initializing...${NC}"
    source venv/bin/activate
    python3 init_db.py
    echo -e "${GREEN}✅ Database initialized${NC}"
fi

# Запуск в фоне
echo -e "\n${YELLOW}🔧 Starting FastAPI server...${NC}"
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000 > logs/fastapi.log 2>&1 &
FASTAPI_PID=$!
echo -e "${GREEN}✅ FastAPI started (PID: $FASTAPI_PID)${NC}"

echo -e "\n${YELLOW}⚙️  Starting Celery worker...${NC}"
celery -A backend.tasks.celery_app worker --loglevel=info > logs/celery.log 2>&1 &
CELERY_PID=$!
echo -e "${GREEN}✅ Celery worker started (PID: $CELERY_PID)${NC}"

# Ждём запуска сервера
echo -e "\n${YELLOW}⏳ Waiting for FastAPI to start...${NC}"
sleep 3

# Проверка что сервер запустился
if ! curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${RED}❌ FastAPI failed to start!${NC}"
    echo "Check logs/fastapi.log for errors"
    kill $FASTAPI_PID $CELERY_PID 2>/dev/null
    exit 1
fi
echo -e "${GREEN}✅ FastAPI is responding${NC}"

# Создаём SSH туннель
echo -e "\n${YELLOW}🌐 Creating localhost.run tunnel...${NC}"
echo -e "${YELLOW}⚠️  This will open SSH connection and display your public URL${NC}"
echo ""

# Записываем PIDs в файл для удобного останова
echo "$FASTAPI_PID" > .pids
echo "$CELERY_PID" >> .pids

echo -e "${GREEN}=================================================="
echo -e "✅ AgentIQ MVP is running!"
echo -e "=================================================="
echo ""
echo -e "📍 Local:  http://localhost:8000"
echo -e "📍 Public: [will be shown below by localhost.run]"
echo ""
echo -e "📝 Next steps:"
echo -e "   1. Copy the public URL from output below"
echo -e "   2. Update @BotFather with /setdomain"
echo -e "   3. Update FRONTEND_URL in .env"
echo -e "   4. Restart: ./stop.sh && ./start-with-tunnel.sh"
echo ""
echo -e "📋 Logs:"
echo -e "   FastAPI: tail -f logs/fastapi.log"
echo -e "   Celery:  tail -f logs/celery.log"
echo ""
echo -e "🛑 To stop: ./stop.sh (or Ctrl+C here)"
echo -e "==================================================${NC}"
echo ""

# Запускаем SSH туннель (это блокирующая команда)
# Ctrl+C здесь остановит туннель и вернёт управление
ssh -o ServerAliveInterval=60 -R 80:localhost:8000 localhost.run

# Cleanup после Ctrl+C
echo -e "\n${YELLOW}🛑 Stopping services...${NC}"
kill $FASTAPI_PID $CELERY_PID 2>/dev/null
rm -f .pids
echo -e "${GREEN}✅ Stopped${NC}"
