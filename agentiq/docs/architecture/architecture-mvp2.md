# AgentIQ MVP2 — Архитектура

## Обзор

AgentIQ — платформа анализа отзывов и качества ответов продавцов на Wildberries. Пользователь вводит артикул товара и получает два типа отчётов:

1. **Анализ товара** — сигналы, причины негатива, сравнение вариантов, тренды
2. **Анализ ответов** — качество ответов продавца, потери конверсии, рекомендации

### Расширение MVP+ (план)

Следующий шаг — **Chat Center MVP+**: единое окно чатов маркетплейса (начать с Ozon).
Это отдельный поток данных, который будет жить рядом с текущими отчётами и использовать
тот же стек (FastAPI + Celery + Redis + DB).

## Схема

```
Browser → Nginx (443, SSL) → FastAPI (8000) → SQLite
    ↑                              ↓
    ├─ Telegram Login Widget       ↓
    ├─ JWT cookie (30 дней)   Celery task → Redis → Worker
    ├─ Invite code gate                            ↓
    │                                    WBCON API (19-fb)
    │                                    WB CDN (card, prices)
    │                                    DeepSeek LLM
    │                                         ↓
    │                              wbcon-task-to-card-v2.py → JSON
    │                                         ↓
    └──────────────────── Jinja2 templates → HTML → Playwright → PDF
```

## Компоненты

### Web-сервер (FastAPI)
- **Файл:** `apps/reviews/backend/main.py`
- Обслуживает HTML-страницы (Jinja2)
- REST API для создания/удаления задач
- JWT-аутентификация через cookies
- PDF-экспорт через Playwright

### Background Worker (Celery)
- **Файл:** `apps/reviews/backend/tasks.py`
- Получает отзывы через WBCON API v2
- Запускает анализ (`wbcon-task-to-card-v2.py`)
- Сохраняет результат в БД
- Отправляет уведомление в Telegram

### Анализ (Python script)
- **Файл:** `scripts/wbcon-task-to-card-v2.py`
- Классификация отзывов по причинам
- Анализ вариантов (цвет/размер)
- Тренды за 30 дней
- LLM-анализ коммуникации (DeepSeek)
- Расчёт денежных потерь

### База данных (SQLite)
- **Файл:** `apps/reviews/backend/database.py`
- Таблицы: `users`, `tasks`, `reports`, `notifications`, `invite_codes`
- Async через `aiosqlite`

## Потоки данных

### Создание задачи
```
1. POST /api/tasks/create {article_id: 123}
2. → Task(status=pending) в БД
3. → Celery delay(analyze_article_task)
4. → Response: TaskResponse
```

### Обработка задачи (Worker)
```
1. WBCON: POST /create_task_fb → task_id
2. WBCON: GET /task_status (polling 5s, max 5 min)
3. WBCON: GET /get_results_fb → feedbacks JSON
4. WB CDN: card.json (описание + текущая цена)
5. WB CDN: price-history.json (средняя цена за 3 мес)
6. Python: wbcon-task-to-card-v2.py (classify, LLM, money loss)
7. → Report(data=JSON) в БД
8. → Telegram notification
```

### Просмотр отчёта
```
GET /dashboard/report/{task_id}                 → report.html (товар)
GET /dashboard/report/{task_id}/communication   → comm-report.html (ответы)
GET /api/reports/{task_id}/pdf?type=communication → Playwright → PDF
```

## Аутентификация

1. Telegram Login Widget на `/` (index.html)
2. Callback → `/api/auth/telegram/callback`
3. HMAC-SHA256 проверка данных от Telegram
4. JWT cookie (HS256, 30 дней, httponly, samesite=lax)
5. Auto-refresh: если до exp < 7 дней → новый cookie
6. Первый вход: redirect на `/invite` (ввод инвайт-кода)
7. Повторный вход: сразу на `/dashboard`

## Внешние API

| API | Назначение | Auth |
|-----|-----------|------|
| WBCON (19-fb.wbcon.su) | Отзывы по артикулу | JWT в header `token` |
| WB CDN (basket-N.wbbasket.ru) | Карточка + история цен | Нет (публичный) |
| DeepSeek API | LLM-анализ коммуникации | API key |
| Telegram Bot API | Уведомления | Bot token |

## MVP+ Chat Center (добавляемое)

**Компоненты:**
- **Коннекторы:** `backend/chat_connectors/ozon.py` (позже WB/Yandex)
- **Sync task:** `sync_chats` (polling 60s, deduplication)
- **Таблицы БД:** `chat_accounts`, `chats`, `chat_messages`, `chat_sync_state`
- **API:** connect account, list chats, get messages, send message
- **UI:** список чатов + окно сообщений + фильтры/unread

**Архитектурный поток (упрощённо):**
```
Ozon API → Celery sync → DB (chats/messages) → FastAPI → UI
```

## Структура файлов

```
agentiq/
├── infra/docker-compose.yml    # Redis + Web + Worker
├── infra/deploy/nginx.conf     # Nginx reverse proxy + SSL
├── docs/
│   ├── architecture/architecture-mvp2.md  # (этот файл)
│   ├── ops/DEPLOYMENT.md                  # Гайд по деплою на VPS
│   └── reviews/API.md                     # Документация API
├── scripts/
│   ├── wbcon-task-to-card-v2.py  # Основной анализ
│   └── llm_analyzer.py           # DeepSeek LLM
└── apps/reviews/
    ├── Dockerfile              # FastAPI + Playwright
    ├── Dockerfile.worker       # Celery worker
    ├── requirements.txt
    ├── .env / .env.example
    ├── backend/
    │   ├── main.py             # FastAPI app
    │   ├── tasks.py            # Celery tasks
    │   ├── database.py         # SQLAlchemy models
    │   ├── auth.py             # JWT auth
    │   ├── pdf_export.py       # Playwright HTML→PDF
    │   └── telegram_bot.py     # TG notifications
    └── templates/
        ├── index.html          # Landing + TG Login
        ├── invite.html         # Invite code entry
        ├── dashboard.html      # Task list + create
        ├── report.html         # Product analysis
        └── comm-report.html    # Communication analysis
```
