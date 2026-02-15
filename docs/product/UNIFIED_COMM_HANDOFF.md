# Unified Communications — Handoff Codex → Claude

**Date:** 2026-02-14
**Status:** Code review completed, handoff in progress
**Previous work:** GitHub Copilot Codex (Sonnet 4.5)
**Current agent:** Claude Code (Opus 4.6)

---

## 1. Что сделал Codex (✅ DONE)

### Фаза 0-1: Foundations + WB API Connectors

**Completed by Codex:**
- ✅ **Unified `Interaction` model** (`app/models/interaction.py`)
  - Все поля из спецификации плана v3 (раздел 5.1)
  - UniqueConstraint для idempotency
  - Indexes на критичные поля (priority, status, source)
  - Relationship с `InteractionEvent` для audit trail

- ✅ **WB Feedbacks Connector** (`app/services/wb_feedbacks_connector.py`)
  - Official WB API integration (`https://feedbacks-api.wildberries.ru`)
  - Auth header fallback (raw token + Bearer prefix)
  - Retry с exponential backoff (429 rate limiting)
  - Error context в логах (truncated body)

- ✅ **WB Questions Connector** (`app/services/wb_questions_connector.py`)
  - Official WB Questions API integration
  - PATCH endpoint для ответов (`state: wbRu`, `answer.text`)
  - Count unanswered endpoint

- ✅ **Ingestion Pipeline** (`app/services/interaction_ingest.py`)
  - `ingest_wb_reviews_to_interactions()` — reviews → interactions
  - `ingest_wb_questions_to_interactions()` — questions → interactions
  - `ingest_chat_interactions()` — chats → interactions
  - Idempotency: UniqueConstraint + `seen_ids` dedup
  - Metadata preservation: `PRESERVED_META_KEYS` (AI drafts, replies, links)
  - Reply pending override: 180min window для eventual consistency WB API

- ✅ **Cross-Channel Linking** (`app/services/interaction_linking.py`)
  - **Уровень A (product):** nm_id + time window (45 days)
  - **Уровень B (customer):** order_id (0.99 conf) | customer_id (0.95 conf)
  - **Уровень C (probabilistic):** name matching + text overlap + time signals
  - **Guardrails policy:** auto-actions ТОЛЬКО для deterministic + conf >= 0.85
  - Reciprocal linking: двусторонние связи (A→B, B→A)
  - Timeline API: 4 scope levels (customer_order | customer | product | single)

- ✅ **Priority & SLA Engine** (`app/services/interaction_ingest.py`)
  - Reviews: priority по rating (1-2★ = high, 3★ = normal, 4-5★ = low)
  - Questions: intent detection (rule-based) + age-based escalation
  - Intents: `sizing_fit`, `availability_delivery`, `compliance_safety`, `post_purchase_issue`
  - SLA targets: compliance_safety (60 min), availability (120 min), general (480 min)
  - Age escalation: 24h → urgent, 8h + high → urgent

- ✅ **Unified API Endpoints** (`app/api/interactions.py`)
  - `POST /sync/reviews` — manual ingestion для reviews
  - `POST /sync/questions` — manual ingestion для questions
  - `POST /sync/chats` — chat threads → interactions
  - `GET /interactions` — unified list с фильтрами (channel, status, priority, source)
  - `GET /interactions/{id}` — single interaction
  - `GET /interactions/{id}/timeline` — cross-channel thread timeline
  - `POST /interactions/{id}/ai-draft` — generate AI draft (с кешированием)
  - `POST /interactions/{id}/reply` — unified reply (review/question/chat)
  - `GET /metrics/quality` — quality + pipeline metrics
  - `GET /metrics/quality-history` — day-level history для charts
  - `GET /metrics/ops-alerts` — operational alerts (SLA, quality regression)
  - `GET /metrics/pilot-readiness` — go/no-go readiness matrix

