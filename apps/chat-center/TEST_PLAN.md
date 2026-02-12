# AgentIQ Chat Center - Test Plan

## Application Architecture

**Backend** (`/apps/chat-center/backend/`):
- **Main application**: `app/main.py` - FastAPI с CORS и роутерами
- **API Routes**:
  - `app/api/auth.py` - Аутентификация (register, login, me, refresh, logout)
  - `app/api/chats.py` - Чаты (list, get, mark-read, close, analyze)
  - `app/api/messages.py` - Сообщения (list, send, get)
  - `app/api/sellers.py` - Продавцы (CRUD)
- **Models**: SQLAlchemy модели - Seller, Chat, Message, SLARule
- **Services**: Auth (JWT/bcrypt), AI analyzer, WB/Ozon connectors

**Demo Data** (`seed_demo_data.py`):
- 1 demo seller (wildberries)
- 5 чатов с разными статусами и приоритетами
- 14 сообщений

---

## API Endpoints

### Public (без авторизации)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/` | API info |
| POST | `/api/auth/register` | Регистрация продавца |
| POST | `/api/auth/login` | Вход |

### Protected (нужен токен)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/auth/me` | Текущий пользователь |
| POST | `/api/auth/refresh` | Обновить токен |
| POST | `/api/auth/change-password` | Сменить пароль |
| POST | `/api/auth/logout` | Выход |

### Optional Auth (работает в demo режиме)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chats` | Список чатов с фильтрами |
| GET | `/api/chats/{id}` | Получить чат |
| POST | `/api/chats/{id}/mark-read` | Пометить прочитанным |
| POST | `/api/chats/{id}/close` | Закрыть чат |
| POST | `/api/chats/{id}/analyze` | AI анализ |
| GET | `/api/messages/chat/{id}` | Сообщения чата |
| POST | `/api/messages` | Отправить сообщение |

---

## Test Cases

### Critical Priority

| ID | Endpoint | Test Case | Expected |
|----|----------|-----------|----------|
| TC-HEALTH-01 | GET /health | Health check | 200, `{"status": "healthy"}` |
| TC-AUTH-REG-01 | POST /api/auth/register | Valid registration | 200, JWT token |
| TC-AUTH-LOGIN-01 | POST /api/auth/login | Valid credentials | 200, JWT token |
| TC-AUTH-ME-01 | GET /api/auth/me | Valid token | 200, user info |
| TC-CHATS-LIST-01 | GET /api/chats | List all | 200, array of chats |
| TC-CHATS-GET-01 | GET /api/chats/1 | Get existing | 200, chat object |
| TC-MSG-LIST-01 | GET /api/messages/chat/1 | Get messages | 200, array of messages |
| TC-MSG-SEND-01 | POST /api/messages | Send message | 200, message object |

### High Priority

| ID | Endpoint | Test Case | Expected |
|----|----------|-----------|----------|
| TC-AUTH-REG-02 | POST /api/auth/register | Duplicate email | 400 |
| TC-AUTH-LOGIN-02 | POST /api/auth/login | Wrong password | 401 |
| TC-AUTH-LOGIN-03 | POST /api/auth/login | Unknown email | 401 |
| TC-AUTH-ME-02 | GET /api/auth/me | Missing token | 401 |
| TC-AUTH-ME-03 | GET /api/auth/me | Invalid token | 401 |
| TC-CHATS-LIST-02 | GET /api/chats?status=open | Filter by status | 200, filtered |
| TC-CHATS-LIST-03 | GET /api/chats?sla_priority=urgent | Filter by priority | 200, filtered |
| TC-CHATS-LIST-04 | GET /api/chats?has_unread=true | Filter unread | 200, filtered |
| TC-CHATS-GET-02 | GET /api/chats/999 | Missing chat | 404 |
| TC-MSG-LIST-02 | GET /api/messages/chat/999 | Missing chat | 404 |
| TC-MSG-SEND-02 | POST /api/messages | Empty text | 400 |

