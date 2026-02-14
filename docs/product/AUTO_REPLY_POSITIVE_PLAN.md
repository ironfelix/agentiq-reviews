# INBOX #10: Авто-ответы на позитивные отзывы (BL-POST-007)

**Last updated:** 2026-02-15
**Status:** plan (не реализовано)
**Автор:** Claude (research + plan)
**Связанный backlog:** `BL-POST-007: Auto-response mode` в `BACKLOG_UNIFIED_COMM_V3.md`
**Оценка:** 2-3 спринта (6-9 дней)

---

## Оглавление

1. [User Story](#1-user-story)
2. [Текущее состояние кодовой базы](#2-текущее-состояние-кодовой-базы)
3. [Архитектура решения](#3-архитектура-решения)
4. [Safety & Guardrails](#4-safety--guardrails)
5. [Шаблоны vs LLM: сравнение и рекомендация](#5-шаблоны-vs-llm-сравнение-и-рекомендация)
6. [Settings UI](#6-settings-ui)
7. [WB API интеграция](#7-wb-api-интеграция)
8. [Rollback и отмена](#8-rollback-и-отмена)
9. [Sprint Breakdown](#9-sprint-breakdown)
10. [Анализ рисков](#10-анализ-рисков)
11. [Success Metrics](#11-success-metrics)

---

## 1. User Story

**Как продавец на WB**, я хочу настроить автоматические ответы на позитивные отзывы (4-5 звёзд), чтобы:
- Экономить время на рутинных благодарностях (70-80% отзывов на здоровом товаре — позитивные)
- Повышать response rate (метрика WB) без ручного труда
- Удерживать покупателей персонализированными ответами (имя, товар)
- Освободить оператора для работы с негативом и вопросами

### Acceptance Criteria

1. Продавец в Settings -> AI-ассистент настраивает:
   - Включение/выключение авто-ответов (toggle, сейчас уже есть как `auto_replies_positive`)
   - Минимальная оценка для авто-ответа (4★ или 5★, slider/select)
   - Задержка перед отправкой (0-60 мин, чтобы успеть отменить)
   - Исключения: товары или категории, где авто-ответ нежелателен

2. Система при поступлении нового отзыва с `rating >= min_rating`:
   - Генерирует персонализированный черновик
   - Проверяет guardrails (pre-send validation)
   - Ставит в очередь на отправку с заданной задержкой
   - Отправляет через WB Feedbacks API
   - Логирует в audit trail

3. Оператор видит в Inbox:
   - Отзыв помечен как "Авто-ответ запланирован" (pending) или "Авто-ответ отправлен"
   - Может отменить запланированный авто-ответ до отправки
   - Может отредактировать и отправить вручную вместо авто-ответа

4. НИКОГДА не авто-отвечать на:
   - Отзывы с rating <= 3
   - Отзывы, содержащие жалобы/дефекты в тексте (даже при 4-5★)
   - Отзывы с escalation-триггерами (аллергия, контрафакт)
   - Отзывы без текста (пустые 5★) — опционально

---

## 2. Текущее состояние кодовой базы

### 2.1 Что уже есть

| Компонент | Файл | Что реализовано |
|-----------|------|-----------------|
| **Settings toggle** | `schemas/settings.py:54` | `auto_replies_positive: bool = False` в `AISettings` |
| **Frontend toggle** | `SettingsPage.tsx:243-258` | UI toggle "Авто-ответы на позитив" с пометкой "пока в режиме гипотезы" |
| **WB API метод** | `wb_feedbacks_connector.py:141-173` | `answer_feedback(feedback_id, text)` — готов, с retry и auth fallback |
| **Reply endpoint** | `api/interactions.py:506-675` | `POST /{id}/reply` — guardrails validation + dispatch по каналам |
| **Draft generation** | `interaction_drafts.py:48-169` | Fallback draft для review: различает rating <= 3 и 4-5★ |
| **Guardrails** | `guardrails.py:164-210` | `apply_review_guardrails()` — banned phrases, return trigger, length |
| **Pre-send validation** | `guardrails.py:294-338` | `validate_reply_text()` — блокирующая проверка перед отправкой |
| **Ingestion pipeline** | `interaction_ingest.py` | Новые отзывы попадают в `Interaction` с `rating`, `channel="review"` |
| **Rate limiter** | `rate_limiter.py` | Token-bucket (30 RPM/seller), per-seller sync lock |
| **Audit trail** | Описан в `GUARDRAILS.md:304-322` | Структура audit trail (пока не полностью реализована) |

### 2.2 Что НЕ реализовано (нужно добавить)

1. **Auto-reply scheduler** — нет механизма "запланировать отправку через N минут"
2. **Content analysis позитивных отзывов** — нет проверки текста 4-5★ на скрытые жалобы
3. **Расширенные настройки** — только toggle, нет min_rating / delay / exclusions
4. **Auto-reply queue** — нет очереди запланированных авто-ответов
5. **Cancel/override** — нет отмены запланированного авто-ответа
6. **Auto-reply audit** — нет отдельного логирования авто-ответов
7. **LLM prompt для позитива** — текущий `CHAT_ANALYSIS_SYSTEM` не оптимизирован для review-ответов

---

## 3. Архитектура решения

### 3.1 Общий flow

```
[Ingestion]              [Scheduler]              [Sender]
    |                        |                        |
    v                        v                        v
New review (4-5★)  -->  Check settings  -->  Generate draft  -->  Guardrails check
                              |                        |                   |
                         min_rating OK?           LLM/template       violations?
                         text analysis OK?             |                   |
                              |                        v              YES → abort
                              v                   Queue with delay         |
                         Schedule auto-reply           |              NO → send
                              |                   Wait N minutes          |
                              v                        |                  v
                         Mark "auto-pending"      Check not cancelled  WB API
                              |                        |                  |
                              v                        v                  v
                         Show in Inbox            Send reply         Mark "auto-responded"
```

### 3.2 Новые компоненты

#### 3.2.1 `AutoReplySettings` (расширение `AISettings`)

```python
class AutoReplyConfig(BaseModel):
    enabled: bool = False
    min_rating: int = Field(default=5, ge=4, le=5)  # 4 или 5
    delay_minutes: int = Field(default=15, ge=0, le=60)  # 0 = мгновенно
    skip_empty_text: bool = True  # Пропускать отзывы без текста
    excluded_nm_ids: list[int] = []  # Товары-исключения
    use_llm: bool = True  # True = LLM, False = шаблоны
    max_daily_count: int = Field(default=100, ge=1, le=500)  # Дневной лимит
```

#### 3.2.2 `AutoReplyScheduler` (новый сервис)

Celery task, вызывается из `interaction_ingest.py` при создании нового review:

```
auto_reply_check.delay(interaction_id)
```

Логика:
1. Проверить `auto_reply_config.enabled` для seller
2. Проверить `interaction.rating >= min_rating`
3. Проверить текст на скрытые жалобы (LLM или keyword analysis)
4. Генерировать черновик
5. Проверить guardrails
6. Если `delay_minutes > 0` — запланировать `auto_reply_send.apply_async(eta=...)`
7. Если `delay_minutes == 0` — отправить сразу

#### 3.2.3 `AutoReplyQueue` (модель или поле в Interaction)

Варианты хранения:
- **Вариант A:** Новая таблица `auto_reply_queue` (id, interaction_id, seller_id, draft_text, scheduled_at, status, sent_at)
- **Вариант B:** Поля в `Interaction.extra_data` (`auto_reply_status`, `auto_reply_draft`, `auto_reply_scheduled_at`)

**Рекомендация:** Вариант B (extra_data) — проще, не нужна миграция, достаточно для MVP. Вариант A — для масштабирования после пилота.

### 3.3 Интеграция с ingestion pipeline

Точка входа — `interaction_ingest.py`, после создания `Interaction` с `channel="review"`:

```python
# После db.flush() для нового review:
if interaction.channel == "review" and interaction.rating and interaction.rating >= 4:
    from app.tasks.auto_reply import schedule_auto_reply
    schedule_auto_reply.delay(interaction.id, seller_id)
```

---

## 4. Safety & Guardrails

### 4.1 Принцип "Never harm"

Авто-ответ на позитив — это low-risk действие, НО:
- Покупатель с 5★ может жаловаться в тексте ("Товар хороший, НО размер не подошёл")
- Шаблонный "Спасибо!" на сложный отзыв выглядит как бот-ответ
- Ошибка auto-reply на негатив = репутационная катастрофа

### 4.2 Многоуровневая защита

| Уровень | Проверка | Действие при fail |
|---------|----------|-------------------|
| **L1: Rating filter** | `rating >= min_rating (4 или 5)` | Skip (no auto-reply) |
| **L2: Text analysis** | Проверка текста на скрытые жалобы | Skip + flag для оператора |
| **L3: Escalation keywords** | Аллергия, контрафакт, угрозы, PII | Skip + escalate |
| **L4: Content guardrails** | Banned phrases в сгенерированном тексте | Block send |
| **L5: Pre-send validation** | `validate_reply_text()` — полная проверка | Block send |
| **L6: Daily limit** | `max_daily_count` per seller | Stop auto-replies до завтра |
| **L7: Human override** | Оператор отменил/отредактировал | Cancel auto-reply |

### 4.3 L2: Text analysis для скрытых жалоб

Позитивные отзывы (4-5★) с жалобами — частый кейс. Нужна проверка:

**Keyword-based (быстрый, без LLM):**
```python
NEGATIVE_SIGNALS_IN_POSITIVE = [
    "но", "однако", "к сожалению", "жаль", "минус",
    "не подошёл", "не подошел", "маленький", "большой",
    "запах", "дефект", "брак", "сломал", "не работает",
    "возврат", "вернуть", "замена", "обменять",
    "не соответствует", "не как на фото", "отличается",
    "разочарован", "ожидал другое", "качество хуже",
]
```

**LLM-based (точный, дороже):**
Вызов DeepSeek с промптом: "Содержит ли этот позитивный отзыв скрытые жалобы? Ответ: yes/no/reason"

**Рекомендация:** Начать с keyword-based (L2a), добавить LLM (L2b) во 2-м спринте.

### 4.4 Жёсткие правила (NEVER)

- **НИКОГДА** не авто-отвечать на rating <= 3 (даже если настройка сломалась — hardcode guard)
- **НИКОГДА** не авто-отвечать если текст содержит слова из `ESCALATION_KEYWORDS`
- **НИКОГДА** не отправлять если `validate_reply_text()` вернул `valid=False`
- **НИКОГДА** не авто-отвечать на уже отвеченный отзыв (`needs_response=False`)
- **НИКОГДА** не превышать `max_daily_count` (защита от loop/bug)
- **Hardcode ceiling:** `rating >= 4` — нельзя настроить авто-ответ для 3★ и ниже

---

## 5. Шаблоны vs LLM: сравнение и рекомендация

### 5.1 Сравнительная таблица

| Критерий | Шаблоны | LLM (DeepSeek) |
|----------|---------|----------------|
| **Скорость** | Мгновенно (<1ms) | 2-5 сек (API call) |
| **Стоимость** | Бесплатно | ~0.001-0.003$ за ответ |
| **Персонализация** | Низкая (имя + товар) | Высокая (контекст отзыва) |
| **Разнообразие** | 5-10 шаблонов (заметно повторяются) | Уникальный каждый раз |
| **Предсказуемость** | 100% (детерминированный) | ~95% (редко галлюцинации) |
| **Риск guardrail violation** | ~0% (проверены заранее) | ~2-5% (нужна валидация) |
| **Восприятие покупателем** | "Бот-ответ" через 20-30 отзывов | Естественный диалог |
| **Масштабируемость** | Неограниченная | Ограничена API rate limits |
| **Поддержка** | Легко (правки шаблонов) | Сложнее (промпт-инжиниринг) |

### 5.2 Шаблоны: примеры

```python
POSITIVE_REVIEW_TEMPLATES = [
    "{name}, спасибо за отзыв! Рады, что {product} понравился.",
    "{name}, благодарим за обратную связь! Будем рады видеть вас снова.",
    "{name}, спасибо за высокую оценку! Если будут вопросы по {product} — обращайтесь.",
    "Спасибо за отзыв! Приятно, что {product} оправдал ожидания.",
    "Благодарим за отзыв! Если будут вопросы — будем рады помочь.",
]
```

Проблема: WB покупатели быстро замечают одинаковые ответы у продавца. 5 шаблонов на 100 отзывов = каждый 20-й одинаковый.

### 5.3 LLM: пример промпта

```
Ты — менеджер по работе с отзывами на WB.
Напиши КОРОТКИЙ (2-3 предложения, max 200 символов) ответ на позитивный отзыв.

Правила:
- Поблагодари за отзыв
- Упомяни товар или то, что понравилось покупателю
- НЕ обещай скидки/возвраты/замены
- НЕ упоминай ИИ/бот/нейросеть
- НЕ используй "Уважаемый клиент"
- Каждый ответ УНИКАЛЬНЫЙ
- Если есть имя — начни с него

Товар: {product_name}
Имя покупателя: {customer_name}
Оценка: {rating}★
Текст отзыва: {review_text}
```

### 5.4 Рекомендация: гибридный подход

**Стратегия "LLM с fallback на шаблоны":**

1. **По умолчанию:** LLM генерация (DeepSeek, ~0.002$ за ответ)
2. **Fallback:** Если LLM недоступен/таймаут/ошибка → шаблон
3. **Настройка:** Продавец может выбрать "Только шаблоны" в Settings (для тех, кто не хочет LLM)

**Обоснование:**
- При 100 позитивных отзывах в месяц: LLM стоит ~0.20$ (пренебрежимо)
- Качество LLM-ответов значительно выше шаблонов
- Fallback гарантирует работоспособность при проблемах с API
- Guardrails валидация одинаково работает для обоих вариантов

---

## 6. Settings UI

### 6.1 Расположение

Настройки авто-ответов размещаются в таб **"AI-ассистент"** на странице Settings (`SettingsPage.tsx`).

Текущий toggle "Авто-ответы на позитив" (`auto_replies_positive`) расширяется до полноценной секции.

### 6.2 Макет секции

```
┌─────────────────────────────────────────────────────────┐
│  Авто-ответы на позитивные отзывы          [TOGGLE ON]  │
│  ───────────────────────────────────────────────────     │
│  AI автоматически отвечает на позитивные отзывы.        │
│  Вы можете отменить запланированный ответ в Inbox.      │
│                                                         │
│  Минимальная оценка                                     │
│  [4★] [5★]               <- pill select                 │
│                                                         │
│  Задержка перед отправкой                               │
│  [──●──────────] 15 мин  <- slider (0-60)               │
│  Время, чтобы проверить и отменить ответ                │
│                                                         │
│  Генерация ответов                                      │
│  (●) AI-генерация (уникальные ответы)                   │
│  ( ) Шаблоны (быстрее, предсказуемее)                   │
│                                                         │
│  Пропускать отзывы без текста         [TOGGLE ON]       │
│                                                         │
│  Дневной лимит                                          │
│  [───────●────] 100      <- slider (1-500)              │
│                                                         │
│  [Сохранить]                                            │
└─────────────────────────────────────────────────────────┘
```

### 6.3 Изменения в схемах

**`schemas/settings.py`** — расширить `AISettings`:

```python
class AutoReplyConfig(BaseModel):
    enabled: bool = False
    min_rating: int = Field(default=5, ge=4, le=5)
    delay_minutes: int = Field(default=15, ge=0, le=60)
    skip_empty_text: bool = True
    use_llm: bool = True
    max_daily_count: int = Field(default=100, ge=1, le=500)

class AISettings(BaseModel):
    tone: Tone = "friendly"
    auto_replies_positive: bool = False  # deprecated, migrate to auto_reply_config.enabled
    ai_suggestions: bool = True
    auto_reply_config: AutoReplyConfig = Field(default_factory=AutoReplyConfig)
```

### 6.4 Backend API

Существующие endpoints `GET/PUT /api/settings/ai` уже работают с `AISettings`. Расширение `AutoReplyConfig` как nested field не требует новых endpoints — Pydantic сериализует/десериализует автоматически.

---

## 7. WB API интеграция

### 7.1 Endpoint для отправки ответа

**Уже реализован** в `wb_feedbacks_connector.py:141-173`:

```python
async def answer_feedback(self, *, feedback_id: str, text: str) -> bool:
```

- Метод: `POST /api/v1/feedbacks/answer`
- Payload: `{"id": feedback_id, "text": text}`
- Auth: `Authorization: <token>` с retry на 401
- Success: HTTP 200/201/202/204

### 7.2 Rate Limits

Из документации WB API (`dev.wildberries.ru/docs/openapi/user-communication`):
- **Общий лимит:** ~60 запросов в минуту на все методы Feedbacks/Questions группы
- **В нашем коде:** `WB_RATE_LIMIT_RPM = 30` (консервативно)
- **Для авто-ответов:** нужно учитывать, что rate limiter делится между sync и reply

**Стратегия rate limiting для авто-ответов:**
1. Авто-ответы используют тот же `WBRateLimiter` (token-bucket)
2. Приоритет: sync > manual reply > auto-reply
3. При исчерпании бюджета: авто-ответ откладывается (retry через 60 сек)
4. Maximum burst: не более 5 авто-ответов подряд, затем пауза 10 сек

### 7.3 Особенности WB

- **Модерация:** WB модерирует ответы продавца. Отправленный ответ может быть отклонён модерацией
- **Повторный ответ:** Нельзя отправить второй ответ на тот же отзыв (WB вернёт ошибку)
- **Пустые отзывы:** Покупатель может оставить только оценку без текста — тогда `feedback_text` будет пустым
- **Идемпотентность:** Если отзыв уже отвечен (`is_answered=true`), повторная отправка вернёт ошибку

### 7.4 Проверка перед отправкой

```python
async def can_auto_reply(interaction: Interaction, db: AsyncSession) -> tuple[bool, str]:
    """Проверить, можно ли авто-ответить на этот отзыв."""

    # 1. Rating guard (hardcode)
    if not interaction.rating or interaction.rating < 4:
        return False, "rating_too_low"

    # 2. Already answered
    if not interaction.needs_response:
        return False, "already_answered"

    # 3. Status check
    if interaction.status == "responded":
        return False, "already_responded"

    # 4. Channel check
    if interaction.channel != "review":
        return False, "not_review_channel"

    # 5. Seller settings
    config = await get_auto_reply_config(interaction.seller_id, db)
    if not config.enabled:
        return False, "auto_reply_disabled"

    if interaction.rating < config.min_rating:
        return False, "below_min_rating"

    # 6. Daily limit
    today_count = await count_auto_replies_today(interaction.seller_id, db)
    if today_count >= config.max_daily_count:
        return False, "daily_limit_reached"

    # 7. Text analysis (hidden complaints)
    if has_negative_signals(interaction.text):
        return False, "negative_signals_detected"

    # 8. Escalation keywords
    if has_escalation_triggers(interaction.text):
        return False, "escalation_trigger"

    return True, "ok"
```

---

## 8. Rollback и отмена

### 8.1 Сценарии отмены

| Сценарий | Механизм | Результат |
|----------|----------|-----------|
| **Оператор отменяет до отправки** | Кнопка "Отменить авто-ответ" в Inbox | `auto_reply_status = "cancelled"`, задача Celery revoked |
| **Оператор редактирует** | Кнопка "Редактировать" в Inbox | Cancel auto-reply + открыть ручное редактирование |
| **Guardrails заблокировали** | Pre-send validation fail | `auto_reply_status = "blocked"`, notification оператору |
| **WB API ошибка** | HTTP error при отправке | `auto_reply_status = "failed"`, retry через 5 мин (max 3 раза) |
| **Продавец выключил auto-reply** | Toggle OFF в Settings | Все pending авто-ответы отменяются |

### 8.2 Celery task lifecycle

```
schedule_auto_reply(interaction_id)
    └─> auto_reply_check (immediate)
        ├─> FAIL: mark "skipped" + reason
        └─> OK: auto_reply_send.apply_async(
                    args=[interaction_id],
                    eta=now + delay_minutes,
                    task_id=f"auto-reply-{interaction_id}"  # для revoke
                )
                └─> auto_reply_send (delayed)
                    ├─> Re-check: still valid? not cancelled?
                    ├─> Generate draft (LLM/template)
                    ├─> Validate guardrails
                    ├─> Send via WB API
                    └─> Mark "sent" or "failed"
```

### 8.3 Отмена через UI

В карточке interaction в Inbox при `auto_reply_status = "pending"`:

```
┌──────────────────────────────────────────┐
│ ⏳ Авто-ответ запланирован на 14:35      │
│ "Спасибо за отзыв! Рады, что товар..."  │
│                                          │
│ [Отменить]  [Редактировать]  [Отправить] │
└──────────────────────────────────────────┘
```

Кнопка "Отменить":
```python
# Backend
from celery.result import AsyncResult
task = AsyncResult(f"auto-reply-{interaction_id}")
task.revoke(terminate=True)
interaction.extra_data["auto_reply_status"] = "cancelled"
```

### 8.4 Что делать, если авто-ответ уже отправлен и он неудачный?

WB не позволяет удалить ответ продавца. Варианты:
1. **Повторный ответ невозможен** — WB не поддерживает редактирование/удаление
2. **Минимизация риска** — задержка 15 мин по умолчанию, guardrails, text analysis
3. **Notification** — если обнаружен проблемный авто-ответ, оператор получает уведомление для ручного follow-up (через чат с покупателем, если доступен)

---

## 9. Sprint Breakdown

### Sprint 1: Backend Core (3-4 дня)

| Задача | Оценка | Файлы |
|--------|--------|-------|
| Расширить `AISettings` + `AutoReplyConfig` | 2h | `schemas/settings.py` |
| Создать `auto_reply.py` service (check, generate, send) | 4h | `app/services/auto_reply.py` |
| Celery tasks: `schedule_auto_reply`, `auto_reply_send` | 3h | `app/tasks/auto_reply.py` |
| Интеграция с ingestion pipeline (trigger точка) | 2h | `interaction_ingest.py` |
| Text analysis (keyword-based L2a) | 2h | `app/services/auto_reply.py` |
| LLM prompt для позитивных отзывов | 2h | `app/services/auto_reply.py` |
| Template fallback (5-7 шаблонов) | 1h | `app/services/auto_reply.py` |
| Тесты (unit + integration) | 4h | `tests/test_auto_reply.py` |
| **Итого Sprint 1** | **~20h (3 дня)** | |

### Sprint 2: Frontend + Cancel (2-3 дня)

| Задача | Оценка | Файлы |
|--------|--------|-------|
| Расширить Settings UI (min_rating, delay, mode) | 3h | `SettingsPage.tsx`, `types/index.ts` |
| Показать auto-reply status в InteractionCard | 2h | `ChatWindow.tsx` / `InteractionDetail.tsx` |
| Кнопки Cancel/Edit/Send now для pending auto-replies | 3h | `ChatWindow.tsx`, `api/interactions.py` |
| API endpoint: `POST /{id}/auto-reply/cancel` | 2h | `api/interactions.py` |
| Celery revoke интеграция | 1h | `tasks/auto_reply.py` |
| E2E тесты (Settings -> auto-reply -> cancel) | 3h | `e2e/` |
| **Итого Sprint 2** | **~14h (2 дня)** | |

### Sprint 3: Hardening + Monitoring (1-2 дня)

| Задача | Оценка | Файлы |
|--------|--------|-------|
| LLM text analysis (L2b) для скрытых жалоб | 3h | `app/services/auto_reply.py` |
| Audit trail для авто-ответов | 2h | `app/services/auto_reply.py` |
| Dashboard: авто-ответы в аналитике (счётчики, acceptance rate) | 3h | `interaction_metrics.py`, frontend |
| Monitoring: алерты если auto-reply failure rate > 5% | 2h | `sync_metrics.py` |
| Excluded nm_ids UI | 2h | `SettingsPage.tsx` |
| Нагрузочное тестирование (100 отзывов за 1 час) | 2h | `scripts/` |
| **Итого Sprint 3** | **~14h (2 дня)** | |

### Общий timeline: 6-9 рабочих дней

---

## 10. Анализ рисков

### 10.1 Матрица рисков

| # | Риск | Вероятность | Импакт | Митигация |
|---|------|-------------|--------|-----------|
| R1 | Авто-ответ на скрытую жалобу в 5★ отзыве | Средняя | Высокий | L2 text analysis + задержка 15 мин + cancel |
| R2 | WB модерация отклоняет авто-ответ | Низкая | Низкий | Логировать, уведомить оператора, retry не нужен |
| R3 | Rate limit WB API при массовой отправке | Средняя | Средний | Token-bucket limiter, burst limit 5, retry |
| R4 | LLM генерирует запрещённую фразу | Низкая | Высокий | Pre-send guardrails validation (blocking) |
| R5 | Покупатель воспринимает авто-ответ как бота | Средняя | Средний | LLM генерация (разнообразие), персонализация |
| R6 | Celery worker упал, задачи потерялись | Низкая | Средний | Celery persistent broker (Redis), retry on restart |
| R7 | Продавец включил авто-ответ и забыл | Низкая | Низкий | Daily limit, monthly report, notification |
| R8 | Double-send (авто + ручной на один отзыв) | Средняя | Средний | Check `needs_response` перед отправкой, lock |
| R9 | LLM API down, все авто-ответы fallback на шаблоны | Средняя | Низкий | Шаблоны как fallback, нотификация в dashboard |

### 10.2 Критические guard clauses (hardcode, не настраиваемые)

```python
# Эти проверки НЕЛЬЗЯ отключить через настройки:
assert interaction.rating >= 4, "Never auto-reply to < 4 stars"
assert interaction.channel == "review", "Only reviews channel"
assert interaction.needs_response, "Already answered"
assert not has_escalation_triggers(text), "Escalation required"
assert validate_reply_text(draft, "review", text)["valid"], "Guardrails block"
```

### 10.3 Worst case scenario

**Сценарий:** Баг в коде → авто-ответ отправляется на 1★ негативный отзыв с текстом "Спасибо за отзыв! Рады, что товар понравился."

**Защита (defence in depth):**
1. Hardcode `rating >= 4` (не из настроек)
2. Pre-send `validate_reply_text()` проверит текст
3. Daily limit предотвращает массовую рассылку
4. Задержка 15 мин даёт время оператору заметить
5. Monitoring алерт при auto-reply на rating < 4

---

## 11. Success Metrics

### 11.1 KPI фичи

| Метрика | Целевое значение | Как измерять |
|---------|------------------|--------------|
| **Auto-reply rate** | >= 70% позитивных отзывов отвечены автоматически | `auto_replied / total_positive_reviews` |
| **Cancel rate** | <= 10% (оператор отменяет редко) | `cancelled / scheduled` |
| **Guardrail block rate** | <= 3% (LLM генерирует качественно) | `blocked / generated` |
| **WB moderation reject rate** | <= 1% | Мониторинг через sync |
| **Time saved** | >= 2 часа/неделю на 100 отзывов | Время оператора до/после |
| **Response rate (WB)** | Рост на 20-30% | Метрика WB seller dashboard |

### 11.2 Аварийное отключение

Если любая из метрик нарушена:
- `cancel_rate > 20%` → уведомление продавцу + рекомендация пересмотреть настройки
- `block_rate > 10%` → авто-отключение + уведомление
- `error_rate > 5%` → авто-отключение + алерт в ops dashboard

---

## Source Files Reference

| Файл | Путь | Что содержит для этой задачи |
|------|------|------------------------------|
| `GUARDRAILS.md` | `docs/GUARDRAILS.md` | Auto-Action Policy, validation pipeline, escalation rules |
| `interaction_linking.py` | `apps/chat-center/backend/app/services/interaction_linking.py` | `evaluate_link_action_policy()` — текущая авто-action логика |
| `ai_analyzer.py` | `apps/chat-center/backend/app/services/ai_analyzer.py` | LLM промпт для чатов, escalation keywords, fallback analysis |
| `wb_feedbacks_connector.py` | `apps/chat-center/backend/app/services/wb_feedbacks_connector.py` | `answer_feedback()` — метод отправки ответа в WB |
| `guardrails.py` | `apps/chat-center/backend/app/services/guardrails.py` | `validate_reply_text()`, `apply_review_guardrails()` |
| `interaction_drafts.py` | `apps/chat-center/backend/app/services/interaction_drafts.py` | `generate_interaction_draft()`, fallback drafts |
| `settings.py` (schemas) | `apps/chat-center/backend/app/schemas/settings.py` | `AISettings`, `auto_replies_positive` |
| `settings.py` (API) | `apps/chat-center/backend/app/api/settings.py` | `GET/PUT /api/settings/ai` |
| `SettingsPage.tsx` | `apps/chat-center/frontend/src/components/SettingsPage.tsx` | UI toggle для авто-ответов |
| `interactions.py` (API) | `apps/chat-center/backend/app/api/interactions.py` | `POST /{id}/reply` — существующий reply flow |
| `rate_limiter.py` | `apps/chat-center/backend/app/services/rate_limiter.py` | Token-bucket rate limiter |
| `BACKLOG_UNIFIED_COMM_V3.md` | `docs/product/BACKLOG_UNIFIED_COMM_V3.md` | BL-POST-007 entry |
