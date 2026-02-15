# AgentIQ — Продуктовый бэклог

**Last updated:** 2026-02-14
**Status:** Demo ready, pilot 20 фев

---

## Timeline

```
2026-02-17  🎯 FINAL DEMO
2026-02-20  🚀 PILOT START (3 sellers, реальные деньги)
2026-03-06  📊 Pilot review (go/no-go для rollout)
────────────────────────────────────────────────
        ▼ ВОДОРАЗДЕЛ: demo → mvp ▼
────────────────────────────────────────────────
2026-03-XX  💰 MVP (под нагрузкой, платные пилоты)
```

---

## ══════════════════════════════════════════════
## ЧАСТЬ 1: ДО FINAL DEMO (17 фев)
## ══════════════════════════════════════════════

**Статус: 100% READY.** Все задачи закрыты, 249 тестов GREEN, frontend на проде.

### Закрыто (33 задачи)

| Блок | Кол-во | Что |
|------|--------|-----|
| P0 Demo Blockers | 7 | CJM smoke, staging, timestamps, chat history, channel tabs, assets |
| P1 Features | 3 | Analytics mode, Settings v3, Promo v3 |
| Unified Comm Layer | 11 | Interaction model, WB connectors (3), ingestion, linking, API, SLA, reply, migrations, guardrails, contract tests |
| Demo Readiness | 5 | Migrations deploy, test run, source labeling, smoke test, demo data |
| Pilot Prep | 7 | Incremental sync, rate limiter, LLM intent, DB indexes, observability, reply_pending config, nightly checks |

### Осталось до демо

| ID | Задача | Статус | Критичность |
|----|--------|--------|-------------|
| — | Buffer day (багфиксы) | 16 фев | nice-to-have |
| BL-NEXT-001 | Frontend: sync_health алерты, source labels в UI | TODO | nice-to-have, не блокирует демо |

**Демо можно проводить прямо сейчас.**

---

## ══════════════════════════════════════════════
## ЧАСТЬ 2: ДО MVP (платные пилоты под нагрузкой)
## ══════════════════════════════════════════════

MVP = продукт, который 10-50 sellers используют ежедневно за деньги.
Отличие от демо: **надёжность, скорость, данные, доверие**.

### 2.1 Production Hardening (до 20 фев — PILOT START)

| ID | Задача | Зачем | Effort |
|----|--------|-------|--------|
| MVP-001 | SSL cert auto-renewal + мониторинг | Сертификат не должен истечь на проде | low |
| MVP-002 | DB backups (pg_dump cron + offsite) | Потеря данных seller'а = потеря клиента | low |
| MVP-003 | Error alerting (Sentry или аналог) | Узнавать о падениях до звонка seller'а | medium |
| MVP-004 | Load test (100 concurrent users, 10 sellers) | Убедиться что staging держит пилот | medium |
| MVP-005 | Celery health monitoring (flower или custom) | Sync задачи не должны молча умирать | low |

### 2.2 Data Quality & Context (первые 2 недели пилота)

| ID | Задача | Зачем | Gap ID | Effort |
|----|--------|-------|--------|--------|
| MVP-006 | Product cache (WB CDN card.json sync) | AI draft без контекста товара = generic ответ. Seller видит что AI не знает его товар → не доверяет | G2-02 | low |
| MVP-007 | Customer profile table (name, order count, sentiment trend) | Без истории клиента каждый чат = с нуля. Seller хочет видеть "этот клиент уже писал 3 раза" | G2-01 | medium |
| MVP-008 | Revenue impact в analytics ("сколько стоит плохой ответ") | Seller платит за AgentIQ → хочет видеть ROI в рублях, не в процентах | G5-01 | low |

### 2.3 AI Quality (первый месяц пилота)

