# INBOX #7: Pre-генерация AI-черновиков при синхронизации

> Last updated: 2026-02-15
> Status: ПЛАН (не реализовано)
> Автор: исследование кодовой базы

---

## 1. Текущий flow (AS-IS)

### 1.1 Два параллельных мира: Chat (старый) vs Interactions (новый)

В системе существуют два механизма AI-анализа, работающих параллельно:

**A) Chat-модель (legacy, только channel=chat)**
- При синхронизации WB-чатов (`sync.py:_sync_wb`, строки 807-828) новые buyer-сообщения ставят задачу `analyze_chat_with_ai.delay(chat_id)`
- Также работает периодическая задача `analyze_pending_chats` (каждые 2 мин), которая находит чаты без `ai_analysis_json` и ставит их в очередь
- Результат пишется в `Chat.ai_analysis_json` + `Chat.ai_suggestion_text`
- Это **единственный канал**, где AI-анализ запускается автоматически при синхронизации

**B) Interaction-модель (unified, все каналы: review/question/chat)**
- AI-черновик генерируется **только по запросу пользователя** (on-demand)
- Frontend триггерит генерацию при клике на чат (`App.tsx:637-643`):
  ```typescript
  if (!chat.ai_suggestion_text && chat.unread_count > 0) {
    const draft = await interactionsApi.generateDraft(chat.id);
  }
  ```
- Это вызывает API `POST /interactions/{id}/ai-draft` -> `generate_interaction_draft()`
- Результат кэшируется в `interaction.extra_data["last_ai_draft"]`
- При повторном запросе без `force_regenerate` — возвращается кэш

### 1.2 Где теряется время

```
Пользователь кликает на interaction
        |
        v
Frontend: POST /interactions/{id}/ai-draft
        |
        v
Backend: generate_interaction_draft()
        |
        v
LLM API call (DeepSeek): ~2-5 секунд
        |
        v
Ответ пользователю
```

**Проблема:** пользователь видит задержку 2-5 секунд при открытии КАЖДОГО нового interaction.
При 50+ непрочитанных interactions в очереди — оператор тратит 100-250 секунд впустую на ожидание.

### 1.3 Текущее хранение AI-черновиков

| Модель | Поле | Формат |
|--------|------|--------|
| `Chat` | `ai_analysis_json` | JSON-строка: intent, sentiment, urgency, recommendation, sla_priority |
| `Chat` | `ai_suggestion_text` | Текст рекомендации (ready-to-send) |
| `Interaction` | `extra_data["last_ai_draft"]` | Dict: text, intent, sentiment, sla_priority, source, guardrail_warnings |

Ключевой момент: при ре-синхронизации `interaction_ingest.py` сохраняет `last_ai_draft` через `PRESERVED_META_KEYS` (строка 118-127), то есть кэш НЕ сбрасывается при обновлении interaction.

### 1.4 Инвалидация кэша

- **Chat-модель:** при новых buyer-сообщениях `ai_analysis_json` и `ai_suggestion_text` обнуляются (`sync.py:991-993`)
- **Interaction-модель:** кэш `last_ai_draft` сохраняется через `PRESERVED_META_KEYS` при ре-синхронизации, но может быть принудительно перезаписан через `force_regenerate=True`

---

## 2. Предлагаемый flow (TO-BE)

### 2.1 Архитектура: генерация при синхронизации

```
Celery Beat (каждые 5 мин)
        |
        v
sync_all_seller_interactions
        |
        v
sync_seller_interactions(seller_id)
    |-- ingest reviews  -> новые interactions
    |-- ingest questions -> новые interactions
    |-- ingest chats    -> новые interactions
        |
        v
[НОВОЕ] generate_pending_interaction_drafts.delay(seller_id)
        |
        v
Celery worker: batch-генерация AI-черновиков
    |-- Выбрать interactions без last_ai_draft
    |-- Приоритизировать: urgent > high > normal > low
    |-- Rate limit: макс N вызовов/мин
    |-- Для каждого: generate_interaction_draft() -> сохранить в extra_data
        |
        v
Пользователь открывает interaction -> черновик УЖЕ готов (0 секунд)
```

