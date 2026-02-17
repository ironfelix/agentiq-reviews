# MVP Readiness Status (Unified Inbox: Reviews + Questions + Chats)

**Дата:** 2026-02-17 (обновлено)
**Предыдущая версия:** 2026-02-16

## Текущая готовность

### MVP по функционалу (demo/pilot UX): ~95%
- CJM registration/login → connect → messages работает.
- Unified inbox (review/question/chat) + drafts/reply + timeline + аналитика + ops-алерты.
- Channel guardrails (25 banned phrases, HTTP 422 на нарушения).
- LLM intent fallback для questions (DeepSeek, opt-in).
- Configurable reply pending window (30-1440 мин).

### MVP по production-hardening (нагрузка/ops/безопасность): ~100%
- ✅ Incremental sync (watermark-based cursor, early pagination stop).
- ✅ Rate limiting (Redis sliding window 30 RPM/seller + distributed lock — multi-worker safe).
- ✅ DB Indexes (5 новых для list/linking queries).
- ✅ Observability (structured sync metrics, health monitor, 4 типа алертов в ops-alerts API).
- ✅ Nightly WB contract checks (offline/online, GitHub Action daily).
- ✅ Contract tests (23 теста: parsing, auth retry, 429 backoff, timeout).
- ✅ E2E smoke (Playwright) — реализован и запускается в проекте.
- ✅ SECRET_KEY hardening (сильный ключ, ротация через sed).
- ✅ Schema managed by Alembic (create_all() удалён — нет schema drift риска).
- ✅ bcrypt/passlib несовместимость устранена (прямой bcrypt==4.2.1).
- ✅ Celery event loop isolation (async Redis закрывается корректно per-task).
- ✅ Celery health endpoint: <5ms (было 15s — 3 inspect calls × 5s).

### Пилот на 1-3 продавца: **~95%** готовности

## Ответы (reply) отправляются?

Да, единый эндпоинт `POST /api/interactions/{id}/reply`:
- `review` → WB Feedbacks API + guardrails validation (HTTP 422)
- `question` → WB Questions API + guardrails validation
- `chat` → outgoing message + Buyers Chat API (Celery)

Защитная логика: `extra_data.wb_sync_state=pending` + configurable reply pending window (default 180 мин).

## Что считается done для MVP пилота

- ✅ Единый inbox: `Отзывы + Вопросы + Чаты` (1 список, фильтры по каналу).
- ✅ Draft/reply: генерация черновика + guardrails + отправка ответа.
- ✅ Timeline между каналами (deterministic linking) + guardrails (auto-actions >= 0.85).
- ✅ Аналитика: quality rates, backlog/SLA, ops alerts, pilot readiness (GO/NO-GO).
- ✅ Incremental sync + rate limiting + observability.
- ✅ Frontend source labeling (wb_api vs fallback) — реализован в UI.
- ✅ E2E smoke test — реализован.

## P0 Production hardening (2026-02-17)

| Исправление | Статус | Детали |
|-------------|--------|--------|
| Redis rate limiter (multi-worker) | ✅ DONE | `rate_limiter.py` — sliding window INCR+EXPIRE, distributed lock |
| Убран create_all() из startup | ✅ DONE | `main.py` — schema только через Alembic migrations |
| bcrypt/passlib конфликт | ✅ DONE | `auth.py` — прямой bcrypt==4.2.1, passlib удалён |
| Celery async event loop isolation | ✅ DONE | `sync.py` — `_async_redis` reset + close per task |
| Celery health 15s → <5ms | ✅ DONE | `celery_health.py` — single ping(timeout=1) |
| SECRET_KEY hardened on VPS | ✅ DONE | `secrets.token_hex(32)`, sed rotation pattern |
| Inactive sellers deactivated | ✅ DONE | Sellers 14, 19 — `is_active=false` |

## Закрытые blockers (с 13 фев)

| Blocker | Статус | Как решено |
|---------|--------|------------|
| Incremental sync | ✅ DONE | Watermark в `runtime_settings`, 2-sec overlap, early stop |
| Rate limiting | ✅ DONE | Token-bucket 30 RPM + 0.5s delay + per-seller lock |
| DB Indexes | ✅ DONE | Migration 0002, 5 indexes, idempotent |
| Observability | ✅ DONE | `SyncMetrics` + `SyncHealthMonitor` + ops-alerts API |
| E2E smoke | ✅ DONE | Playwright CJM smoke |

## Статус 3 пунктов до hard pilot (закрыто 2026-02-16)

| Пункт | Текущее состояние | Статус |
|-------|-------------------|--------|
| Frontend hook-warnings (`react-hooks/exhaustive-deps`) | `npm run lint`: `0 errors`, `0 warnings` (deps в `App.tsx` приведены к корректным) | ✅ DONE |
| Staging-контур | Восстановлен отдельный контур: `/opt/agentiq-staging`, сервисы `agentiq-staging*` active, endpoints `http://79.137.175.164/staging/app/` и `http://79.137.175.164/staging/api/health` = `200` | ✅ DONE |
| SLO/p95 пороги в runbook | Зафиксированы в `docs/ops/HARD_PILOT_SLO_RUNBOOK_20260216.md` | ✅ DONE |

## Follow-up обновление (2026-02-16, Codex)

1. Pilot QA matrix прогнан на сервере (`localhost` контур) и сохранён:
   `docs/product/reports/pilot-qa-report-20260216-remote.md` → `GO`.
2. Production Alembic состояние выровнено:
   `alembic_version` = `0003`, `0005` (актуальные heads), схема подтверждена.
3. SLO/p95 пороги на hard pilot формально закреплены:
   `docs/ops/HARD_PILOT_SLO_RUNBOOK_20260216.md`.
4. Staging-контур восстановлен:
   `/opt/agentiq-staging` + отдельные systemd units + отдельный API порт `8002` + публичные staging маршруты по IP (`/staging/app`, `/staging/api`).
5. Исправлен reload UX очередей в inbox:
   в `apps/chat-center/frontend/src/App.tsx` добавлен priority-first prefetch (`needs_response=true`) до полной пагинации, чтобы `В работе`/`Ожидают ответа` были доступны сразу.

## Где смотреть staging

См. `docs/product/STAGING_DEMO_STATUS.md`.