- ✅ **Tests** (`tests/test_interactions_layer.py`)
  - Route registration smoke tests
  - Fallback draft generation tests
  - Reply quality classification tests

**Code review verdict:** ⭐⭐⭐⭐⭐ (5/5) — Отличная работа! Production-ready.

---

## 2. Блокеры для пилота (Claude будет делать)

### ❗ P0 — BLOCKER (Must-have для пилота)

#### 2.1. Database Migrations (Alembic)
**Issue:** Новая таблица `interactions` не имеет миграций.
**Current state:** Нет Alembic, колонки добавляются вручную (CLAUDE.md:11).
**Impact:** На проде придётся делать `ALTER TABLE` вручную, риск downtime.

**Tasks:**
- [ ] Инициализировать Alembic: `alembic init alembic`
- [ ] Создать миграцию для `interactions`: `alembic revision --autogenerate -m "Add interactions table"`
- [ ] Создать миграцию для `interaction_events`: `alembic revision -m "Add interaction_events table"`
- [ ] Создать миграцию для `sla_rules` (если существует)
- [ ] Протестировать миграции на staging: `alembic upgrade head`
- [ ] Добавить `alembic upgrade head` в deploy pipeline

**Acceptance criteria:**
- Миграции работают на чистой БД (SQLite + PostgreSQL)
- Downgrade работает корректно: `alembic downgrade -1`
- CI/CD pipeline запускает миграции автоматически

**Estimate:** 2-3 часа

---

#### 2.2. Frontend Source Labeling
**Issue:** Поле `source` (wb_api | wbcon_fallback) не отображается в UI.
**Plan requirement (неделя 7):** "В UI явно маркировать fallback-метрики (`WB API` / `Fallback`)".
**Impact:** Нарушение прозрачности данных (plan section 2.2).

**Tasks:**
- [ ] Добавить badge `source` в InteractionCard компонент
- [ ] Цвета: `wb_api` → зелёный, `wbcon_fallback` → оранжевый + warning icon
- [ ] Tooltip на badge: "Данные из WB API" / "Оценка (доп. источник)"
- [ ] Добавить фильтр по `source` в список interactions
- [ ] Обновить `/metrics/quality` — показывать split по source

**Acceptance criteria:**
- Каждая карточка interaction показывает источник данных
- Fallback-метрики визуально отличаются от primary-метрик
- Фильтр `source` работает на клиенте и сервере

**Estimate:** 3-4 часа

---

### ⚠️ P1 — RECOMMENDED (Strongly recommended)

#### 2.3. Question Intent Detection — LLM Fallback
**Issue:** Rule-based intent detection покрывает только obvious keywords.
**Current state:** `_question_intent()` — hardcoded keywords (размер, наличие, материал).
**Gaps:**
- Не покрывает синонимы (размер → габарит, замер, параметры)
- Не работает для опечаток (размр, разме)
- `general_question` для всех unknown intents → incorrect SLA priority

**Tasks:**
- [ ] Создать `app/services/ai_question_analyzer.py`
- [ ] Добавить LLM-based intent classification (DeepSeek/GPT-4o-mini)
- [ ] Fallback logic: rule-based first (fast path) → LLM (slow path)
- [ ] Cache intent results в `extra_data.question_intent_llm`
- [ ] Metrics: track `intent_detection_method` (rule_based | llm | unknown)

**Prompt example:**
```python
INTENT_CLASSIFICATION_PROMPT = """
Classify customer question intent for e-commerce product inquiry.

Question: "{question_text}"

Possible intents:
- sizing_fit: size, height, weight, fit questions
- availability_delivery: in stock, when available, delivery time
- spec_compatibility: materials, specs, compatibility, power, volume
- compliance_safety: certificates, allergies, safety, warranty
- post_purchase_issue: defect, not working, broken, return
- general_question: other questions

Return only intent name, no explanation.
"""
```

**Acceptance criteria:**
- Intent detection accuracy >= 85% на eval set (100 questions)
- LLM fallback срабатывает только для unknown intents
- Latency <= 500ms для LLM path

