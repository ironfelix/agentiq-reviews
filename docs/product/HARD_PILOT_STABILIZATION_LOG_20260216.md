# Hard Pilot Stabilization Log (Codex)

**Date:** 2026-02-16  
**Owner:** Codex (GPT-5.3-Codex)  
**Goal:** закрыть найденные high/medium риски перед hard pilot и зафиксировать изменения прозрачно.

## 1. Что делалось

| ID | Задача | Статус | Кто делал |
|---|---|---|---|
| HP-001 | Починить контракт health-check в production deploy workflow (`ok` vs `healthy`) | ✅ DONE | Codex |
| HP-002 | Включить `alembic upgrade head` в staging/prod deploy workflows | ✅ DONE | Codex |
| HP-003 | Добавить quality gate в production workflow (backend tests + frontend lint/build) | ✅ DONE | Codex |
| HP-004 | Добавить frontend lint в pre-deploy check | ✅ DONE | Codex |
| HP-005 | Исправить timezone parsing для JWT `exp` | ✅ DONE | Codex |
| HP-006 | Привести frontend к lint-pass (0 errors) | ✅ DONE | Codex |
| HP-007 | Добавить source labels `WB API/Fallback` в UI inbox/chat | ✅ DONE | Codex |
| HP-008 | Синхронизировать backlog/readiness статусы и ownership | ✅ DONE | Codex |

## 2. Что изменено (файлы)

### CI/CD и pre-deploy
- `.github/workflows/deploy-production.yml`
- `.github/workflows/deploy-staging.yml`
- `scripts/pre-deploy-check.sh`

### Backend
- `apps/chat-center/backend/app/services/auth.py`
- `apps/chat-center/backend/alembic/versions/2026_02_14_0001-0001_add_interactions_and_interaction_events.py` (fix boolean default for PostgreSQL)

### Frontend (lint/perf/source labels)
- `apps/chat-center/frontend/src/App.tsx`
- `apps/chat-center/frontend/src/components/ChatList.tsx`
- `apps/chat-center/frontend/src/components/ChatWindow.tsx`
- `apps/chat-center/frontend/src/components/Login.tsx`
- `apps/chat-center/frontend/src/components/MarketplaceOnboarding.tsx`
- `apps/chat-center/frontend/src/components/PromoCodes.tsx`
- `apps/chat-center/frontend/src/components/SettingsPage.tsx`
- `apps/chat-center/frontend/src/index.css`
- `apps/chat-center/frontend/src/types/index.ts`
- `apps/chat-center/frontend/vite.config.ts`
- `apps/chat-center/frontend/e2e/performance.spec.ts`

### Документация
- `docs/product/BACKLOG.md`
- `docs/product/BACKLOG_UNIFIED_COMM_V3.md`
- `docs/product/MVP_READINESS_STATUS.md`
- `docs/ops/HARD_PILOT_SLO_RUNBOOK_20260216.md`

## 3. Верификация

### Frontend
- `npm run lint` → **0 errors, 0 warnings**
- `npm run build` → **green**

### Backend
- `./venv/bin/pytest -q` → **465 passed, 9 skipped**

## 4. Остаточные пункты (после закрытия follow-up)

1. Критичных открытых пунктов по этому пакету нет.

## 5. Follow-up (2026-02-16, docs-only фиксация)

### 5.1 Пункт 1: warnings в `App.tsx` (закрыт)
- Проверка: `npm run lint`
- Результат: **0 errors, 0 warnings**
- Статус: `DONE` (замечания `react-hooks/exhaustive-deps` устранены в `App.tsx`)

### 5.2 Пункт 2: live Alembic на окружениях (закрыт)
- Staging:
 - восстановлен отдельный контур `/opt/agentiq-staging`;
 - подняты сервисы `agentiq-staging`, `agentiq-staging-celery`, `agentiq-staging-celery-beat` (active);
 - staging БД `agentiq_chat_staging` приведена к актуальным heads (`0003`, `0005`);
 - staging endpoints: `http://79.137.175.164/staging/app/` и `http://79.137.175.164/staging/api/health` отвечают `200`.
- Production:
 - обнаружены `._*` (AppleDouble) файлы в `/opt/agentiq/alembic/versions`, удалены;
 - `alembic upgrade head/heads` показал историческую проблему состояния БД:
   миграции частично применены вручную, но `alembic_version` отставал;
 - подтверждено фактическое состояние схемы: `product_cache` + `customer_profiles` + `interactions.is_auto_response` присутствуют;
 - `alembic_version` приведён к актуальным heads через postgres: `0003`, `0005`.
- Статус: `DONE (prod + staging)`.

### 5.3 Пункт 3: свежий Pilot QA matrix report
- DNS-доступ к `https://agentiq.ru/api` из локального раннера нестабилен (`nodename nor servname provided`), поэтому прогон выполнен на сервере по `http://localhost:8001/api`.
- Итоговый отчёт: `docs/product/reports/pilot-qa-report-20260216-remote.md`
- Результат: **GO** (`pass=8, warn=0, fail=0`, `alerts=0`).
- Статус: `DONE`.

### 5.4 SLO/p95 runbook (до hard pilot)
- Сформирован и зафиксирован единый baseline порогов:
  `docs/ops/HARD_PILOT_SLO_RUNBOOK_20260216.md`.
- Включены целевые метрики: uptime, 5xx rate, p95 latency по ключевым API, sync freshness/success.
- Статус: `DONE` (документация).

### 5.5 Priority-first reload для очередей inbox
- Симптом: после reload в `Chat Center` сначала отображались mostly resolved/green, а `В работе` и `Ожидают ответа` дополнялись с задержкой после фоновой пагинации.
- Fix: в `apps/chat-center/frontend/src/App.tsx` добавлен fast prefetch (`needs_response=true`, page_size=100) до полной загрузки страницы `all`, с мгновенным merge в cache.
- Результат: unresolved-поток появляется сразу, оператор может начинать работу без ожидания догрузки остальных страниц.
- Проверка: `npm run lint -- --max-warnings=0` + `npm run build` (frontend) — `DONE`.
