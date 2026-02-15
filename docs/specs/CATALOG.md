# Specs Catalog (Source Of Truth Map)

Last updated: 2026-02-13
Status: active

Этот файл отвечает на вопрос "что уже реализовано" и "где спека, по которой это живет".

## 1) Domain Specs (поведение, независимо от API)

### Entities (разные сущности отдельно)
- `entities/CHATS.md` - контракты и обработка чатов
- `entities/REVIEWS.md` - контракты и обработка отзывов
- `entities/QUESTIONS.md` - контракты и обработка вопросов
- `entities/UNIFIED_INTERACTION.md` - как мы маппим сущности в unified Interaction (если используем)

### Guardrails (как AI должен и не должен себя вести)
- `guardrails/AI_DRAFTS.md` - требования к AI-draft/reply: формат, запреты, audit trail
- `guardrails/REVIEWS_RESPONSES.md` - правила ответов на отзывы (banned phrases и т.д.)
- `guardrails/CHAT_RESPONSES.md` - правила ответов в чатах
- `guardrails/QUESTIONS_RESPONSES.md` - правила ответов на вопросы

### Marketplaces (вариативность и адаптеры)
- `marketplaces/CONTRACT.md` - общий контракт marketplace-адаптера (capabilities, нормализация)
- `marketplaces/WILDBERRIES.md` - WB: особенности API, статусы, ограничения
- `marketplaces/OZON.md` - Ozon: особенности (пока skeleton)

## 2) API Inventory (Chat Center backend)

Все роуты подключаются с префиксом `/api` в `apps/chat-center/backend/app/main.py`.

### `/api/auth/*`
Code: `apps/chat-center/backend/app/api/auth.py`
- POST `/api/auth/register`
- POST `/api/auth/login`
- GET `/api/auth/me`
- POST `/api/auth/refresh`
- POST `/api/auth/change-password`
- POST `/api/auth/connect-marketplace`
- POST `/api/auth/sync-now`
- POST `/api/auth/logout`

Spec: TBD (обычно описываем в feature-спеке на "Auth & Marketplace Connection")

### `/api/sellers/*`
Code: `apps/chat-center/backend/app/api/sellers.py`
- GET `/api/sellers`
- GET `/api/sellers/{seller_id}`
- POST `/api/sellers`
- PATCH `/api/sellers/{seller_id}`
- DELETE `/api/sellers/{seller_id}`

Spec: TBD

### `/api/chats/*`
Code: `apps/chat-center/backend/app/api/chats.py`
- GET `/api/chats`
- GET `/api/chats/{chat_id}`
- POST `/api/chats/{chat_id}/mark-read`
- POST `/api/chats/{chat_id}/analyze`
- POST `/api/chats/{chat_id}/close`
- POST `/api/chats/{chat_id}/reopen`

Spec: `entities/CHATS.md` (domain) + TBD (API-spec при необходимости)

### `/api/messages/*`
Code: `apps/chat-center/backend/app/api/messages.py`
- GET `/api/messages/chat/{chat_id}`
- POST `/api/messages`
- GET `/api/messages/{message_id}`

Spec: `entities/CHATS.md` (domain) + TBD

### `/api/interactions/*`
Code: `apps/chat-center/backend/app/api/interactions.py`
- GET `/api/interactions`
- POST `/api/interactions/sync/reviews`
- POST `/api/interactions/sync/questions`
- POST `/api/interactions/sync/chats`
- GET `/api/interactions/metrics/quality`
- GET `/api/interactions/metrics/quality-history`
- GET `/api/interactions/metrics/ops-alerts`
- GET `/api/interactions/metrics/pilot-readiness`
- GET `/api/interactions/{interaction_id}`
- GET `/api/interactions/{interaction_id}/timeline`
- POST `/api/interactions/{interaction_id}/ai-draft`
- POST `/api/interactions/{interaction_id}/reply`

Spec: `features/interaction-reply.md` (covers reply guardrails + entity contracts) + `entities/*` + `guardrails/*` + `marketplaces/*` (в зависимости от типа interaction)

### `/api/settings/*`
Code: `apps/chat-center/backend/app/api/settings.py`
- GET `/api/settings/promo`
- PUT `/api/settings/promo`
- GET `/api/settings/ai`
- PUT `/api/settings/ai`

Spec: TBD
