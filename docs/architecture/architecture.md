# AgentIQ — Архитектура: 5-Layer Model

**Last updated:** 2026-02-14
**Status:** implemented (partial) — validated against codebase

## Содержание

1. [Overview](#1-overview)
2. [Five Layers](#2-five-layers)
3. [Layer 1: Ingestion](#3-layer-1-ingestion)
4. [Layer 2: Context](#4-layer-2-context)
5. [Layer 3: Orchestration](#5-layer-3-orchestration)
6. [Layer 4: Intelligence](#6-layer-4-intelligence)
7. [Layer 5: Analytics](#7-layer-5-analytics)
8. [Cross-Cutting Concerns](#8-cross-cutting-concerns)
9. [Gap Analysis & Roadmap](#9-gap-analysis--roadmap)
10. [Source Files Map](#10-source-files-map)
11. [Scalability: Single-Table Model](#11-scalability-single-table-interaction-model)

---

## 1. Overview

AgentIQ построен на 5 слоях, каждый из которых решает одну задачу. Принцип: **новый канал = новый коннектор**, а не переписывание системы.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        5. ANALYTICS LAYER                           │
│   Метрики качества, SLA compliance, ops alerts, pilot readiness     │
├─────────────────────────────────────────────────────────────────────┤
│                     4. INTELLIGENCE LAYER                           │
│   AI drafts, guardrails, intent classification, safety policies     │
├─────────────────────────────────────────────────────────────────────┤
│                     3. ORCHESTRATION LAYER                          │
│   Маршрутизация, приоритеты, SLA, workflow, escalation              │
├─────────────────────────────────────────────────────────────────────┤
│                       2. CONTEXT LAYER                              │
│   Linking (det/prob), timeline, customer memory, product knowledge   │
├─────────────────────────────────────────────────────────────────────┤
│                       1. INGESTION LAYER                            │
│   WB reviews, WB questions, WB chats, Ozon chats, [email], [TG]    │
├─────────────────────────────────────────────────────────────────────┤
│                    UNIFIED DATA: Interaction                        │
│   channel-agnostic model, single table, all channels converge here  │
└─────────────────────────────────────────────────────────────────────┘
```

**Ключевой актив:** модель `Interaction` — channel-agnostic, marketplace-agnostic. Все каналы нормализуются в одну таблицу. Это позволяет добавлять email/Telegram/Ozon reviews как "просто новый источник".

---

## 2. Five Layers — Summary

| # | Layer | Что делает | Готовность | Главный gap |
|---|-------|-----------|------------|-------------|
| 1 | **Ingestion** | Сбор из всех каналов → `Interaction` | 85% | Нет BaseConnector interface |
| 2 | **Context** | Память о клиенте, связки, товарный контекст | 40% | Нет Customer profile, Product cache |
| 3 | **Orchestration** | Кто и как отвечает (routing, priority, SLA) | 25% | Нет маршрутизации, escalation, workflow DSL |
| 4 | **Intelligence** | AI + правила (drafts, guardrails, analysis) | 75% | Нет template DB, draft confidence |
| 5 | **Analytics** | Влияние на бизнес (quality, ops, readiness) | 70% | Нет revenue model, external warehouse |

---

## 3. Layer 1: Ingestion

### Что реализовано

Три WB-коннектора + Ozon chats. Все сходятся в `Interaction`:

| Коннектор | Файл | Каналы | API |
|-----------|------|--------|-----|
| WB Feedbacks | `wb_feedbacks_connector.py` | review | WB Feedbacks API |
| WB Questions | `wb_questions_connector.py` | question | WB Questions API |
| WB Chat | `wb_connector.py` | chat | WB Chat Events API |
| Ozon Chat | `ozon_connector.py` | chat | Ozon Chat API |

**Оркестратор:** `interaction_ingest.py` (936 строк) — incremental sync, watermark persistence, rate limiting (0.5s inter-page), dedup по `external_id`.

**Channels enum:** `review | question | chat` — не отдельные code paths, а field в unified таблице.

**Celery beat:** `sync_all_sellers()` каждые 30 сек → per-seller sync всех каналов последовательно.

### Gaps (будущее)

| Gap | Описание | Приоритет | Решение |
|-----|----------|-----------|---------|
| **G1-01** | Нет `BaseConnector` interface | medium | Abstract class с методами `list()`, `send()`, `mark_read()` |
| **G1-02** | Marketplace dispatch хардкожен в `sync.py` | medium | Factory/registry pattern по `seller.marketplace` |
| **G1-03** | Нет plugin system | low | Connector registry: `register_connector("email", EmailConnector)` |
| **G1-04** | Ozon reviews/questions не подключены | medium | Добавить коннекторы по аналогии с WB |
| **G1-05** | Нет webhook support | low | WB/Ozon пока не дают webhooks, polling достаточно |

### Как добавить email

```
1. Написать EmailConnector (IMAP/SMTP или API)
2. Добавить channel="email" в Interaction enum
3. Написать ingest_email_to_interactions() по аналогии с reviews
4. Зарегистрировать в sync.py dispatch
5. Guardrails автоматически применятся (default = strictest)
```

---

## 4. Layer 2: Context

### Что реализовано

**Cross-channel linking** (`interaction_linking.py`, 522 строки):
- Deterministic: `order_id` (0.99), `customer_id` (0.95), `nm_id+window` (0.82), `article+window` (0.78)
- Probabilistic: name match, semantic overlap, time proximity
- Timeline: `get_deterministic_thread_timeline()` — cross-channel история по заказу/клиенту
- Policy: auto-action only for deterministic + confidence >= 0.85

**Identity keys в Interaction:** `customer_id`, `order_id`, `nm_id`, `product_article`.

### Gaps (будущее)

| Gap | Описание | Приоритет | Решение |
|-----|----------|-----------|---------|
| **G2-01** | Нет таблицы `Customer` | high | Profile: name, total orders, avg rating, LTV, satisfaction trend |
| **G2-02** | Нет product cache | high | Таблица `Product`: nmId, name, specs, image. Sync с WB CDN card.json |
| **G2-03** | Нет knowledge base | medium | FAQ по товарам, политики возврата, sizing tables — для AI context |
| **G2-04** | Linking thresholds хардкожены | low | Вынести в `RuntimeSetting` для A/B тестирования |
| **G2-05** | Нет customer sentiment history | medium | Агрегация: "клиент писал 3 раза за месяц, настроение ухудшается" |

---

## 5. Layer 3: Orchestration

### Что реализовано

**Приоритеты** (в `interaction_ingest.py`):
- Reviews: `rating <= 2` → high
- Questions: intent-based SLA (compliance → urgent 60min, delivery → high 120min, general → normal 480min)
- Chats: `unread_count > 0` → high
- Age escalation: >24h old → urgent

**SLA rules:** модель `sla_rule.py` в БД (condition_type + deadline_minutes). Celery `check_sla_escalation()` каждые 5 мин.

**Chat lifecycle:** `waiting → responded → client-replied → closed`.

### Gaps (будущее) — САМЫЙ БОЛЬШОЙ СЛОЙ ДЛЯ ДОРАБОТКИ

| Gap | Описание | Приоритет | Решение |
|-----|----------|-----------|---------|
| **G3-01** | Нет маршрутизации | high | Routing engine: по seller team, skill, load balance |
| **G3-02** | Нет назначения на оператора | high | Assignment: auto-assign из queue, manual reassign |
| **G3-03** | Нет escalation workflow | high | Escalation rules: supervisor, другая команда, timeout → re-route |
| **G3-04** | Нет workflow state machine | medium | States: new → assigned → in_progress → waiting_customer → resolved → closed |
| **G3-05** | Priority thresholds хардкожены | medium | Вынести в DB: per-seller configurable SLA rules UI |
| **G3-06** | Нет queue discipline | medium | FIFO vs SLA-driven vs workload-balanced — configurable per seller |
| **G3-07** | Нет team/role model | medium | RBAC: owner → manager → operator, с разными полномочиями |

### Почему это ок сейчас

Текущий use case: **один seller = один оператор = одна очередь**. Routing не нужен. Когда seller вырастет до команды — включаем routing + assignment.

---

## 6. Layer 4: Intelligence

### Что реализовано

**AI Analyzer** (`ai_analyzer.py`, 700+ строк):
- LLM: DeepSeek Chat (configurable в DB через `llm_runtime.py`)
- Intents: 14 post-purchase + 4 pre-purchase
- Output: intent, sentiment, recommendation, draft reply
- Fallback: rule-based intent → LLM только если rule-based вернул `general_question`

**AI Draft Pipeline** (`interaction_drafts.py`):
```
generate_interaction_draft()
  → resolve chat/review/question context
  → call AI analyzer (or fallback)
  → apply guardrails
  → store in extra_data.last_ai_draft
```

**Guardrails** (`guardrails.py`, 338 строк):
- 4 категории banned phrases (ai_mention, promises, blame, dismissive)
- Channel-specific rules (review/question = strict, chat = relaxed)
- Pre-send validation: `validate_reply_text()` блокирует отправку при error-severity
- Полная документация: `docs/GUARDRAILS.md`

**Auto-Action Policy** (`interaction_linking.py`):
- deterministic + confidence >= 0.85 → auto allowed
- всё остальное → assist-only

### Gaps (будущее)

| Gap | Описание | Приоритет | Решение |
|-----|----------|-----------|---------|
| **G4-01** | Fallback шаблоны хардкожены в коде | medium | Template DB: per-intent, per-channel, per-seller |
| **G4-02** | Нет draft confidence scoring | medium | LLM возвращает confidence → UI показывает "уверенность AI" |
| **G4-03** | Нет A/B тестирования промптов | low | Experiment framework: два промпта → сравнить accept rate |
| **G4-04** | Нет RAG (knowledge base) | medium | Vector DB с успешными ответами → few-shot examples |
| **G4-05** | Нет learning loop | low | LearningAgent: seller edits draft → система учится |
| **G4-06** | Guardrails phrases в коде, не в DB | low | Вынести списки в `RuntimeSetting` для runtime обновления |

---

## 7. Layer 5: Analytics

### Что реализовано

**Event stream** (`interaction_metrics.py`, 865 строк):
- 6 event types: `draft_generated`, `draft_cache_hit`, `reply_sent`, `draft_accepted`, `draft_edited`, `reply_manual`
- Quality metrics: accept_rate, edit_rate, manual_rate (по каналам)
- Quality history: day-level trends (30 дней)
- Ops alerts: SLA overdue, quality regression, sync health
- Pilot readiness: go/no-go checklist

**Sync metrics** (`sync_metrics.py`, 300 строк):
- Ring buffer (10 entries) per seller/channel
- Health alerts: stale, errors, rate_limited, zero_fetch

**API endpoints:**
- `GET /interactions/quality-metrics`
- `GET /interactions/quality-history`
- `GET /interactions/ops-alerts`
- `GET /interactions/pilot-readiness`

### Gaps (будущее)

| Gap | Описание | Приоритет | Решение |
|-----|----------|-----------|---------|
| **G5-01** | Нет revenue impact | high | `loss_per_bad_reply = manual_rate × avg_order_value × conversion_drop` |
| **G5-02** | Нет external warehouse | low | ClickHouse/BigQuery для долгосрочной аналитики |
| **G5-03** | Нет сравнения периодов | medium | "Этот месяц vs прошлый" в UI |
| **G5-04** | Нет CSV/PDF экспорта | medium | Выгрузка метрик для seller |
| **G5-05** | Нет A/B experiment tracking | low | Версионирование промптов + метрики per-version |

---

## 8. Cross-Cutting Concerns

### Внутри каждого слоя должно быть:

| Concern | Где живёт сейчас | Статус |
|---------|-------------------|--------|
| **Маршрутизация** | Нет (single queue) | gap → Layer 3 |
| **Приоритеты** | `interaction_ingest.py` (hardcoded) | partial → externalize |
| **Правила** | `guardrails.py` + `GUARDRAILS.md` | implemented |
| **Guardrails** | `guardrails.py` + `interaction_linking.py` | implemented |
| **Логирование** | `interaction_metrics.py` + `sync_metrics.py` | implemented |
| **Аналитика** | `interaction_metrics.py` (quality + ops + readiness) | implemented |

### Audit Trail
Каждый AI-draft и reply логируется: timestamp, policy_version, confidence, violations, warnings, operator_edited. Подробнее: `docs/GUARDRAILS.md` секция 7.3.

### Multi-Marketplace
- `Interaction.marketplace` field (wb/ozon)
- Коннекторы marketplace-specific
- Бизнес-логика marketplace-agnostic (guardrails, analytics, linking)

---

## 9. Gap Analysis & Roadmap

### Priority Matrix

| ID | Gap | Layer | Impact | Effort | Priority |
|----|-----|-------|--------|--------|----------|
| G2-01 | Customer profile | Context | high | medium | **P1** |
| G2-02 | Product cache | Context | high | low | **P1** |
| G3-01 | Routing engine | Orchestration | high | high | **P2** (when team support needed) |
| G3-02 | Operator assignment | Orchestration | high | medium | **P2** |
| G5-01 | Revenue model | Analytics | high | low | **P1** |
| G4-01 | Template DB | Intelligence | medium | medium | **P2** |
| G1-01 | BaseConnector interface | Ingestion | medium | low | **P2** |
| G1-02 | Marketplace dispatch | Ingestion | medium | low | **P2** |
| G2-03 | Knowledge base (RAG) | Context | medium | high | **P3** |
| G3-03 | Escalation workflow | Orchestration | high | high | **P3** |
| G3-04 | Workflow state machine | Orchestration | medium | high | **P3** |
| G4-02 | Draft confidence | Intelligence | medium | medium | **P3** |
| G4-04 | RAG for drafts | Intelligence | medium | high | **P3** |
| G3-07 | Team roles (RBAC) | Orchestration | medium | medium | **P3** |

### Phase Plan

**Phase A (post-pilot, февраль-март 2026):**
- G2-01: Customer profile table
- G2-02: Product cache (WB CDN sync)
- G5-01: Revenue impact в analytics

**Phase B (масштабирование, апрель 2026):**
- G1-01 + G1-02: BaseConnector + factory dispatch
- G4-01: Template DB
- G1-04: Ozon reviews/questions

**Phase C (team support, когда sellers вырастут):**
- G3-01 + G3-02: Routing + assignment
- G3-03: Escalation
- G3-07: RBAC

**Phase D (intelligence upgrade):**
- G2-03 + G4-04: Knowledge base + RAG
- G4-02 + G4-03: Draft confidence + A/B testing
- G4-05: Learning loop

---

## 10. Source Files Map

### Layer 1: Ingestion
| File | Lines | What |
|------|-------|------|
| `services/interaction_ingest.py` | 936 | Core ingestion orchestrator |
| `services/wb_connector.py` | ~300 | WB Chat API connector |
| `services/wb_feedbacks_connector.py` | ~200 | WB Reviews API connector |
| `services/wb_questions_connector.py` | ~200 | WB Questions API connector |
| `services/ozon_connector.py` | ~150 | Ozon Chat API connector |
| `tasks/sync.py` | ~500 | Celery sync orchestration |
| `services/rate_limiter.py` | ~100 | Token bucket rate limiter |

### Layer 2: Context
| File | Lines | What |
|------|-------|------|
| `services/interaction_linking.py` | 522 | Cross-channel linking + auto-action policy |
| `models/interaction.py` | ~200 | Unified Interaction model |
| `models/interaction_event.py` | ~50 | Event stream model |

### Layer 3: Orchestration
| File | Lines | What |
|------|-------|------|
| `services/interaction_ingest.py` | (shared) | Priority assignment logic |
| `models/sla_rule.py` | ~50 | SLA rule model |
| `models/chat.py` | ~100 | Chat lifecycle (waiting/responded/closed) |
| `tasks/sync.py` | (shared) | SLA escalation check |

### Layer 4: Intelligence
| File | Lines | What |
|------|-------|------|
| `services/ai_analyzer.py` | ~700 | LLM analysis (intent, sentiment, draft) |
| `services/ai_question_analyzer.py` | ~200 | Question intent classifier |
| `services/interaction_drafts.py` | ~170 | Draft orchestrator |
| `services/guardrails.py` | 338 | Banned phrases, channel rules, validation |
| `services/llm_runtime.py` | ~100 | LLM provider config (DB-driven) |

### Layer 5: Analytics
| File | Lines | What |
|------|-------|------|
| `services/interaction_metrics.py` | 865 | Quality metrics, ops alerts, readiness |
| `services/sync_metrics.py` | ~300 | Sync health monitoring |
| `api/interactions.py` | (shared) | Analytics API endpoints |

### Docs
| File | What |
|------|------|
| `docs/GUARDRAILS.md` | Единая guardrails документация |
| `docs/architecture/architecture.md` | Этот документ |
| `docs/architecture/AGENTIQ_2.0_ARCHITECTURE.md` | Vision (post-PMF, multi-agent) |
| `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` | Execution log |
| `docs/product/BACKLOG_UNIFIED_COMM_V3.md` | Backlog с таймлайном |

---

## 11. Scalability: Single-Table Interaction Model

### Почему single table

Все каналы (review, question, chat) сходятся в одну таблицу `interactions`. Альтернатива — table-per-channel — добавляет JOIN/UNION в каждый запрос, каждый endpoint, каждый отчёт. На текущей стадии это неоправданная сложность.

### Текущая нагрузка

Средний WB-seller: ~200-500 отзывов/мес + ~100-300 вопросов + ~50-200 чатов = **~500-1000 interactions/мес**.

| Sellers | Строк/год | PostgreSQL | Проблемы |
|---------|-----------|------------|----------|
| 10 | ~120K | trivial | нет |
| 100 | ~1.2M | нормально | нет |
| 500 | ~6M | нормально | нет |
| 1000 | ~12M | терпимо | начинают проявляться |
| 5000+ | ~60M+ | нужна оптимизация | да |

### Известные узкие места (при росте)

**1. Индексы раздуваются.** 9 индексов на таблице (`__table_args__` в `interaction.py:63-81`). Каждый INSERT обновляет все 9. При bulk ingestion (1000 reviews за один sync) это заметно начиная с ~10M строк.

**2. JSON `extra_data` не индексируется.** `link_candidates`, `last_ai_draft`, channel-specific metadata — всё в JSON blob. Запросы вида `WHERE extra_data->>'field' = 'value'` делают seq scan. Пока объём мал — не критично, но не масштабируется.

**3. Смешанные query patterns.** Reviews фильтруются по `rating`, questions по intent (в `extra_data`), chats по `unread_count` (в отдельной таблице `chats`). Один набор индексов не покрывает все паттерны оптимально. Composite индекс `(seller_id, channel, status)` помогает, но при росте optimizer начнёт промахиваться.

**4. `Text` колонка в основной таблице.** Полный текст отзывов (до нескольких КБ) тянется при каждом list-запросе, даже если UI показывает только preview. Это widening rows и лишний I/O.

### План масштабирования (когда понадобится)

**Уровень 1 (~1-5M строк, ~100-500 sellers) — ничего не менять.**
PostgreSQL справляется. Текущие индексы достаточны. Мониторить `pg_stat_user_tables` (seq_scan vs idx_scan) и `pg_stat_user_indexes` (idx_scan count) для раннего обнаружения.

**Уровень 2 (~5-15M строк) — table partitioning + text separation:**

```sql
-- Вариант A: Partition по channel (3 партиции, разные query patterns)
CREATE TABLE interactions (
    ...
) PARTITION BY LIST (channel);

CREATE TABLE interactions_review PARTITION OF interactions FOR VALUES IN ('review');
CREATE TABLE interactions_question PARTITION OF interactions FOR VALUES IN ('question');
CREATE TABLE interactions_chat PARTITION OF interactions FOR VALUES IN ('chat');

-- Вариант B: Partition по seller_id range (если sellers сильно различаются по объёму)
CREATE TABLE interactions (
    ...
) PARTITION BY RANGE (seller_id);
```

```sql
-- Вынос text в отдельную таблицу (основная таблица становится лёгкой)
CREATE TABLE interaction_content (
    interaction_id INTEGER PRIMARY KEY REFERENCES interactions(id),
    text TEXT,
    extra_data JSONB
);
-- List-запросы не тянут text. Detail-запрос делает JOIN.
```

**Плюсы:** прозрачно для приложения (SQLAlchemy работает с partitioned tables без изменений). Индексы per-partition меньше. Vacuum быстрее.

**Уровень 3 (~50M+ строк, enterprise):**

- **CQRS:** write model = текущая `interactions`, read model = materialized views per-channel для dashboard и list-запросов. Refresh views через pg_cron или Celery.
- **Архивация:** interactions старше 12 мес → `interactions_archive` (отдельная таблица или холодный storage). Запросы к архиву — через explicit "показать архив" в UI.
- **Read replicas:** один PostgreSQL replica для аналитических запросов, master для OLTP.

### Что НЕ делать

- **Не переходить на table-per-channel** без крайней нужды. Это ломает главное преимущество — единый query для "все обращения seller'а отсортированные по приоритету". Каждый новый канал = новый UNION = комбинаторный взрыв в API.
- **Не переезжать на NoSQL** (MongoDB, DynamoDB) ради "масштабируемости". Structured data + relational queries + ACID транзакции (reply + event logging) — это exactly PostgreSQL.
- **Не оптимизировать заранее.** Партиционирование на 10K строках — overhead без пользы.

### Мониторинг (добавить сейчас)

Добавить в ops-alerts (`interaction_metrics.py`) проверку:
```python
# G-SCALE-01: Table bloat monitoring (future)
# SELECT pg_total_relation_size('interactions') → alert if > 1GB
# SELECT count(*) FROM interactions WHERE seller_id = X → alert if > 50K per seller
```

---

## Appendix A: Sierra.ai Reference

AgentIQ строится по модели Sierra.ai, адаптированной для РФ маркетплейсов. Детальное сравнение: `docs/architecture/AGENTIQ_2.0_ARCHITECTURE.md`.

| Sierra Module | AgentIQ Equivalent | Status |
|---------------|-------------------|--------|
| Agent OS / Orchestration | Layers 3+4 (Orchestration + Intelligence) | partial |
| Channels (chat, email, voice) | Layer 1 (Ingestion) — WB/Ozon | implemented |
| Memory | Layer 2 (Context) — linking, timeline | partial |
| Supervisors / Guardrails | Layer 4 — `guardrails.py` + `GUARDRAILS.md` | implemented |
| Insights | Layer 5 (Analytics) — metrics, alerts, readiness | implemented |
| Live Assist (copilot) | AI Drafts + operator approval | implemented |
| Agent Studio (no-code) | Not planned for v1 | future |
| Voice | Not planned | future |

---

_Этот документ описывает ТЕКУЩУЮ архитектуру (validated against code 2026-02-14) и БУДУЩИЕ планы. Для vision post-PMF см. `AGENTIQ_2.0_ARCHITECTURE.md`._
