# Quickstart — Запуск локально за 10 минут

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Redis 7+

## 1. Clone & Setup

```bash
cd apps/chat-center

# Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install
```

## 2. Database Setup

```bash
# Start PostgreSQL (via Docker)
docker run -d \
  --name agentiq-postgres \
  -e POSTGRES_PASSWORD=agentiq123 \
  -e POSTGRES_DB=agentiq_chat \
  -p 5432:5432 \
  postgres:15

# Apply migrations
cd backend
psql -U postgres -d agentiq_chat < ../database/schema.sql

# Or with Alembic (if configured)
alembic upgrade head
```

## 3. Redis Setup

```bash
# Start Redis (via Docker)
docker run -d \
  --name agentiq-redis \
  -p 6379:6379 \
  redis:7
```

## 4. Environment Variables

```bash
# backend/.env
DATABASE_URL=postgresql://postgres:agentiq123@localhost:5432/agentiq_chat
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-key-here
DEEPSEEK_API_KEY=your-deepseek-key
OZON_CLIENT_ID=your-ozon-client-id  # Demo credentials
OZON_API_KEY=your-ozon-api-key
```

**Генерация ENCRYPTION_KEY (Fernet):**
```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## 5. Start Backend

```bash
cd backend

# Terminal 1: FastAPI server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery worker
celery -A celery_app worker --loglevel=info

# Terminal 3: Celery Beat (scheduler)
celery -A celery_app beat --loglevel=info
```

Backend доступен: http://localhost:8000
API docs: http://localhost:8000/docs

## 6. Start Frontend

```bash
cd frontend
npm run dev
```

Frontend доступен: http://localhost:5173

## 7. Добавить первого продавца

### Через API:

```bash
curl -X POST http://localhost:8000/api/sellers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Seller",
    "marketplace": "ozon",
    "client_id": "123456",
    "api_key": "your-api-key"
  }'
```

### Через UI:
1. Открыть http://localhost:5173
2. Перейти в Settings → Add Seller
3. Заполнить форму:
   - Name: Test Seller
   - Marketplace: Ozon
   - Client ID: 123456
   - API Key: your-api-key
4. Сохранить

## 8. Проверить синхронизацию

```bash
# Вручную запустить sync task
curl -X POST http://localhost:8000/api/debug/sync-now

# Проверить логи Celery worker
# Должны увидеть:
# [INFO] Syncing chats for seller 1
# [INFO] Found 5 chats from Ozon API
# [INFO] Inserted 3 new chats, updated 2
```

## 9. Тестирование

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm run test

# E2E tests
npm run test:e2e
```

## 10. Docker Compose (альтернатива)

```bash
# Запустить всё одной командой
docker-compose up -d

# Доступ:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:3000
# - Flower (Celery UI): http://localhost:5555
```

## Troubleshooting

### Проблема: Celery не подключается к Redis
```bash
# Проверить Redis
redis-cli ping
# Должен вернуть: PONG

# Проверить REDIS_URL в .env
echo $REDIS_URL
```

### Проблема: PostgreSQL connection refused
```bash
# Проверить статус контейнера
docker ps | grep agentiq-postgres

# Проверить логи
docker logs agentiq-postgres

# Перезапустить
docker restart agentiq-postgres
```

### Проблема: Ozon API 401 Unauthorized
```bash
# Проверить credentials
curl -X POST https://api-seller.ozon.ru/v1/chat/list \
  -H "Client-Id: YOUR_CLIENT_ID" \
  -H "Api-Key: YOUR_API_KEY" \
  -d '{"filter": {"chat_status": "All"}, "limit": 10}'

# Если 401 → credentials неверные
# Получить новые: https://seller.ozon.ru/app/settings/api-keys
```

### Проблема: AI suggestions не работают
```bash
# Проверить DeepSeek API key
curl https://api.deepseek.com/v1/chat/completions \
  -H "Authorization: Bearer $DEEPSEEK_API_KEY" \
  -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "test"}]}'

# Если 401 → получить ключ: https://platform.deepseek.com/api_keys
```

## Полезные команды

```bash
# Очистить БД
psql -U postgres -d agentiq_chat -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
psql -U postgres -d agentiq_chat < database/schema.sql

# Пересобрать фронтенд
cd frontend
npm run build

# Просмотреть Celery tasks
celery -A celery_app inspect active

# Flower UI (мониторинг Celery)
celery -A celery_app flower --port=5555
```

## Что дальше?

1. **Прочитать документацию:**
   - `BACKEND_ARCHITECTURE.md` — как устроен бэкенд
   - `FRONTEND_ARCHITECTURE.md` — как устроен фронтенд
   - `FILTERS_AND_SLA.md` — как работают фильтры и SLA

2. **Настроить SLA правила:**
   - Перейти в UI → Settings → SLA Rules
   - Создать правила для своих кейсов

3. **Протестировать на реальных данных:**
   - Добавить свои Ozon credentials
   - Дождаться синхронизации (60s)
   - Ответить на первый чат

4. **Feedback:**
   - Что работает хорошо?
   - Что нужно улучшить?
   - Какие фичи добавить в первую очередь?