### 2.2 Когда НЕ генерировать

1. **Interaction.needs_response = False** — уже отвечено
2. **Interaction.status = "responded"** — закрыто
3. **extra_data["last_ai_draft"] уже есть** — кэш валиден
4. **LLM отключен в RuntimeSettings** — fallback или пропуск
5. **Interaction.text пустой** (только рейтинг без текста) — fallback-черновик достаточен

### 2.3 Когда ПЕРЕГЕНЕРИРОВАТЬ (инвалидация)

1. **Новое сообщение от покупателя** (channel=chat) — текущий контекст изменился
2. **Ручной force_regenerate** — оператор нажал "Обновить" в UI
3. **Изменился текст interaction** (редкий кейс при ре-синхронизации)

---

## 3. Детальная архитектура

### 3.1 Новая Celery-задача: `generate_pending_interaction_drafts`

**Файл:** `apps/chat-center/backend/app/tasks/sync.py`

```
@celery_app.task(name="app.tasks.sync.generate_pending_interaction_drafts")
def generate_pending_interaction_drafts(seller_id: int, batch_size: int = 20):
    """
    Post-sync task: генерация AI-черновиков для interactions без draft.
    Вызывается после sync_seller_interactions.
    """
```

**Логика:**
1. Выбрать interactions где:
   - `seller_id` = целевой продавец
   - `needs_response = True`
   - `status != "responded"`
   - `extra_data` не содержит `last_ai_draft` (или `last_ai_draft` = null)
2. Отсортировать по приоритету:
   - `priority = "urgent"` первым
   - `priority = "high"` вторым
   - `priority = "normal"` третьим
   - `priority = "low"` последним
   - Внутри приоритета: по `occurred_at DESC` (свежие первыми)
3. Ограничить `batch_size` (по умолчанию 20)
4. Для каждого interaction: вызвать `generate_interaction_draft()` и сохранить результат в `extra_data["last_ai_draft"]`
5. Между вызовами: пауза (rate limiting)

### 3.2 Rate Limiting стратегия

DeepSeek API лимиты и стоимость:
- ~$0.14/1M input tokens, ~$0.28/1M output tokens
- Один черновик: ~500 input + ~200 output tokens = ~$0.0001
- 100 черновиков/день = ~$0.01/день = ~$0.30/мес

**Ограничения в коде:**
- `MAX_DRAFTS_PER_SYNC_CYCLE = 20` — максимум за один цикл sync
- `DRAFT_DELAY_SECONDS = 1.0` — пауза между LLM-вызовами (≤60 RPM)
- `MAX_DAILY_DRAFTS_PER_SELLER = 200` — дневной лимит на продавца
- RuntimeSetting `ai_draft_pregenerate_enabled` — глобальный выключатель

**Счетчик дневного лимита:** через Redis ключ `draft_count:{seller_id}:{date}` с TTL 86400.

### 3.3 Очередь и приоритизация

```sql
SELECT id, priority, occurred_at
FROM interactions
WHERE seller_id = :seller_id
  AND needs_response = true
  AND status != 'responded'
  AND (
    extra_data IS NULL
    OR extra_data->>'last_ai_draft' IS NULL
    OR extra_data->'last_ai_draft' = 'null'::jsonb
  )
ORDER BY
  CASE priority
    WHEN 'urgent' THEN 0
    WHEN 'high'   THEN 1
    WHEN 'normal' THEN 2
    WHEN 'low'    THEN 3
  END,
  occurred_at DESC
LIMIT :batch_size
```

### 3.4 Хук в sync_seller_interactions

**Точка вставки:** `sync.py`, строка ~492, после `await db.commit()` в конце `_sync()`.

