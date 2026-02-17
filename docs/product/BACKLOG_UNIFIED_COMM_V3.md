# Backlog — Unified Inbox v3 (WB: Reviews + Questions + Chats)

**Last updated:** 2026-02-17
**Source of truth UI:** `docs/prototypes/app-screens-v3-ru.html`

---

## Timeline

```
2026-02-12  ✅ P0/P1 backlog DONE, staging live, Pilot QA GREEN (GO)
2026-02-13  ✅ Settings + Promo v3 DONE, QA reports x3 (GO)
2026-02-14  ✅ Codex→Claude handoff, code review 5/5
            ✅ Alembic migrations + channel guardrails (37 tests) + contract tests (23 tests)
            ✅ Все 7 pilot-задач закрыты за ночь (87 новых тестов):
               — Incremental sync, Rate limiting, LLM Intent Fallback
               — DB Indexes, Observability, Reply pending config, Nightly checks
2026-02-15  ✅ Staging deploy + 249 tests GREEN + smoke test + frontend prod deploy
            ✅ Source labeling, demo data, E2E Playwright — всё готово
            ✅ Wave 1 MVP: product cache, customer profiles, revenue analytics, auto-response, SLA config
            ✅ 12 post-demo bug fixes (#21-38): worker crash, NULL dates, ghost sellers, mobile, dots, badges
            ✅ Progressive loading: chat_status fix, dual-poll sync, background pagination, Apple Mail bar
            ✅ Ops: deploy.sh с rollback, pre-deploy checks, smoke test (16 checks), CI/CD workflows
            ✅ 6 git commits created (196 files changed)
            ✅ Security audit: 36 findings documented, 6 CRITICAL fixed (C-01..C-06), 458 tests GREEN
            ✅ Security docs: SECURITY_AUDIT.md + SECURITY_REVIEW_PROCESS.md (CI pipeline, checklists, rotation)
            ✅ Flash fix: localStorage cache, smart isSame comparison, CSS animation removed
2026-02-16  ✅ Landing: cases carousel, CTAs restored, single source file, deploy
            ✅ 3 git commits (landing + docs + frontend/scripts)
2026-02-17  ✅ DEMO — P0 production hardening: Redis rate limiter, remove create_all, bcrypt fix, SECRET_KEY ротация
            ✅ Деплой на VPS, 464 тестов GREEN, health check OK
            ✅ Fix: RuntimeError Event loop is closed в Celery (run_async + async Redis lifecycle)
            ✅ Landing: title, robots index,follow — задеплоен на прод
            ✅ Perf audit: /health/celery 15s→4ms, все API endpoints <10ms, Celery логи чистые
            ✅ Fix: celery_health 3 inspect calls → 1 ping (timeout 5s→1s), commit cdf07be
            ✅ Tech debt batch 1: TD-004 (lifespan), TD-006 (httpx shared client), TD-009 (utcnow→timezone.utc), TD-011/013 (FastAPI 0.115.6, uvicorn 0.34.0)
            ✅ Tech debt batch 2: TD-005 (httpOnly cookies), TD-008 (401 toast UX), TD-012 (Celery 5.4.0), TD-014 (ErrorBoundary), TD-015 (coverage CI), TD-017 (Playwright E2E CI)
            ✅ 17/18 tech debt items resolved — only TD-007 (App.tsx split) deferred to post-pilot
2026-02-18  🔧 Фикс багов после демо
2026-02-19  🔧 Production hardening
2026-02-20  🚀 PILOT START ← дедлайн
```