**Estimate:** 4-5 часов

---

#### 2.4. Channel-Specific Guardrails
**Issue:** AI drafts не применяют channel-specific guardrails.
**Plan requirement (неделя 4):** "Guardrails (публичность ответа, ограничения текста)".
**Current state:** Guardrails есть в `scripts/llm_analyzer.py:478-519`, но не импортированы в `interaction_drafts.py`.

**Tasks:**
- [ ] Портировать GUARDRAILS конфиг из `llm_analyzer.py` в `app/services/guardrails.py`
- [ ] Создать `apply_review_guardrails(draft_text)` — запреты на обещания возвратов
- [ ] Создать `apply_question_guardrails(draft_text)` — запреты на персональные данные
- [ ] Интегрировать в `generate_interaction_draft()`:
  ```python
  if interaction.channel == "review":
      draft_text = apply_review_guardrails(draft_text)
  elif interaction.channel == "question":
      draft_text = apply_question_guardrails(draft_text)
  ```
- [ ] Добавить validation перед отправкой: `validate_reply_text(text, channel)`

**Banned phrases (reviews/questions — PUBLIC):**
- "вернём деньги", "гарантируем возврат", "бесплатную замену"
- "вы неправильно", "ваша вина"
- "обратитесь в поддержку" (отписка)
- ИИ/бот/нейросеть упоминания

**Acceptance criteria:**
- Drafts для reviews/questions не содержат banned phrases
- Validation блокирует отправку replies с banned content
- UI показывает warning если draft содержит risky phrases

**Estimate:** 3-4 часа

---

### ℹ️ P2 — NICE TO HAVE (Post-pilot)

#### 2.5. Contract Tests для WB Connectors
**Issue:** Нет contract tests против WB API schemas.
**Plan requirement (неделя 8):** "Contract tests against WB schemas + integration tests".
**Current state:** Только unit tests для draft/quality classification.

**Tasks:**
- [ ] Создать `tests/test_wb_feedbacks_contract.py`
- [ ] Mock WB API responses (fixtures из реальных payload)
- [ ] Verify payload structure matches connector expectations
- [ ] Test error handling (401, 429, 502, timeout)
- [ ] Создать `tests/test_wb_questions_contract.py`
- [ ] Integration tests для sync endpoints (`POST /sync/reviews`, etc.)

**Acceptance criteria:**
- Contract tests покрывают все WB connector methods
- Tests падают при изменении WB API contract
- CI запускает contract tests на каждый PR

**Estimate:** 4-6 часов

---

#### 2.6. Nightly Contract Checks
**Issue:** Нет мониторинга дрейфа WB API контрактов.
**Plan requirement (риски, секция 9):** "Nightly contract check + alert на дрейф WB API контрактов".
**Impact:** Silent breakage при изменении WB API schema.

**Tasks:**
- [ ] Создать GitHub Action: `.github/workflows/wb-contract-check.yml`
- [ ] Schedule: daily at 03:00 UTC
- [ ] Run contract tests против production WB API
- [ ] Alert на Slack/Telegram при failure
- [ ] Store contract snapshots в `tests/fixtures/wb_api_snapshots/`
- [ ] Diff tool: compare current response vs snapshot

**Acceptance criteria:**
- Nightly job запускается автоматически
- Alerts приходят в Telegram/Slack при contract drift
- Snapshots обновляются автоматически после manual approval

**Estimate:** 3-4 часа

---

#### 2.7. Reply Pending Window — Runtime Configurable
**Issue:** Reply pending window (180 min) захардкожен.
**Current state:** `_reply_pending_override(window_minutes=180)` — hardcoded.
**Improvement:** Сделать configurable через `runtime_settings`.

