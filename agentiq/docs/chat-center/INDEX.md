# AgentIQ MVP+ Chat Center — Документация

> **Статус:** Ready for Development
> **Дата:** 2026-02-08
> **Версия:** 1.0

---

## 📚 Навигация по документации

### 🎯 Начать здесь
1. **[QUICKSTART.md](./QUICKSTART.md)** — Запуск за 10 минут (PostgreSQL + FastAPI + React)
2. **[DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)** — План разработки (4 недели, milestones, риски)

### 🔍 Исследование
3. **[OZON_CHAT_API_RESEARCH.md](./OZON_CHAT_API_RESEARCH.md)** — Полное исследование Ozon Chat API
   - Все endpoints с примерами
   - Webhooks vs Polling
   - Сравнение с WB API
   - Rate limits и best practices

### 🗄️ База данных
4. **[schema.sql](./schema.sql)** — PostgreSQL схема
   - Таблицы для multi-seller архитектуры
   - Индексы и triggers
   - SLA calculation function
   - Views для быстрых запросов

### 🏗️ Архитектура
5. **BACKEND_ARCHITECTURE.md** (TODO) — FastAPI + Celery + PostgreSQL
   - Структура проекта
   - API endpoints
   - OzonConnector
   - Background workers
   - Security (credentials encryption)

6. **FRONTEND_ARCHITECTURE.md** (TODO) — React + TypeScript + Zustand
   - Компоненты (ChatList, ChatWindow, AIPanel)
   - State management
   - Адаптация HTML прототипа
   - Polling vs WebSocket

### ⚙️ Функциональность
7. **FILTERS_AND_SLA.md** (TODO) — Система фильтров и SLA
   - Типы фильтров (unread, urgent, по дате)
   - SLA rules (keyword, time-based, rating)
   - UI для таймеров
   - Уведомления

---

## 🚀 Quick Links

### Для разработчиков
- [Установка зависимостей](./QUICKSTART.md#1-clone--setup)
- [Запуск локально](./QUICKSTART.md#5-start-backend)
- [Добавить продавца](./QUICKSTART.md#7-добавить-первого-продавца)
- [Troubleshooting](./QUICKSTART.md#troubleshooting)

### Для менеджеров
- [Roadmap (4 недели)](./DEVELOPMENT_PLAN.md)
- [Риски и митигация](./DEVELOPMENT_PLAN.md#риски-и-митигация)
- [Post-MVP фичи](./DEVELOPMENT_PLAN.md#post-mvp-phase-2)

### API Reference
- [Ozon API endpoints](./OZON_CHAT_API_RESEARCH.md#3-endpoints-для-чатов)
- [Webhooks setup](./OZON_CHAT_API_RESEARCH.md#4-webhooks)
- [Rate limits](./OZON_CHAT_API_RESEARCH.md#5-лимиты-api)

---

## 📊 Структура проекта

```
apps/chat-center/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── models/              # SQLAlchemy models
│   │   ├── api/                 # API routes
│   │   ├── services/            # Business logic (OzonConnector, AIService)
│   │   └── tasks/               # Celery tasks
│   ├── celery_app.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   ├── store/               # Zustand store
│   │   └── services/            # API client
│   ├── package.json
│   └── vite.config.ts
├── database/
│   └── schema.sql               # PostgreSQL schema
docs/
└── chat-center/                 # This folder
    ├── INDEX.md                 # You are here
    ├── QUICKSTART.md
    ├── DEVELOPMENT_PLAN.md
    ├── OZON_CHAT_API_RESEARCH.md
    └── schema.sql
```

---

## 🎯 Технологический стек

### Backend
- **FastAPI** — современный async web framework
- **SQLAlchemy** — ORM для PostgreSQL
- **Celery** — background tasks (polling, SLA checks)
- **Redis** — Celery broker
- **PostgreSQL** — основная БД
- **Fernet** — encryption для credentials
- **DeepSeek API** — AI suggestions

### Frontend
- **React 18** — UI library
- **TypeScript** — type safety
- **Vite** — fast dev server
- **Zustand** — lightweight state management
- **Axios** — HTTP client
- **CSS Modules** — styled components

### DevOps
- **Docker** — PostgreSQL + Redis containers
- **Docker Compose** — one-command setup
- **Alembic** — database migrations
- **Pytest** — backend testing
- **Playwright** — E2E testing

---

## 📈 Ключевые метрики MVP+

### Производительность
- **Polling interval:** 60s (can be reduced to 30s for urgent)
- **Response time API:** < 200ms (p95)
- **Chat sync latency:** < 5s (после получения нового сообщения)
- **AI suggestion time:** 2-5s (DeepSeek)

### Масштабируемость
- **Sellers:** 3-5 (MVP+), 50-100 (Phase 2)
- **Chats per seller:** 100-500 (MVP+), 5000+ (Phase 2)
- **Messages per day:** 1000-5000 (MVP+), 50000+ (Phase 2)
- **Concurrent users:** 5-10 (MVP+), 50+ (Phase 2)

### SLA
- **Urgent chats (< 1h):** 95% response rate
- **High priority (< 4h):** 90% response rate
- **Normal (< 24h):** 85% response rate

---

## 🛠️ Следующие шаги

1. **Прочитать [QUICKSTART.md](./QUICKSTART.md)** — понять как запустить локально
2. **Изучить [schema.sql](./schema.sql)** — понять структуру БД
3. **Просмотреть [DEVELOPMENT_PLAN.md](./DEVELOPMENT_PLAN.md)** — понять roadmap
4. **Начать разработку Week 1** — Database + Ozon Connector + FastAPI skeleton

---

## 📞 Контакты и поддержка

- **GitHub Issues:** (TODO: добавить ссылку)
- **Documentation:** `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/docs/chat-center/`
- **Slack:** (TODO: добавить канал)

---

**Версия:** 1.0
**Последнее обновление:** 2026-02-08
**Следующее обновление:** После Week 1 (добавить BACKEND_ARCHITECTURE.md и FRONTEND_ARCHITECTURE.md)