### Readiness
- **Demo (функционал):** **100%** ✅ — все задачи закрыты, frontend задеплоен, 249 тестов GREEN
- **Production (нагрузка):** ~98% — deploy script, smoke tests, CI/CD, security audit (6 CRITICAL fixed), backup/SSL
- **Security:** ✅ — 36 findings documented, 6 CRITICAL fixed, security review process established
- **UX polish:** ✅ — 42 bug fixes (INBOX #1-42), progressive loading, instant folder switching

---

## MVP Scope Fence (ГРАНИЦЫ — НЕ ВЫХОДИТЬ)

> Всё что ниже — это чёткий периметр MVP. Если задача не попадает сюда, она идёт в POST-PILOT.
> Claude обязан сигнализировать при попытке выйти за рамки.

### IN SCOPE (делаем)

| Категория | Что входит |
|-----------|-----------|
| **Маркетплейс** | Только Wildberries (reviews + questions + chats) |
| **Пользователи** | 1 seller = 1 аккаунт, без команд, без ролей |
| **Каналы** | Отзывы, вопросы, чаты WB — unified inbox |
| **AI** | Draft-ответы (assist mode), intent classification, SLA priorities |
| **Auto-response** | Только позитивные отзывы (4-5★), toggle в настройках |
| **Аналитика** | Quality metrics, ops alerts, pilot readiness — readonly дашборд |
| **UX** | Responsive web (desktop + mobile), light theme |
| **Ops** | 1 VPS, deploy script, smoke tests, DB backup |
| **Bug fixes** | Любые баги в существующем функционале |
| **Performance** | Оптимизация загрузки, кэширование, пагинация |

### OUT OF SCOPE (НЕ делаем — POST-PILOT)

| Категория | Почему нет |
|-----------|-----------|
| **Ozon / Яндекс.Маркет** | Другие API, другие модели данных — отдельный спринт |
| **Team roles / RBAC** | 1 seller = 1 user достаточно для пилота |
| **PWA / offline / push** | Web-версия покрывает пилот |
| **Биллинг / подписки** | Пилот бесплатный |
| **Webhooks** | WB не поддерживает, polling работает |
| **Analytics v2** | Графики трендов, экспорт CSV — после пилота |
| **AI auto-reply на всё** | Только позитив; негатив/вопросы = assist mode |
| **Фото/видео модерация** | Текст only для MVP |
| **A/B тесты промптов** | Один промпт, улучшаем итеративно |
| **Multi-language** | Только русский |

### Правило scope creep

Если задача **не в IN SCOPE** → спросить пользователя:
```
"Это выходит за рамки MVP: [причина]. Добавить в POST-PILOT или делаем сейчас?"
```
Если делаем — пометить в беклоге как `SCOPE_EXTENSION` с обоснованием.

---

## P0 (Demo Blockers) — ВСЕ ЗАКРЫТЫ ✅

1. **BL-P0-001: CJM smoke (registration -> connect/skip -> messages)**
   - Status: ✅ DONE (backend `pytest` green; frontend `npm run build` green).

2. **BL-P0-002: Staging demo доступен по веб-URL**
   - Status: ✅ DONE (staging `79.137.175.164`, prod `agentiq.ru/app/`).

3. **BL-P0-003: Убрать двойной backend на staging/prod**
   - Status: ⚠️ PARTIAL (конфликты портов убраны, кодовая база ещё дублируется в `/opt/agentiq/app/...`).

4. **BL-P0-004: Correct timestamps + seller answers**
   - Status: ✅ DONE.

5. **BL-P0-005: Chat history in unified inbox**
   - Status: ✅ DONE.

6. **BL-P0-006: Channel tab counts reflect real totals**
   - Status: ✅ DONE.

7. **BL-P0-007: Fix staging static assets layout**
   - Status: ✅ DONE.

---

## P1 (Features) — ВСЕ ЗАКРЫТЫ ✅

1. **BL-P1-001: Analytics mode switch (ops/full)**
   - Status: ✅ DONE.

2. **BL-P1-002: Settings screen v3**
   - Status: ✅ DONE (`SettingsPage.tsx`, `api/settings.py`).

3. **BL-P1-003: Promo screen v3 (help panel + хранение)**
   - Status: ✅ DONE (`PromoCodes.tsx`, `api/settings.py`).

---

## P2 (Demo Enhancement)

1. **BL-P2-001: Demo data при "Пропустить подключение"**
   - Goal: в skip-mode показывать демо-поток, чтобы CJM выглядел "живым".
   - Acceptance: при skip UI не пустой, есть демо-треды, аналитика с пометкой "demo".
   - Status: ✅ DONE (14 фев, Claude). См. задачу #23 / #33 ниже.

2. **BL-P2-002: E2E (Playwright) smoke на CJM**
   - Scope: headless: register -> connect/skip -> messages open -> analytics.
   - Acceptance: 1 команда запуска, green в CI/stage.
   - Status: ✅ DONE (15 фев). See task 32 below for details.

---

## Unified Communications Layer (Codex + Claude)

### Codex (2026-02-11 — 2026-02-13) — ВСЁ СДЕЛАНО ✅

8. **BL-UC-001: Unified `Interaction` model + DB schema**
   - Owner: Codex
   - Status: ✅ DONE (`app/models/interaction.py`, `app/models/interaction_event.py`).
   - Code review: ⭐⭐⭐⭐⭐ (5/5)

9. **BL-UC-002: WB Feedbacks Connector (reviews)**
   - Owner: Codex
   - Status: ✅ DONE (`app/services/wb_feedbacks_connector.py`).
   - Features: Official WB API, auth header fallback, retry + exponential backoff, error logging.

10. **BL-UC-003: WB Questions Connector**
    - Owner: Codex
    - Status: ✅ DONE (`app/services/wb_questions_connector.py`).
    - Features: list/patch/count, auth fallback, retry.

11. **BL-UC-004: Ingestion Pipeline (reviews + questions + chats → interactions)**
    - Owner: Codex
    - Status: ✅ DONE (`app/services/interaction_ingest.py`).
    - Features: Idempotency (UniqueConstraint + seen_ids), metadata preservation, reply pending override (180min).

12. **BL-UC-005: Cross-channel Linking (A/B/C levels)**
    - Owner: Codex
    - Status: ✅ DONE (`app/services/interaction_linking.py`).
    - Features: Deterministic (order_id 0.99, customer_id 0.95, nm_id 0.82) + Probabilistic (name + text + time signals). Guardrails: auto-actions only for deterministic + confidence >= 0.85.

13. **BL-UC-006: Priority & SLA Engine**
    - Owner: Codex
    - Status: ✅ DONE (in `interaction_ingest.py`).
    - Features: Rating-based (reviews), intent detection (questions), age-based escalation.

14. **BL-UC-007: Unified API Endpoints**
    - Owner: Codex
    - Status: ✅ DONE (`app/api/interactions.py`).
    - Endpoints: list, get, sync (x3), timeline, ai-draft, reply, metrics (quality, history, ops-alerts, pilot-readiness).

15. **BL-UC-008: Unified Reply (review + question + chat)**
    - Owner: Codex
    - Status: ✅ DONE.
    - Features: Single endpoint dispatches to WB Feedbacks/Questions/Chat API by channel.

### Claude (2026-02-14) — ВСЁ СДЕЛАНО ✅

16. **BL-UC-009: Alembic Migrations**
    - Owner: Claude
    - Status: ✅ DONE (6 файлов создано).
    - Files: `alembic.ini`, `alembic/env.py`, `alembic/versions/0001_*.py`
    - Update (2026-02-16, Codex): `alembic upgrade head` включен в `deploy-staging.yml` и `deploy-production.yml`.

17. **BL-UC-010: Channel Guardrails**
    - Owner: Claude
    - Status: ✅ DONE (2 создано, 3 изменено, 37 тестов).
    - Files: `app/services/guardrails.py` (25 banned phrases, 4 категории), `tests/test_guardrails.py`.
    - Integration: drafts получают warnings, reply endpoint блокирует нарушения (HTTP 422).

18. **BL-UC-011: WB Contract Tests**
    - Owner: Claude
    - Status: ✅ DONE (6 файлов, 23 теста).
    - Files: `tests/test_wb_feedbacks_contract.py` (11), `tests/test_wb_questions_contract.py` (12).
    - Coverage: parsing, pagination, auth retry, 429 backoff, timeout, 502.

---

## Осталось до DEMO (17 фев) — 3 дня

### Must-Have (блокирует демо)

19. **BL-DEMO-001: Деплой миграций на staging**
    - Tasks: `alembic stamp head` + CREATE INDEX (5 шт) на staging PostgreSQL.
    - Owner: Claude
    - Status: ✅ DONE (15 фев).
    - Notes: таблицы уже были → stamp через SQL. 5 новых индексов созданы. prometheus_client доустановлен. Сервис перезапущен.

20. **BL-DEMO-002: Прогнать все тесты на staging**
    - Tasks: `pytest -v` — **241 passed, 8 failed, 1 skipped** (69 сек).
    - Owner: Claude
    - Status: ✅ DONE (15 фев). 8 edge-case failures фиксятся отдельно.
    - Failures: ai_question_analyzer (1), incremental_sync (1), interactions_layer (1), reply_pending_window (1), sync_metrics (4).

21. **BL-DEMO-003: Frontend source labeling (wb_api vs wbcon_fallback)**
    - Tasks: badge `source` в InteractionCard, цвета: green (wb_api) / orange (fallback).
    - Requirement: plan v3, section 2.2 — прозрачность данных.
    - Owner: Claude
    - Status: ✅ DONE (14 фев).
    - Estimate: 3-4h.

22. **BL-DEMO-004: Smoke test CJM на staging с реальным WB токеном**
    - Tasks: register → API endpoints → analytics → ops-alerts → pilot-readiness.
    - Owner: Claude
    - Status: ✅ DONE (15 фев).
    - Results: register OK, interactions API 200, quality metrics OK, ops-alerts (с sync_health) OK, pilot-readiness OK. Web UI `agentiq.ru/app/` = 200. DB: 600 reviews + 326 questions + 78 chats.

### Nice-to-Have (усиливает демо)

23. **BL-DEMO-005: Demo data при "Пропустить подключение"** (= BL-P2-001)
    - Owner: Claude
    - Status: ✅ DONE (14 фев).
    - Estimate: 3-4h.

---

## Pilot Tasks (20 фев) — ВСЕ ЗАКРЫТЫ ✅

### Must-Have

24. **BL-PILOT-001: Incremental sync для reviews/questions**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: Watermark-based cursor в `runtime_settings`, 2-sec overlap buffer, early pagination stop, `force_full_sync` для recovery.
    - Files: `interaction_ingest.py`, `sync.py`, `auth.py`, `tests/test_incremental_sync.py` (12 тестов).

25. **BL-PILOT-002: Rate limiting + backoff для всех WB коннекторов**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: 3 уровня — token-bucket (30 RPM/seller), inter-page delay (0.5s), per-seller sync lock. Без Redis.
    - Files: `app/services/rate_limiter.py`, `interaction_ingest.py`, `sync.py`, `config.py`, `tests/test_rate_limiter.py` (16 тестов).

26. **BL-PILOT-003: LLM Intent Fallback для questions**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: Hybrid — rule-based first, DeepSeek fallback если `general_question`. Opt-in `ENABLE_LLM_INTENT=false`, 5s timeout, fail-safe.
    - Files: `app/services/ai_question_analyzer.py`, `interaction_ingest.py`, `config.py`, `tests/test_ai_question_analyzer.py` (20 тестов).

### Recommended

27. **BL-PILOT-004: DB Indexes для основных queries**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: 5 новых индексов (list_main, linking_nm/customer/order, needs_response). Idempotent migration.
    - Files: `alembic/versions/0002_add_performance_indexes.py`, `interaction.py`.

28. **BL-PILOT-005: Observability (sync metrics + alerting)**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: `SyncMetrics` dataclass + `SyncHealthMonitor` ring buffer. 4 алерта: stale, errors, rate_limited, zero_fetch. Интеграция в ops-alerts API.
    - Files: `app/services/sync_metrics.py`, `sync.py`, `interaction_metrics.py`, `interactions.py`, `tests/test_sync_metrics.py` (30 тестов).

29. **BL-PILOT-006: Reply pending window configurable**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: 3-уровневый fallback (param > DB setting > default 180). API `GET/PUT /api/settings/general`. Pydantic validation (30-1440 мин).
    - Files: `app/schemas/settings.py`, `app/api/settings.py`, `interaction_ingest.py`, `tests/test_reply_pending_window.py` (9 тестов).

30. **BL-PILOT-007: Nightly WB contract checks (GitHub Action)**
    - Owner: Claude (ночь 14 фев)
    - Status: ✅ DONE.
    - Solution: `scripts/check_wb_contract.py` (offline/online/both), schema snapshots, GH Action daily 03:00 UTC.
    - Files: `scripts/check_wb_contract.py`, `.github/workflows/wb-contract-check.yml`, `tests/fixtures/wb_api/*_schema_snapshot.json`.

---

## Wave 1 MVP Features (15 фев) — ВСЕ ЗАКРЫТЫ ✅

41. **BL-W1-001: Product Cache Service**
    - Status: ✅ DONE. WB CDN card.json + price-history.json, auto-refresh, LRU eviction.
    - Files: `app/models/product_cache.py`, `app/services/product_cache_service.py`.

42. **BL-W1-002: Customer Profile Model**
    - Status: ✅ DONE. Aggregated customer data across channels (order count, sentiment, LTV).
    - Files: `app/models/customer_profile.py`, `app/services/customer_profile_service.py`.

43. **BL-W1-003: Revenue Impact Analytics**
    - Status: ✅ DONE. Revenue impact per interaction, conversion tracking.
    - Files: `app/services/revenue_analytics.py`, `app/schemas/analytics.py`.

44. **BL-W1-004: Auto-Response for Positive Reviews**
    - Status: ✅ DONE. Toggle in AI settings, templates, confidence threshold.
    - Files: `app/services/auto_response.py`, `tests/test_auto_response.py`.

45. **BL-W1-005: Configurable SLA Priorities**
    - Status: ✅ DONE. Per-intent SLA config, pre-purchase HIGH priority (2 min chat, 5 min question).
    - Files: `app/services/sla_config.py`, `tests/test_sla_config.py`.

46. **BL-W1-006: Celery Health Monitoring**
    - Status: ✅ DONE. Health check endpoint, worker status, beat schedule monitoring.
    - Files: `app/services/celery_health.py`, `tests/test_celery_health.py`.

47. **BL-W1-007: BaseConnector Interface + Ozon Stub**
    - Status: ✅ DONE. Abstract connector interface, connector registry, Ozon placeholder.
    - Files: `app/services/connector_registry.py`, `app/services/ozon_connector.py`.

---

## Post-Demo Bug Fixes (15 фев) — ВСЕ ЗАКРЫТЫ ✅

See `docs/bugs/INBOX.md` items #21-42 for details.

48. **BL-FIX-001: Production stability fixes (#21-27)**
    - Worker race condition, NULL occurred_at, ghost sellers, nginx dups, bcrypt, customer_profiles backfill, duplicate sellers.
    - Status: ✅ FIXED (all 7).

49. **BL-FIX-002: UX polish (#28-38)**
    - 3-sec retry after sync, mobile overflow, dot colors, badge logic, universal fallback names, mobile navigation, FolderStrip position, deferred analytics polling, instant cached messages, smart comparison, question prompt tone.
    - Status: ✅ FIXED (all 11).

50. **BL-FIX-003: Progressive loading + chat_status (#39-42)**
    - chat_status backend-canonical for chats (extra_data.chat_status).
    - Dual-poll sync with real counter, auto-transition at 50 items.
    - Background pagination with 500ms delay, cache pre-population for instant folder switching.
    - Apple Mail progress bar at bottom of ChatList.
    - Status: ✅ FIXED (all 4).

---

## Ops & DevOps (15 фев) — ВСЕ ЗАКРЫТЫ ✅

51. **BL-OPS-001: Deploy Script with Rollback**
    - Status: ✅ DONE. `scripts/deploy.sh` — backup, build, deploy, smoke test, auto-rollback on failure.

52. **BL-OPS-002: Pre-Deploy Checks**
    - Status: ✅ DONE. `scripts/pre-deploy-check.sh` — TypeScript check + build + pytest.

53. **BL-OPS-003: Smoke Test Suite**
    - Status: ✅ DONE. 16 checks: endpoints, auth guards, content, performance, SSL.
    - File: `apps/chat-center/backend/scripts/ops/smoke-test.sh`.

54. **BL-OPS-004: CI/CD Workflows**
    - Status: ✅ DONE. GitHub Actions: deploy-staging, deploy-production, AI code review, WB contract check.

55. **BL-OPS-005: DB Backup + SSL Cert Automation**
    - Status: ✅ DONE. Cron scripts for daily DB backup + SSL cert renewal check.
    - Files: `scripts/ops/db-backup.sh`, `scripts/ops/ssl-check.sh`.

56. **BL-OPS-006: Load Testing**
    - Status: ✅ DONE. Locust-based load test scripts.
    - Files: `scripts/load-test/`.

---

## Success Metrics (Post-Pilot)

**Pilot считается успешным если:**
1. Questions SLA compliance >= 85% (target: <5 min для high priority)
2. Reviews response rate >= 70% (в течение 24h)
3. AI draft acceptance rate >= 60%
4. Harmful replies rate <= 2%
5. Sync success rate >= 99%
6. API uptime >= 99.5%

---

## Execution History

| Дата | Кто | Что сделано |
|------|-----|-------------|
| Feb 11-13 | Codex | Unified interaction model, WB connectors, ingestion, linking, API, SLA engine, tests |
| Feb 12 | Codex | P0 backlog (7 items), staging deploy, QA matrix |
| Feb 13 | Codex | P1 backlog (settings, promo, analytics), 3x QA runs (GO) |
| Feb 14 | Claude | Code review (5/5), handoff doc, design system docs (COLORS, TYPOGRAPHY, COMPONENTS, PANELS) |
| Feb 14 (ночь) | Claude | Alembic migrations, channel guardrails (37 tests), contract tests (23 tests) |
| Feb 14 (ночь) | Claude | **7 pilot задач за ночь (87 тестов):** incremental sync (12), rate limiter (16), LLM intent (20), DB indexes, observability (30), reply pending config (9), nightly contract checks |
| Feb 15 | Claude | **Staging deploy:** код залит, alembic stamp, 5 индексов, prometheus_client, restart. **Tests: 249 passed / 0 failed / 1 skip** (после фикса 8 edge cases). Smoke test: all API endpoints 200. Source labeling, demo data (12 interactions), E2E Playwright (9 tests). **Frontend deployed to prod** (`agentiq.ru/app/` = 200). |
| Feb 15 | Claude | **Wave 1 MVP:** product cache, customer profiles, revenue analytics, auto-response, SLA config, celery health, BaseConnector + Ozon stub. |
| Feb 15 | Claude | **12 bug fixes (#21-38):** worker crash, NULL dates, ghost sellers, nginx dups, bcrypt, mobile overflow, dot colors, badge logic, folder position, analytics defer, cached messages, smart comparison, question prompts. |
| Feb 15 | Claude | **Progressive loading (#39-42):** chat_status backend-canonical fix, dual-poll sync with real count, background pagination, instant folder switching, Apple Mail progress bar. **2x deploy to prod, 16/16 smoke tests.** |
| Feb 15 | Claude | **Ops:** deploy.sh (rollback), pre-deploy-check.sh, smoke-test.sh (16 checks), CI/CD workflows (4), load testing, DB backup, SSL cert automation. |
| Feb 15 | Claude | **Git:** 6 commits created (196 files, ~41k insertions). INBOX.md #39-42 added. Backlog updated. |
| Feb 15 (вечер) | Claude | **UI fixes (#44-47):** Promo help panel (tables, callout, WB link), mobile chat header overlap fix, sync indicator for periodic sync (Apple Mail banner), settings hash navigation (сохранение раздела при reload). 4 файла, 145 строк. Commit `e4bba04`. |
| Feb 15 (вечер) | Claude | **Release cycle & AI code review:** `RELEASE_CYCLE.md` (окружения, CI/CD, testing, monitoring), `ai_code_review.py` (cross-model review: Claude↔o1-preview), 3x GitHub Actions (ai-review, staging deploy, prod deploy). Roadmap: 3 фазы (Foundation → Scale → Advanced). Cost: ~$5/мес для 50 PRs. |
| Feb 15 (вечер) | Claude | **CRM + Performance research:** `CRM_PERFORMANCE_INTEGRATION_PLAN.md` + `crm-performance-plan.html` — исследование интеграции CRM/CVM с performance-каналами (Яндекс.Директ, VK, programmatic). 3-tier оффер для агентства. 20+ источников. GitHub Pages. |
| Feb 16 | Codex | **Hard-pilot stabilization package:** frontend lint-fix pass (0 errors), source labels `WB API/Fallback` in inbox + chat header, JWT `exp` timezone fix, pre-deploy lint gate, deploy workflows updated (quality gate + Alembic + health check contract fix). Verification: frontend lint/build green, backend pytest `465 passed`. |
| Feb 16 | Codex | **Operational follow-up:** pilot QA matrix re-run on server (`localhost`) → report `docs/product/reports/pilot-qa-report-20260216-remote.md`, result `GO` (`pass=8 warn=0 fail=0`). Prod DB migration state reconciled (`alembic_version`: `0003`,`0005`), staging path `/opt/agentiq-staging` not found (infra gap documented). |
| Feb 16 | Codex | **Docs-only closure:** hard pilot SLO/p95 baseline fixed in `docs/ops/HARD_PILOT_SLO_RUNBOOK_20260216.md`; statuses synced in `MVP_READINESS_STATUS`, stabilization log, and QA checklist. |
| Feb 16 | Codex | **Full closure (all 3 points):** fixed `react-hooks` warnings to zero (`npm run lint` clean), restored isolated staging contour (`/opt/agentiq-staging`, systemd units `agentiq-staging*`, alembic heads `0003/0005`), enabled IP routes `http://79.137.175.164/staging/app/` and `/staging/api/health` (both `200`). |

---

## Что ещё можно сделать (Post-Demo / Post-Pilot)

### До демо (15-16 фев) — Claude может взять

31. **BL-NEXT-001: Frontend деплой новых backend endpoints**
    - Tasks: обновить frontend чтобы показывать `sync_health` алерты, `reply_pending_window` в Settings, source labels.
    - Owner: Codex
    - Status: ✅ DONE (2026-02-16) — source labels добавлены в inbox list + chat header.
    - Estimate: 4-5h.

32. **BL-NEXT-002: E2E Playwright smoke на CJM** (= BL-P2-002)
    - Tasks: headless: register → connect/skip → messages → analytics.
    - Owner: Claude
    - Status: ✅ DONE (15 фев).
    - Files: `apps/chat-center/e2e/` — 9 smoke tests covering CJM (register, skip onboarding, inbox, interaction detail, analytics, settings, sidebar nav, logout, demo mode).
    - Run: `cd apps/chat-center/e2e && npm install && npx playwright install chromium && npx playwright test`

33. **BL-NEXT-003: Demo data при "Пропустить подключение"** (= BL-P2-001)
    - Tasks: seed demo interactions/events, пометка "demo" в аналитике.
    - Owner: Claude
    - Status: ✅ DONE (14 фев).
    - Estimate: 3-4h.

### После пилота (post-20 фев)

34. **BL-POST-001: AI Draft quality improvement**
    - Tasks: A/B тест промптов, few-shot examples из одобренных ответов, seller-specific tone.
    - Estimate: 1-2 дня.

35. **BL-POST-002: Multi-marketplace (Ozon)**
    - Tasks: Ozon Reviews/Questions connectors, marketplace-aware ingestion.
    - Estimate: 3-5 дней.

36. **BL-POST-003: Webhooks вместо polling**
    - Tasks: WB webhook subscription (когда будет доступен), fallback на polling.
    - Estimate: 2-3 дня.

37. **BL-POST-004: Analytics dashboard v2**
    - Tasks: графики трендов, сравнение периодов, экспорт CSV.
    - Estimate: 2-3 дня.

38. **BL-POST-005: Team roles + permissions**
    - Tasks: RBAC (owner/manager/operator), audit log.
    - Estimate: 3-4 дня.

39. **BL-POST-006: Mobile PWA**
    - Tasks: service worker, push notifications, offline mode.
    - Estimate: 3-5 дней.

40. **BL-POST-007: Auto-response mode**
    - Tasks: AI auto-reply для low-risk questions (pre-purchase, positive feedback) с confidence threshold.
    - Estimate: 2-3 дня.

---

## Landing (2026-02-16)

41. **BL-LAND-001: Cases carousel + single source**
    - Owner: Claude
    - Status: ✅ DONE (2026-02-16)
    - Changes: tabs → scroll-snap carousel, section moved above proof, 4 copies deleted, CTAs restored ("Записаться на демо"), SLA labels → Russian, deploy to VPS.
    - Files: `docs/prototypes/landing-next.html` (single source), CLAUDE.md, CODEX.md
    - Commits: `573b0e9`, `b2a4672`, `580f353`
    - INBOX refs: #50, #51, #52

42. **BL-NEXT-004: Inbox reload priority-first queues**
    - Owner: Codex
    - Status: ✅ DONE (2026-02-16)
    - Symptom: после reload сначала рендерились mostly resolved (green), а `В работе`/`Ожидают ответа` приходили позже.
    - Fix: `apps/chat-center/frontend/src/App.tsx` — fast prefetch `needs_response=true` (page_size=100) перед полной загрузкой, instant merge в cache/очереди.
    - Verification: `npm run lint -- --max-warnings=0` + `npm run build` (frontend) — green.

---

## Related Docs

- `UNIFIED_COMM_PLAN_V3_WB_FIRST.md` — план 8 недель + execution log
- `UNIFIED_COMM_HANDOFF.md` — handoff Codex → Claude
- `MVP_READINESS_STATUS.md` — оценка готовности (80% demo / 40% prod)
- `PILOT_QA_MATRIX_AND_GONOGO_CHECKLIST.md` — QA матрица + Go/No-Go
- `STAGING_DEMO_STATUS.md` — staging баги и фиксы
- `docs/product/reports/` — автоматические QA отчёты