```python
# --- [НОВОЕ] Trigger AI draft pre-generation ---
if not channel_errors:
    generate_pending_interaction_drafts.delay(seller_id)
```

Важно: задача запускается **после** успешного коммита синхронизации, как отдельная Celery-задача, чтобы не замедлять сам sync.

### 3.5 Кэширование и инвалидация

**Кэш-хит:** если `extra_data["last_ai_draft"]` существует и содержит поле `"text"` — возвращать кэш.

**Инвалидация при новых сообщениях (channel=chat):**

В `_upsert_chat_and_messages()` (sync.py:990-993) уже есть:
```python
if new_buyer_messages > 0 and chat.ai_analysis_json is not None:
    chat.ai_analysis_json = None
    chat.ai_suggestion_text = None
```

Нужно добавить аналогичную логику в `interaction_ingest.py` для chat-interactions:
- Если interaction получил новое сообщение от buyer — очистить `extra_data["last_ai_draft"]`

**Content-hash подход (опциональный, Sprint 2):**

Добавить поле `extra_data["draft_content_hash"]` = SHA256(interaction.text + last_message_text).
При pre-generation: если hash совпадает — пропустить. Это предотвращает лишние LLM-вызовы когда текст не изменился.

---

## 4. Приоритизация interactions для генерации

### 4.1 Матрица приоритетов

| Приоритет | Каналы | SLA | Генерация |
|-----------|--------|-----|-----------|
| **urgent** | chat (defect, wrong_item) | <30 мин | Немедленно при sync |
| **high** | chat (pre-purchase, delivery), review (1-2 звезды), question (sizing) | <1 час | Первая волна batch |
| **normal** | review (3 звезды), question (общие) | <4 часа | Вторая волна |
| **low** | review (4-5 звезд, спасибо), chat (thanks) | <24 часа | Последняя волна |

### 4.2 Immediate vs Batch

- **Immediate (inline с sync):** `priority = "urgent"` — черновик генерируется прямо в sync pipeline (1-3 interactions максимум)
- **Batch (отложенная Celery-задача):** все остальные — через `generate_pending_interaction_drafts`

---

## 5. Sprint Breakdown

### Sprint 1: Основа pre-генерации (3-5 дней)

**Цель:** AI-черновики генерируются автоматически после каждого sync-цикла для interactions без draft.

**Задачи:**

1. **Новая Celery-задача `generate_pending_interaction_drafts`**
   - Файл: `apps/chat-center/backend/app/tasks/sync.py`
   - Логика: batch-выбор interactions без draft, сортировка по приоритету, последовательная генерация
   - Rate limit: пауза между вызовами, batch_size лимит
   - Error handling: при ошибке LLM — fallback_draft, не прерывать batch

2. **Хук в `sync_seller_interactions`**
   - Файл: `apps/chat-center/backend/app/tasks/sync.py`
   - Вставка: `.delay()` после успешного sync commit
   - Guard: не вызывать при channel_errors

3. **RuntimeSetting для управления**
   - Ключ: `ai_draft_pregenerate_enabled` (default: "true")
   - Ключ: `ai_draft_batch_size` (default: "20")
   - Ключ: `ai_draft_delay_seconds` (default: "1.0")
   - Файл: `apps/chat-center/backend/app/services/llm_runtime.py` — добавить функцию загрузки настроек

4. **Celery Beat (периодическая страховочная задача)**
   - Файл: `apps/chat-center/backend/app/tasks/__init__.py`
   - Новая beat-задача: `generate-all-pending-drafts-every-10min` (на случай если sync не триггернул)
   - Schedule: каждые 10 минут

5. **Тесты**
   - Файл: `apps/chat-center/backend/tests/test_draft_pregeneration.py`
   - Unit: mock LLM, проверить batch-размер, порядок приоритетов, rate limiting
   - Integration: полный flow sync -> draft generation

