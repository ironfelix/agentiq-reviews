# AgentIQ Chat Center - Backend

FastAPI backend для управления чатами маркетплейсов (Ozon, Wildberries, Yandex Market).

## Стек

- **FastAPI** - async web framework
- **SQLAlchemy 2.0** - async ORM с asyncpg
- **PostgreSQL** - основная БД
- **Redis + Celery** - фоновые задачи (polling)
- **Pydantic** - валидация данных
- **Cryptography (Fernet)** - шифрование API ключей

## Быстрый старт

### 1. Установка зависимостей

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 2. Настройка окружения

```bash
# Копируем шаблон
cp .env.example .env

# Генерируем ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Вставляем полученный ключ в .env файл
nano .env
```

### 3. Запуск PostgreSQL и Redis (Docker)

```bash
# PostgreSQL
docker run -d \
  --name agentiq-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=agentiq123 \
  -e POSTGRES_DB=agentiq_chat \
  -p 5432:5432 \
  postgres:15

# Redis
docker run -d \
  --name agentiq-redis \
  -p 6379:6379 \
  redis:7
```

### 4. Запуск сервера

```bash
# Development mode (auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

API будет доступен на http://localhost:8000

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Структура проекта

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Pydantic Settings
│   ├── database.py          # SQLAlchemy setup
│   ├── models/              # SQLAlchemy models
│   │   ├── seller.py
│   │   ├── chat.py
│   │   ├── message.py
│   │   └── sla_rule.py
│   ├── schemas/             # Pydantic schemas (validation)
│   │   ├── seller.py
│   │   ├── chat.py
│   │   └── message.py
│   ├── api/                 # API routers
│   │   ├── sellers.py
│   │   ├── chats.py
│   │   └── messages.py
│   ├── services/            # Business logic
│   │   ├── ozon_connector.py
│   │   └── encryption.py
│   └── tasks/               # Celery tasks (Week 2)
│       └── sync_chats.py
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

### Sellers (Продавцы)

- `GET /api/sellers` - Список продавцов
- `GET /api/sellers/{id}` - Получить продавца
- `POST /api/sellers` - Создать продавца
- `PATCH /api/sellers/{id}` - Обновить продавца
- `DELETE /api/sellers/{id}` - Деактивировать продавца

### Chats (Чаты)

- `GET /api/chats` - Список чатов (с фильтрами)
- `GET /api/chats/{id}` - Получить чат
- `POST /api/chats/{id}/mark-read` - Отметить чат прочитанным
- `POST /api/chats/{id}/close` - Закрыть чат

### Messages (Сообщения)

- `GET /api/messages/chat/{chat_id}` - Сообщения чата
- `GET /api/messages/{id}` - Получить сообщение
- `POST /api/messages` - Отправить сообщение

## Пример использования

### 1. Создать продавца

```bash
curl -X POST http://localhost:8000/api/sellers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Ozon Store",
    "marketplace": "ozon",
    "client_id": "your-client-id",
    "api_key": "your-api-key"
  }'
```

### 2. Получить список чатов

```bash
curl http://localhost:8000/api/chats?seller_id=1&unread_only=true
```

### 3. Отправить сообщение

```bash
curl -X POST http://localhost:8000/api/messages \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": 123,
    "text": "Здравствуйте! Чем могу помочь?"
  }'
```

## Безопасность

- API ключи маркетплейсов **шифруются** в БД через Fernet (symmetric encryption)
- ENCRYPTION_KEY должен храниться в .env и **не коммититься** в Git
- В production используйте HTTPS и надёжные секретные ключи

## Следующие шаги (Week 2+)

- [ ] Celery worker для polling чатов (каждые 60 сек)
- [ ] SLA rules engine (автоматический расчет дедлайнов)
- [ ] AI suggestions (DeepSeek API)
- [ ] WebSocket для real-time обновлений
- [ ] Alembic migrations (вместо create_all)

## Runtime LLM Config (через БД)

Чтобы менять провайдера/модель без правок кода и без деплоя, используется таблица `runtime_settings`.

Зачем это нужно:
- быстро переключать LLM между окружениями (demo/pilot/prod);
- делать безопасный rollback при деградации качества;
- временно отключать генерацию (`enabled=false`) без остановки сервиса.

Ключи конфигурации:
- `llm_provider` (например, `deepseek`)
- `llm_model` (например, `deepseek-chat`)
- `llm_enabled` (`true`/`false`)

Установить текущий runtime-конфиг:

```bash
cd apps/chat-center/backend
PYTHONPATH=. ./venv/bin/python scripts/set_llm_runtime.py \
  --provider deepseek \
  --model deepseek-chat \
  --enabled true
```

Примечание: для реальных LLM-вызовов нужен `DEEPSEEK_API_KEY` в `.env`.

## Документация

См. [`docs/chat-center/`](../../../docs/chat-center/):
- `OZON_CHAT_API_RESEARCH.md` - Документация Ozon Chat API
- `schema.sql` - Полная схема PostgreSQL
- `QUICKSTART.md` - Подробное руководство по запуску
- `DEVELOPMENT_PLAN.md` - 4-недельный план разработки