---

## Curl Commands for Manual Testing

### Health Check
```bash
curl -s http://localhost:8001/health | python3 -m json.tool
```

### Register User
```bash
curl -s -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","name":"Test Seller","marketplace":"wildberries"}'
```

### Login
```bash
curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'
```

### Get Current User (с токеном)
```bash
TOKEN="your_jwt_token_here"
curl -s http://localhost:8001/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### List Chats
```bash
# Все чаты (demo mode)
curl -s "http://localhost:8001/api/chats"

# Фильтр по статусу
curl -s "http://localhost:8001/api/chats?status=open"

# Фильтр по приоритету
curl -s "http://localhost:8001/api/chats?sla_priority=urgent"

# Поиск
curl -s "http://localhost:8001/api/chats?search=Иван"
```

### Get Chat
```bash
curl -s "http://localhost:8001/api/chats/1"
```

### Get Messages
```bash
curl -s "http://localhost:8001/api/messages/chat/1"
```

### Send Message
```bash
curl -s -X POST "http://localhost:8001/api/messages" \
  -H "Content-Type: application/json" \
  -d '{"chat_id":1,"text":"Тестовый ответ"}'
```

### Mark as Read
```bash
curl -s -X POST "http://localhost:8001/api/chats/1/mark-read"
```

### AI Analysis
```bash
curl -s -X POST "http://localhost:8001/api/chats/1/analyze"
```

---

## Key Findings

### 1. Authentication
- JWT-based с bcrypt хешированием
- Токены истекают через 7 дней
- Refresh token для продления сессии

### 2. Demo Mode vs Production
- **Demo mode**: Сообщения сохраняются со status="sent" сразу
- **Production mode** (с API credentials): status="pending", Celery задача в очередь

### 3. Seller Isolation
- С токеном: пользователь видит только свои чаты
- Demo mode: показывает все чаты

### 4. AI Analysis
- `/api/chats/{id}/analyze` поддерживает sync и async режимы
- Требует DEEPSEEK_API_KEY в environment

### 5. Chat Prioritization
- `sla_priority`: urgent, high, normal, low
- `chat_status`: waiting, responded, client-replied, auto-response
- `status`: open, closed

---

## Security Notes

1. **Sellers API** (`/api/sellers`) не имеет авторизации — нужно добавить в production
2. JWT секрет должен быть в environment variables
3. CORS настроен для localhost — обновить для production

---

## Future Automation

### pytest + httpx (Backend)
```python
import pytest
import httpx

@pytest.fixture
def client():
    return httpx.Client(base_url="http://localhost:8001")

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

def test_list_chats(client):
    r = client.get("/api/chats")
    assert r.status_code == 200
    assert "chats" in r.json()
```

### Playwright (Frontend)
```typescript
import { test, expect } from '@playwright/test';

test('login and view chat', async ({ page }) => {
  await page.goto('http://localhost:5173/app/');
  await page.click('text=Демо-режим');
  await expect(page.locator('.chat-list')).toBeVisible();
  await page.click('.chat-item >> nth=0');
  await expect(page.locator('.chat-messages')).toBeVisible();
});

test('copy AI suggestion', async ({ page }) => {
  // ... login steps
  await page.click('.chat-item >> nth=0');
  await page.click('.ai-suggestion');
  await expect(page.locator('text=Скопировано')).toBeVisible();
});
```

---

## Files Analyzed

- `app/main.py` - Main FastAPI application
- `app/api/auth.py` - Auth routes
- `app/api/chats.py` - Chat routes
- `app/api/messages.py` - Message routes
- `app/api/sellers.py` - Seller routes
- `app/models/*.py` - SQLAlchemy models
- `app/schemas/*.py` - Pydantic schemas
- `app/middleware/auth.py` - JWT middleware
- `app/services/auth.py` - Auth service
- `seed_demo_data.py` - Demo data seeder
