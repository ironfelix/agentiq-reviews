# MVP Readiness Status (Unified Inbox: Reviews + Questions + Chats)

**Дата:** 2026-02-14 (обновлено)
**Предыдущая версия:** 2026-02-13

## Текущая готовность

### MVP по функционалу (demo/pilot UX): ~90%
- CJM registration/login → connect → messages работает.
- Unified inbox (review/question/chat) + drafts/reply + timeline + аналитика + ops-алерты.
- Channel guardrails (25 banned phrases, HTTP 422 на нарушения).
- LLM intent fallback для questions (DeepSeek, opt-in).
- Configurable reply pending window (30-1440 мин).

### MVP по production-hardening (нагрузка/ops/безопасность): ~80%
- ✅ Incremental sync (watermark-based cursor, early pagination stop).
- ✅ Rate limiting (token-bucket 30 RPM/seller + inter-page delay + sync lock).
- ✅ DB Indexes (5 новых для list/linking queries).
- ✅ Observability (structured sync metrics, health monitor, 4 типа алертов в ops-alerts API).
- ✅ Nightly WB contract checks (offline/online, GitHub Action daily).
- ✅ Contract tests (23 теста: parsing, auth retry, 429 backoff, timeout).
- ⚠️ E2E smoke (Playwright) — ещё не сделан.

### Пилот на 1-3 продавца: **~85%** готовности

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
- ⚠️ Frontend source labeling (wb_api vs fallback) — TODO.
- ⚠️ E2E smoke test — TODO.

## Закрытые blockers (с 13 фев)

| Blocker | Статус | Как решено |
|---------|--------|------------|
| Incremental sync | ✅ DONE | Watermark в `runtime_settings`, 2-sec overlap, early stop |
| Rate limiting | ✅ DONE | Token-bucket 30 RPM + 0.5s delay + per-seller lock |
| DB Indexes | ✅ DONE | Migration 0002, 5 indexes, idempotent |
| Observability | ✅ DONE | `SyncMetrics` + `SyncHealthMonitor` + ops-alerts API |
| E2E smoke | ❌ TODO | Playwright CJM smoke |

## Оставшиеся задачи до DEMO (17 фев)

1. Деплой миграций на staging (30 мин)
2. Прогнать ~150 тестов на staging (30 мин)
3. Frontend source labeling (3-4h)
4. Smoke test CJM с реальным WB токеном (1h)

## Где смотреть staging

См. `docs/product/STAGING_DEMO_STATUS.md`.