| ID | Задача | Зачем | Gap ID | Effort |
|----|--------|-------|--------|--------|
| MVP-009 | Template DB (per-intent, per-channel, per-seller) | Хардкод шаблонов в коде = не настраивается. Seller хочет свой тон | G4-01 | medium |
| MVP-010 | AI draft quality v2 (few-shot из одобренных ответов seller'а) | Accept rate 60% → 80%. Seller утверждает ответы → система учится его стилю | BL-POST-001 | medium |
| MVP-011 | Auto-response для low-risk (pre-purchase, positive feedback) | +20% конверсии (WB стат). Pre-purchase ответ за 2 мин vs 2 часа = seller зарабатывает больше | BL-POST-007 | medium |

### 2.4 Reliability & Scale

| ID | Задача | Зачем | Gap ID | Effort |
|----|--------|-------|--------|--------|
| MVP-012 | BaseConnector interface + factory dispatch | Ozon подключение не должно трогать sync.py. Каждый новый marketplace = только новый класс | G1-01, G1-02 | low |
| MVP-013 | Ozon reviews + questions connectors | Второй marketplace = proof что архитектура работает. Увеличивает TAM 2x | G1-04, BL-POST-002 | medium |
| MVP-014 | Priority thresholds в RuntimeSetting (не хардкод) | Seller хочет "мне urgent = rating 1-2, другому = rating 1-3". Без этого → one-size-fits-all | G3-05 | low |
| MVP-015 | Analytics dashboard v2 (тренды, сравнение периодов, CSV export) | Seller хочет показать руководству отчёт за месяц. "Скачать CSV" = must-have для B2B | BL-POST-004 | medium |

### 2.5 MVP Definition of Done

Pilot считается **успешным** (→ переход к платному MVP) если:

| Метрика | Target | Как измерить |
|---------|--------|-------------|
| Questions SLA compliance | >= 85% | `GET /interactions/quality-metrics` |
| Reviews response rate (24h) | >= 70% | `GET /interactions/quality-metrics` |
| AI draft acceptance rate | >= 60% | `GET /interactions/quality-metrics` |
| Harmful replies rate | <= 2% | `GET /interactions/quality-metrics` |
| Sync success rate | >= 99% | `GET /interactions/ops-alerts` |
| API uptime | >= 99.5% | External monitoring |
| NPS от pilot sellers | >= 7 | Manual survey |

---

## ══════════════════════════════════════════════
## ЧАСТЬ 3: ПОСЛЕ MVP (roadmap, не в scope пилота)
## ══════════════════════════════════════════════

Эти задачи **не нужны** для первых платных пилотов. Делаем когда:
- Sellers вырастут до команд (routing, RBAC)
- Появится запрос на advanced intelligence (RAG, learning loop)
- Нужна enterprise-grade аналитика

### 3.1 Orchestration (когда seller = команда)

| ID | Задача | Gap ID | Trigger |
|----|--------|--------|---------|
| ROAD-001 | Routing engine (по team, skill, load) | G3-01 | Seller с 3+ операторами |
| ROAD-002 | Operator assignment (auto/manual) | G3-02 | То же |
| ROAD-003 | Escalation workflow (supervisor, timeout) | G3-03 | Seller с менеджером + операторами |
| ROAD-004 | Workflow state machine (assigned → in_progress → resolved) | G3-04 | То же |
| ROAD-005 | Queue discipline (FIFO vs SLA-driven vs balanced) | G3-06 | 10+ операторов |
| ROAD-006 | Team roles + RBAC (owner/manager/operator) | G3-07, BL-POST-005 | Seller с 3+ людьми |

### 3.2 Intelligence Upgrade

| ID | Задача | Gap ID | Trigger |
|----|--------|--------|---------|
| ROAD-007 | Knowledge base (FAQ, sizing tables, policies) | G2-03 | Accept rate <70% при 50+ sellers |
| ROAD-008 | RAG for AI drafts (vector DB, few-shot) | G4-04 | То же |
| ROAD-009 | Draft confidence scoring (UI: "уверенность AI") | G4-02 | Seller жалуется на качество drafts |
| ROAD-010 | A/B testing промптов | G4-03 | 100+ sellers, нужна оптимизация |
| ROAD-011 | Learning loop (seller edits → система учится) | G4-05 | 1000+ одобренных ответов |
| ROAD-012 | Guardrails phrases в DB (runtime update) | G4-06 | Seller хочет свои banned phrases |

### 3.3 Analytics & Scale

| ID | Задача | Gap ID | Trigger |
|----|--------|--------|---------|
| ROAD-013 | External warehouse (ClickHouse/BigQuery) | G5-02 | 10M+ interactions |
| ROAD-014 | Period comparison ("этот месяц vs прошлый") | G5-03 | Seller с 3+ месяцами данных |
| ROAD-015 | A/B experiment tracking (версии промптов + метрики) | G5-05 | 100+ sellers |
| ROAD-016 | Customer sentiment history (тренд настроения по клиенту) | G2-05 | Customer profile ready (MVP-007) |
| ROAD-017 | Linking thresholds в RuntimeSetting | G2-04 | A/B тестирование линковки |

### 3.4 Platform

| ID | Задача | Gap ID | Trigger |
|----|--------|--------|---------|
| ROAD-018 | Webhooks вместо polling | G1-05, BL-POST-003 | WB API поддержит webhooks |
| ROAD-019 | Plugin system (connector registry) | G1-03 | 3+ marketplaces |
| ROAD-020 | Mobile PWA | BL-POST-006 | Seller просит mobile |
| ROAD-021 | Table partitioning (Interaction по channel или seller_id) | arch.md §11 | 5M+ строк |

### 3.5 Scalability Triggers (из architecture.md §11)

| Строк | Что делать |
|-------|-----------|
| < 5M | Ничего. PostgreSQL справляется. |
| 5-15M | Table partitioning (channel или seller_id) + text в отдельную таблицу |
| 50M+ | CQRS + архивация 12мес + read replicas |

---

## Execution History

| Дата | Кто | Что |
|------|-----|-----|
| Feb 11-13 | Codex | Unified model, WB connectors, ingestion, linking, API, SLA, tests |
| Feb 13 | Codex | Settings, Promo, Analytics, 3x QA runs (GO) |
| Feb 14 | Claude | Code review, handoff, Alembic, guardrails (37 tests), contract tests (23), 7 pilot задач (87 тестов) |
| Feb 15 | Claude | Staging deploy, 249 tests GREEN, smoke test, source labeling, demo data, E2E Playwright, frontend prod deploy |
| Feb 14 | Claude | Consolidated GUARDRAILS.md, 5-layer architecture.md, docs-home.html update + deploy |

---

## Related Docs

| Документ | Что |
|----------|-----|
| `docs/architecture/architecture.md` | 5-Layer Architecture + Gap Analysis + Scalability |
| `docs/GUARDRAILS.md` | Единые guardrails (content + safety + action + audit) |
| `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` | Execution log 8-week plan |
| `docs/product/BACKLOG_UNIFIED_COMM_V3.md` | Legacy backlog (detail per task) |
| `docs/product/PILOT_QA_MATRIX_AND_GONOGO_CHECKLIST.md` | QA матрица + Go/No-Go |
| `docs/SLA_RULES.md` | SLA правила с обоснованием |