**Файлы для модификации:**
- `apps/chat-center/backend/app/tasks/sync.py` — новая задача + хук
- `apps/chat-center/backend/app/tasks/__init__.py` — beat_schedule
- `apps/chat-center/backend/app/services/llm_runtime.py` — настройки pre-generation
- `apps/chat-center/backend/tests/test_draft_pregeneration.py` — новый тест

---

### Sprint 2: Инвалидация и оптимизация (2-3 дня)

**Цель:** черновики инвалидируются при изменении контекста, дневной лимит, content-hash.

**Задачи:**

1. **Инвалидация draft при новых сообщениях**
   - Файл: `apps/chat-center/backend/app/services/interaction_ingest.py`
   - При обновлении chat-interaction с новым buyer-сообщением: удалить `extra_data["last_ai_draft"]`
   - Также удалить `extra_data["draft_content_hash"]`

2. **Content-hash для предотвращения повторной генерации**
   - Файл: `apps/chat-center/backend/app/services/interaction_drafts.py`
   - Перед генерацией: вычислить hash текста interaction
   - Сравнить с `extra_data["draft_content_hash"]`
   - Если совпадает — пропустить (draft актуален)

3. **Дневной лимит через Redis**
   - Файл: `apps/chat-center/backend/app/services/rate_limiter.py`
   - Функция: `check_daily_draft_limit(seller_id) -> bool`
   - Redis key: `draft_count:{seller_id}:{YYYY-MM-DD}`, INCR + TTL 86400

4. **Immediate-генерация для urgent**
   - Файл: `apps/chat-center/backend/app/tasks/sync.py`
   - При инвалидации draft для urgent/high interactions: вызывать `generate_interaction_draft()` inline (без batch)
   - Лимит: не более 3 inline-генераций за sync-цикл

5. **Observability: метрики pre-генерации**
   - Файл: `apps/chat-center/backend/app/services/sync_metrics.py`
   - Добавить: `drafts_generated`, `drafts_cached`, `drafts_failed`, `draft_generation_time_ms`
   - Логировать в structured log

**Файлы для модификации:**
- `apps/chat-center/backend/app/services/interaction_ingest.py` — инвалидация
- `apps/chat-center/backend/app/services/interaction_drafts.py` — content-hash
- `apps/chat-center/backend/app/services/rate_limiter.py` — дневной лимит
- `apps/chat-center/backend/app/tasks/sync.py` — inline urgent drafts
- `apps/chat-center/backend/app/services/sync_metrics.py` — метрики

---

### Sprint 3: Frontend UX и fallback (1-2 дня)

**Цель:** frontend мгновенно показывает pre-generated draft, graceful degradation если draft не готов.

**Задачи:**

1. **Убрать on-click генерацию для interactions с готовым draft**
   - Файл: `apps/chat-center/frontend/src/App.tsx`
   - В `handleSelectChat`: если `chat.ai_suggestion_text` уже есть — не вызывать `generateDraft`
   - Текущий код (строка 637) уже делает эту проверку, но можно убрать задержку на показ

2. **Loading state для draft-in-progress**
   - Файл: `apps/chat-center/frontend/src/components/ChatWindow.tsx`
   - Если draft ещё не готов (null) и interaction.needs_response — показать skeleton/spinner
   - Текст: "AI готовит рекомендацию..." (вместо пустоты)

3. **Индикатор "pre-generated" vs "on-demand"**
   - Файл: `apps/chat-center/frontend/src/components/ChatWindow.tsx`
   - Опциональный badge "Готово заранее" если draft.source = "llm" и был в кэше
   - UX-сигнал оператору что система работает проактивно

4. **Fallback: если pre-generation не успела**
   - Сохранить текущую on-demand логику как fallback
   - Если при открытии interaction draft = null — генерировать по клику (текущее поведение)

**Файлы для модификации:**
- `apps/chat-center/frontend/src/App.tsx` — оптимизация handleSelectChat
- `apps/chat-center/frontend/src/components/ChatWindow.tsx` — loading state, badge

---

## 6. Полный список файлов для модификации

