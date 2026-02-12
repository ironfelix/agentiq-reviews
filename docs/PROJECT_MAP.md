# AgentIQ Project Map (Modules + Architecture)

Last updated: 2026-02-12

## 1) Что сейчас “продукт”

AgentIQ в текущей структуре это **suite** из двух рабочих контуров:

1. `apps/chat-center` — основной `agentiq.ru/app` (WB-first). Здесь строится Unified Communications Workspace: единый inbox для `чатов`, `вопросов`, `отзывов`.
2. `apps/reviews` — legacy-контур генерации детальных отчётов по отзывам (WBCON pipeline, PDF).

Намерение (по `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md`): постепенно тащить “review/question/chat” в unified слой `Interaction` внутри Chat Center.

## 2) Продукты внутри продукта (что видит пользователь)

### A. Workspace: “Сообщения”

Единая очередь обращений (`Interaction`) с фильтрами:
- канал: `Все / Отзывы / Вопросы / Чаты`
- приоритет/SLA
- статус: `needs_response` и т.д.

Карточка обращения:
- текст/контекст
- AI draft (assist)
- отправка ответа (reply dispatcher по каналу)
- thread timeline (deterministic + assist-only guardrails)

Документы:
- `docs/chat-center/INDEX.md`
- `docs/chat-center/SCENARIO_ENGINE.md`

### B. Workspace: “Аналитика”

Операционные метрики по работе операторов:
- quality funnel: `draft accepted / edited / manual`
- ops alerts (SLA overdue / quality regression)
- pilot readiness gate (GO/NO-GO)
- daily history (quality-history)

Источник:
- `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` (execution log реализации)

### C. Onboarding / Connect Marketplace

Пользователь подключает WB (и другие МП) через токены/ключи. Важно surfacing статуса:
- `syncing`
- `error + retry`
- `skip` (demo-mode)

## 3) Модульная карта (код)

### Основные приложения

- `apps/chat-center/frontend`
  - UI workspace: список обращений, детали, отправка ответов, analytics экран
  - основные папки: `src/components`, `src/services`, `src/types`

- `apps/chat-center/backend`
  - FastAPI: API для seller, chats, interactions (unified)
  - Celery: sync pipeline + scheduled checks
  - основные папки: `app/api`, `app/services`, `app/tasks`, `app/models`

- `apps/reviews`
  - FastAPI + Celery + SQLite
  - генерация HTML/PDF отчётов по отзывам + communication audit

### Документация модулей

- `docs/chat-center/` — Chat Center (API research, DB schema, планы)
- `docs/reviews/` — Reviews app (API, guardrails, quickstart)
- `docs/product/` — продуктовые планы/roadmap/UX audit
- `docs/architecture/` — архитектурные документы
- `docs/ops/` — деплой и security

## 4) Backend: ключевые подсистемы (Chat Center)

Ниже “что за что отвечает” в терминах сервисов `apps/chat-center/backend/app/services`:

- Ingestion:
  - `interaction_ingest.py` — reviews/questions/chats -> `Interaction` upsert
  - коннекторы: `wb_feedbacks_connector.py`, `wb_questions_connector.py`, `wb_connector.py`, `ozon_connector.py`
- Linking:
  - `interaction_linking.py` — deterministic/probabilistic candidates + policy “auto vs assist”
- Drafting:
  - `interaction_drafts.py`, `ai_analyzer.py` — AI draft generation (LLM + fallback)
  - `llm_runtime.py` — runtime-переключатель provider/model через `runtime_settings`
- Reply dispatch:
  - `api/interactions.py` (reply endpoint) — отправка по каналу: review/question/chat
- Metrics & Ops:
  - `interaction_metrics.py` — events-based качество, ops alerts, readiness
- Background workers:
  - `tasks/sync.py` — sync chats + unified interactions, cursor state, retry surfacing

## 5) Data model (концептуально)

Unifying сущность:
- `Interaction`: канал (`review/question/chat`), внешний id, статус/приоритет, корреляционные ключи, `extra_data`.
- `InteractionEvent`: аудируемое событие (draft/reply/policy_decision/ops_alert etc).

Рядом живут channel-specific модели (например, `Chat`, `Message`) как транспортный слой и для деталей.

## 6) Scenario Engine (как автоматизируем)

Внутри Chat Center нужен сценарный слой:
- вход: событие (new message, SLA due soon, resolved, buyer asked promo, etc.)
- решение: `allow/assist/deny` (policy + guardrails)
- действие: draft/schedule/send + audit

Документы:
- `docs/chat-center/SCENARIO_ENGINE.md`
- `docs/chat-center/scenario-engine.html`
- комплаенс по P3 окнам: `docs/research/06-wb-chat-consent-and-crm-triggers-2026.md`

## 7) Deployment: два разных контура

На сегодня у приложений разные runtime-профили:
- `apps/chat-center`: PostgreSQL + Redis + FastAPI + React
- `apps/reviews`: SQLite + Redis + FastAPI (+ Playwright для PDF)

Это важно для локального запуска, портов и конфигураций.

Документы:
- `docs/chat-center/QUICKSTART.md`
- `docs/reviews/QUICKSTART.md`
- `docs/ops/DEPLOYMENT.md`

## 8) Где искать “истину”

Если нужно понять “что реально в коде сейчас”:
- execution log и точные эндпоинты: `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md`
- схемы БД: `docs/chat-center/schema.sql` (chat-center)
- API surface: `apps/chat-center/backend/app/api/*.py`, `apps/reviews/backend/main.py`