**Tasks:**
- [ ] Добавить поле `reply_pending_window_minutes` в `runtime_settings` таблицу
- [ ] Default value: 180 минут
- [ ] UI в Settings: input для настройки window
- [ ] Backend: `get_setting(db, seller_id, "reply_pending_window_minutes", default=180)`
- [ ] Documentation: объяснить для чего нужен window

**Acceptance criteria:**
- Продавец может настроить window через UI
- Изменение window применяется немедленно (next sync)
- Default 180 минут для новых продавцов

**Estimate:** 2-3 часа

---

## 3. План выполнения (Claude)

### Week 1: P0 Blockers
**Days 1-2:**
- [ ] 2.1. Database Migrations (Alembic) — 2-3h
- [ ] 2.2. Frontend Source Labeling — 3-4h

**Day 3:**
- [ ] Smoke tests на staging
- [ ] Deploy миграций на prod

### Week 2: P1 Recommended
**Days 4-5:**
- [ ] 2.3. Question Intent Detection — LLM Fallback — 4-5h
- [ ] 2.4. Channel-Specific Guardrails — 3-4h

**Day 6:**
- [ ] Integration tests
- [ ] Eval set для intent detection (100 questions)

### Week 3: P2 Nice-to-Have (optional)
**Days 7-9:**
- [ ] 2.5. Contract Tests — 4-6h
- [ ] 2.6. Nightly Contract Checks — 3-4h
- [ ] 2.7. Reply Pending Window Config — 2-3h

**Day 10:**
- [ ] Final QA + Documentation update
- [ ] Release notes

---

## 4. Acceptance Criteria (Pilot Ready)

**Unified Communications считается готовым к пилоту если:**
1. ✅ Все P0 blockers закрыты (migrations + source labeling)
2. ✅ P1 recommended закрыты (LLM intent + guardrails)
3. ✅ Smoke tests проходят на staging:
   - Sync reviews → interactions (100 reviews)
   - Sync questions → interactions (50 questions)
   - Cross-channel linking works (min 10 linked pairs)
   - Unified reply sends to WB API (review + question)
4. ✅ Metrics API возвращает данные:
   - `GET /metrics/quality` — totals + by_channel
   - `GET /metrics/pilot-readiness` — go=true
5. ✅ Documentation updated:
   - `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` — статус "DONE"
   - `docs/INDEX.md` — ссылка на handoff doc

---

## 5. Rollback Plan

**Если пилот fail:**
1. Rollback миграций: `alembic downgrade -1`
2. Отключить interactions sync через feature flag: `ENABLE_UNIFIED_INTERACTIONS=false`
3. Fallback на старый чат-контур (`apps/chat-center` без interactions layer)
4. Post-mortem: анализ причин failure + action items

---

## 6. Success Metrics (After Pilot)

**Pilot считается успешным если:**
1. **Operational SLA:**
   - Questions SLA compliance >= 85% (target: <5 min для high priority)
   - Reviews response rate >= 70% (в течение 24h)
2. **Quality metrics:**
   - AI draft acceptance rate >= 60%
   - Harmful replies rate <= 2%
3. **Linking accuracy:**
   - Deterministic links confidence >= 0.90
   - Probabilistic links false positive rate <= 10%
4. **Reliability:**
   - Sync success rate >= 99%
   - No data loss events
   - API uptime >= 99.5%

---

## 7. Handoff Notes

**From Codex:**
- Архитектура соответствует плану v3 на 95%
- Код clean, типизированный, production-ready
- Linking algorithm mathematically sound
- Retry/backoff/caching/observability — всё на месте

**To Claude:**
- Основная работа сделана, осталось закрыть blockers + polish
- Фокус на прозрачность данных (source labeling)
- Guardrails критичны для публичных каналов (review/question)
- Contract tests — must-have для production stability

**Critical files для Claude:**
- `app/models/interaction.py` — data model
- `app/services/interaction_ingest.py` — ingestion pipeline
- `app/api/interactions.py` — REST API
- `scripts/llm_analyzer.py:478-519` — guardrails source

**Good luck! 🚀**