### Backend (обязательные)

| Файл | Изменение |
|------|-----------|
| `apps/chat-center/backend/app/tasks/sync.py` | Новая задача `generate_pending_interaction_drafts`, хук в `sync_seller_interactions`, inline urgent drafts |
| `apps/chat-center/backend/app/tasks/__init__.py` | Новая beat-задача в `beat_schedule` |
| `apps/chat-center/backend/app/services/llm_runtime.py` | Настройки pre-generation (batch_size, delay, enabled) |
| `apps/chat-center/backend/app/services/interaction_ingest.py` | Инвалидация `last_ai_draft` при новых buyer-сообщениях |
| `apps/chat-center/backend/app/services/interaction_drafts.py` | Content-hash, batch-safe генерация |
| `apps/chat-center/backend/app/services/rate_limiter.py` | Дневной лимит через Redis |
| `apps/chat-center/backend/app/services/sync_metrics.py` | Метрики draft-генерации |

### Frontend (опциональные, Sprint 3)

| Файл | Изменение |
|------|-----------|
| `apps/chat-center/frontend/src/App.tsx` | Оптимизация `handleSelectChat` |
| `apps/chat-center/frontend/src/components/ChatWindow.tsx` | Loading state для draft |

### Тесты (обязательные)

| Файл | Содержание |
|------|-----------|
| `apps/chat-center/backend/tests/test_draft_pregeneration.py` | Batch-генерация, приоритизация, rate limiting, инвалидация |

---

## 7. Риски и mitigation

| Риск | Вероятность | Последствие | Mitigation |
|------|------------|-------------|------------|
| LLM API rate limit | Средняя | Часть черновиков не сгенерируется | Pause между вызовами + fallback_draft + on-demand fallback |
| Высокая стоимость API | Низкая | Рост расходов при масштабировании | Дневной лимит + RuntimeSetting выключатель + content-hash |
| Celery worker перегрузка | Средняя | Задержка sync | Отдельная задача с низким приоритетом, batch_size лимит |
| Stale drafts | Средняя | Неактуальная рекомендация | Инвалидация при новых сообщениях + content-hash |
| DeepSeek downtime | Низкая | Нет черновиков | fallback_draft (keyword-based) всегда доступен |

---

## 8. Метрики успеха

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| Время до показа AI-рекомендации при клике | 2-5 сек | <100 мс (из кэша) |
| % interactions с ready draft при открытии | 0% | >80% для urgent/high |
| Среднее время обработки одного interaction оператором | ~15 сек | ~8 сек |
| LLM API стоимость / день | ~$0 (on-demand) | ~$0.01-0.05 (pre-generated) |

---

## 9. Связь с существующими механизмами

### analyze_pending_chats (уже существует)

Задача `analyze_pending_chats` (`sync.py:1300-1338`) уже делает похожую работу для Chat-модели:
- Каждые 2 минуты ищет чаты без `ai_analysis_json`
- Ставит их в очередь `analyze_chat_with_ai.delay()`

Разница с предлагаемым решением:
- `analyze_pending_chats` работает только с Chat-моделью (не с Interactions)
- Не имеет приоритизации
- Не имеет rate limiting
- Не имеет инвалидации

**Рекомендация:** после реализации pre-generation для Interactions, `analyze_pending_chats` можно deprecate, переведя всю логику на unified Interaction-модель.

### analyze_chat_with_ai (уже существует)

Задача `analyze_chat_with_ai` (`sync.py:1259-1297`) вызывается inline при sync WB-чатов.
Она пишет результат в `Chat.ai_analysis_json` и `Chat.ai_suggestion_text`.

**Взаимодействие:** pre-generation для Interactions вызывает `generate_interaction_draft()`, который для `channel=chat` внутри вызывает `analyze_chat_for_db()` — ту же логику. Дублирования не будет, потому что Chat-модель и Interaction-модель хранят draft в разных местах, а frontend читает из Interaction (unified).
