# Reply Flow Plan -- Отправка ответов через WB API

> Last updated: 2026-02-15
> Status: Research Complete, Ready for Implementation
> Author: AgentIQ Engineering

---

## 1. Текущее состояние (Current State)

### 1.1 Что уже реализовано

**Все три канала полностью реализованы на уровне backend.** Система готова отправлять ответы на отзывы, вопросы и сообщения в чатах через WB API.

#### Review (отзывы) -- ГОТОВО
- Коннектор: `wb_feedbacks_connector.py` -> метод `answer_feedback(feedback_id, text)`
- Endpoint WB: `POST /api/v1/feedbacks/answer` на `feedbacks-api.wildberries.ru`
- API endpoint AgentIQ: `POST /interactions/{id}/reply` (channel=review)
- Реализация: `interactions.py:555-560`
- Retry: 3 попытки с exponential backoff при 429, dual auth header (token / Bearer token)

#### Question (вопросы) -- ГОТОВО
- Коннектор: `wb_questions_connector.py` -> метод `patch_question(question_id, state, answer_text)`
- Endpoint WB: `PATCH /api/v1/questions` на `feedbacks-api.wildberries.ru`
- API endpoint AgentIQ: `POST /interactions/{id}/reply` (channel=question)
- Реализация: `interactions.py:561-572`
- Поддерживает параметр `state` (wbRu / none) из `extra_data`

#### Chat (чаты) -- ГОТОВО
- Коннектор: `wb_connector.py` -> метод `send_message(chat_id, text, attachments)`
- Endpoint WB: `POST /api/v1/seller/message` на `buyer-chat-api.wildberries.ru`
- API endpoint AgentIQ: `POST /interactions/{id}/reply` (channel=chat)
- Реализация: `interactions.py:573-634`
- Дополнительно: `POST /messages` endpoint для прямой отправки из chat view (`messages.py:76-158`)
- Асинхронная отправка: сообщение создается со статусом `pending`, Celery task `send_message_to_marketplace` отправляет в фоне

### 1.2 Unified Reply Endpoint

Единый endpoint `POST /interactions/{interaction_id}/reply`:

```
POST /api/interactions/{interaction_id}/reply
Content-Type: application/json
Authorization: Bearer <seller_token>

{
  "text": "Здравствуйте! Спасибо за отзыв..."
}
```

**Полный pipeline:**
1. Загрузка interaction из БД
2. Проверка ownership (seller_id)
3. Валидация текста (не пустой)
4. **Pre-send guardrails** (blocking) -- `validate_reply_text()`
5. Маршрутизация по channel -> вызов соответствующего WB API
6. Запись метрик (reply_sent, draft_accepted/edited/manual)
7. Обновление статуса interaction -> `responded`, `needs_response=false`
8. Сохранение `last_reply_text`, `last_reply_at`, `wb_sync_state: pending` в `extra_data`

### 1.3 Guardrails Pipeline -- ГОТОВО

Файл: `guardrails.py`

**Draft-time (advisory):** `apply_guardrails()` -- добавляет warnings, не блокирует
**Pre-send (blocking):** `validate_reply_text()` -- блокирует при severity=error

Проверки:
- Banned phrases (AI mentions, promises, blame, dismissive)
- Unsolicited return/refund mention (без запроса покупателя)
- Length validation (20-300 символов)

При нарушении -> HTTP 422 с деталями violations.

### 1.4 AI Draft Generation -- ГОТОВО

Файл: `interaction_drafts.py`

- `POST /interactions/{id}/ai-draft` -- генерация черновика
- Кэширование в `extra_data.last_ai_draft`
- Fallback шаблоны для каждого канала
- Guardrail warnings на сгенерированный текст
- Quality tracking: draft_accepted / draft_edited / reply_manual

### 1.5 Async Sending (Chat) -- ГОТОВО

Файл: `sync.py:1145-1256` -- Celery task `send_message_to_marketplace`

- Message создается со статусом `pending`
- Celery task отправляет через WBConnector / OzonConnector
- max_retries=5, exponential backoff (10, 20, 40, 80, 160 sec)
- При модерации (ValueError) -> `status=failed`, без retry
- При сетевой ошибке -> retry
- При успехе -> `status=sent`, `chat_status=responded`

### 1.6 Reply Pending Window -- ГОТОВО

Файл: `interaction_ingest.py` -- `_reply_pending_override()`

Защита от перезатирания: если AgentIQ отправил ответ < 180 мин назад, но WB API еще не отразил это (модерация, propagation delay), re-ingestion сохраняет статус `responded`.

### 1.7 Что отсутствует / Gaps

| Gap | Описание | Приоритет |
|-----|----------|-----------|
| **UI отправки (review/question)** | Фронтенд Chat Center не имеет UI для отправки ответов на отзывы и вопросы из interaction card | P0 |
| **Confirmation state в UI** | Нет визуального "pending/sending..." состояния при отправке | P1 |
| **Error display в UI** | Нет отображения ошибок модерации WB и guardrail violations в UI | P1 |
| **Edit feedback reply** | WB позволяет PATCH для редактирования ответа (1 раз за 60 дней), не реализовано | P2 |
| **Attachment support (review/question)** | WB Chat поддерживает файлы, reviews/questions -- нет в текущем API | P3 |
| **Rate limiter client-side** | Нет клиентского rate limiter, полагаемся на retry при 429 | P2 |
| **Bulk reply** | Нет массовой отправки ответов (выбрать несколько -> отправить) | P2 |
| **Reply queue** | Нет очереди на отправку для review/question (только chat имеет Celery task) | P1 |
| **Webhook/callback** | WB не поддерживает webhooks; нет уведомлений о результате модерации отзывов | -- |
| **Cursor persistence** | Sync cursor не сохраняется между перезапусками (известный tech debt) | P1 |

---

## 2. WB API Endpoints для записи (Write Operations)

### 2.1 Ответ на отзыв (Review Reply)

```
POST https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer
Authorization: <API_KEY>
Content-Type: application/json

{
  "id": "<feedback_id>",
  "text": "Текст ответа (2-5000 символов)"
}
```

| Параметр | Значение |
|----------|----------|
| HTTP Method | POST |
| Auth | API key (Feedbacks category) |
| Text length | 2-5000 символов |
| Response | 204 No Content (success) |
| Rate limit | 3 req/sec, burst 6 |
| Ошибки | 400 (bad request), 401 (auth), 429 (rate limit) |

**Редактирование ответа:**
```
PATCH https://feedbacks-api.wildberries.ru/api/v1/feedbacks/answer
```
- Тот же формат body
- Ограничение: редактировать можно **1 раз в 60 дней**
- Response: 204

### 2.2 Ответ на вопрос (Question Reply)

```
PATCH https://feedbacks-api.wildberries.ru/api/v1/questions
Authorization: <API_KEY>
Content-Type: application/json

{
  "id": "<question_id>",
  "state": "wbRu",
  "answer": {
    "text": "Текст ответа"
  }
}
```

| Параметр | Значение |
|----------|----------|
| HTTP Method | PATCH |
| Auth | API key (Questions category) |
| state | "wbRu" (для русскоязычных) или "none" |
| Response | 200 OK |
| Rate limit | 3 req/sec, burst 6 |
| Ошибки | 400, 401, 403 (forbidden), 404 (not found), 429 |

**Примечание:** Можно также отметить вопрос как просмотренный:
```json
{"id": "...", "wasViewed": true}
```

### 2.3 Сообщение в чат (Chat Message)

```
POST https://buyer-chat-api.wildberries.ru/api/v1/seller/message
Authorization: Bearer <JWT_TOKEN>
Content-Type: multipart/form-data

replySign=<chatID>&message=<текст>
file=@photo.jpg  (опционально)
```

| Параметр | Значение |
|----------|----------|
| HTTP Method | POST |
| Auth | Bearer JWT (Chat category) |
| Content-Type | multipart/form-data |
| replySign | chatID (формат "1:UUID"), макс 255 символов |
| message | Текст, макс **1000 символов** |
| file | JPEG/PDF/PNG, макс 5 MB каждый, 30 MB суммарно |
| Response | 200 с `{result: {addTime, chatID}, errors: []}` |
| Rate limit | 10 req/10sec, burst 10 |
| Модерация | Мгновенная (sync), блокирует ссылки/email/телефоны/соцсети |

### 2.4 Сводная таблица rate limits

| Канал | Rate Limit | Burst | Интервал |
|-------|-----------|-------|----------|
| Review reply | 3 req/sec | 6 | 333 ms |
| Question reply | 3 req/sec | 6 | 333 ms |
| Chat message | 10 req/10sec | 10 | 1 sec |
| Events polling | ~100 req/min | -- | 60 sec recommended |

### 2.5 Аутентификация

**Критичный нюанс:** WB использует **разные типы токенов** для разных API:

| API | Auth Header | Тип токена | Как получить |
|-----|------------|-----------|-------------|
| Feedbacks (reviews) | `Authorization: <token>` | API key (не JWT) | ЛК -> API ключи -> "Вопросы / Отзывы" |
| Questions | `Authorization: <token>` | API key (не JWT) | То же самое |
| Chat | `Authorization: Bearer <JWT>` | JWT (3 сегмента) | ЛК -> API ключи -> "Чат с покупателями" |

**Текущая реализация:** `wb_feedbacks_connector.py` и `wb_questions_connector.py` пробуют оба варианта auth header (token и Bearer token) с retry при 401. `wb_connector.py` (chat) требует строго JWT.

**Рекомендация:** Seller может иметь один или два токена (feedbacks+questions и chat). При onboarding нужно проверять оба.

---

## 3. UI Flow: Пользователь нажимает "Отправить"

### 3.1 Review / Question Reply Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERACTION CARD                          │
│                                                             │
│  [Текст отзыва/вопроса покупателя]                         │
│                                                             │
│  ┌─────────────────────────────────┐                        │
│  │ AI Draft: "Здравствуйте!..."   │  [Принять] [Изменить]  │
│  │ ⚠ Guardrail: too_long (320)    │                        │
│  └─────────────────────────────────┘                        │
│                                                             │
│  ┌─────────────────────────────────┐                        │
│  │ [textarea: редактированный текст]│                       │
│  └─────────────────────────────────┘                        │
│                                                             │
│  [Отправить] ← disabled если guardrails error              │
│                                                             │
│  Статус: ● Отправка...  /  ✓ Отправлено  /  ✗ Ошибка      │
└─────────────────────────────────────────────────────────────┘
```

**Последовательность:**

1. Пользователь открывает interaction card (review/question)
2. Нажимает "Сгенерировать ответ" -> `POST /interactions/{id}/ai-draft`
3. Получает draft + guardrail warnings
4. Редактирует текст при необходимости
5. Нажимает "Отправить":
   a. Фронтенд делает client-side валидацию (не пустой, длина)
   b. `POST /interactions/{id}/reply` с `{text: "..."}`
   c. Backend: guardrail validation (blocking)
   d. Если violation -> 422, показать ошибки пользователю
   e. Если ok -> вызов WB API
   f. Если WB error (модерация) -> 502, показать ошибку
   g. Если ok -> 200, обновить статус в UI

### 3.2 Chat Reply Flow (существующий)

```
┌─────────────────────────────────────────┐
│              CHAT WINDOW                │
│                                         │
│  [Сообщения чата...]                    │
│                                         │
│  ┌─── AI Suggestion ──────────────────┐ │
│  │ "Здравствуйте! Рекомендую..."      │ │
│  │ [Использовать] [Изменить]          │ │
│  └────────────────────────────────────┘ │
│                                         │
│  ┌────────────────────────┐ [Отправить] │
│  │ [input: текст]         │             │
│  └────────────────────────┘             │
│                                         │
│  Статус: ● Отправляется... ✓ Отправлено │
└─────────────────────────────────────────┘
```

**Последовательность:**
1. Пользователь вводит текст или принимает AI suggestion
2. Нажимает "Отправить"
3. **Оптимистичный UI:** сообщение сразу отображается с индикатором "pending"
4. `POST /messages` или `POST /interactions/{id}/reply`
5. Создается Message(status=pending)
6. Celery task `send_message_to_marketplace` отправляет в фоне
7. При успехе -> status=sent, UI обновляется
8. При ошибке -> status=failed, показать ошибку

### 3.3 Unified Flow (target)

```
                    Пользователь
                        │
                    [Отправить]
                        │
                ┌───────▼───────┐
                │ Client-side   │ пустой? длина?
                │ validation    │
                └───────┬───────┘
                        │
              POST /interactions/{id}/reply
                        │
                ┌───────▼───────┐
                │ Guardrails    │ banned phrases?
                │ validate_     │ unsolicited return?
                │ reply_text()  │
                └───────┬───────┘
                        │
              ┌─────────▼─────────┐
              │ violations?        │
              │ -> 422 + details   │──── показать ошибку
              └─────────┬─────────┘
                        │ ok
              ┌─────────▼─────────┐
              │ Route by channel   │
              ├─────┬───────┬─────┤
              │rev  │quest  │chat │
              ▼     ▼       ▼     │
        answer_ patch_  send_     │
        feedback question message │
              │     │       │     │
              ▼     ▼       ▼     │
         WB Feedbacks  WB Chat   │
            API         API      │
              │     │       │     │
         ┌────▼─────▼───────▼────┐
         │ WB error?              │
         │ -> 502 + "модерация"   │── показать ошибку
         └────────┬───────────────┘
                  │ ok
         ┌────────▼───────────────┐
         │ record_reply_events()  │
         │ status = responded     │
         │ needs_response = false │
         │ wb_sync_state = pending│
         └────────┬───────────────┘
                  │
            200 OK + updated interaction
```

---

## 4. Guardrails: Валидация перед отправкой

### 4.1 Текущие guardrails (реализованы)

| Категория | Правило | Severity | Каналы |
|-----------|---------|----------|--------|
| AI mentions | "ИИ", "бот", "нейросеть", "GPT", "автоматический ответ" | error (block) | Все |
| Promises | "вернём деньги", "гарантируем замену", "компенсируем" | error (block) | review, question |
| Blame | "вы неправильно", "ваша вина", "сами виноваты" | error (review/question), warning (chat) | Все |
| Dismissive | "обратитесь в поддержку" | error (block) | review, question |
| Unsolicited return | Упоминание возврата без запроса покупателя | error (block) | review, question |
| Too long | > 300 символов | warning | Все |
| Too short | < 20 символов | warning | Все |

### 4.2 WB Moderation (серверная)

WB дополнительно проверяет на своей стороне:
- Внешние ссылки (URL)
- Email адреса
- Номера телефонов
- Упоминания соцсетей (Telegram, WhatsApp, VK)
- Нецензурная лексика

**Проблема:** Ошибки модерации WB возвращаются как HTTP 400 с `errors[]`, текст ошибки неструктурированный.

### 4.3 Рекомендуемые дополнительные guardrails

| Правило | Описание | Приоритет |
|---------|----------|-----------|
| URL detection | Предупреждать о ссылках до отправки (WB заблокирует) | P0 |
| Phone/email detection | Предупреждать о телефонах/email до отправки | P0 |
| Duplicate reply detection | Предупреждать если тот же текст уже отправлен | P1 |
| Rate limit throttle | Блокировать если > 3 ответа/сек (WB rate limit) | P1 |
| Text similarity check | Предупреждать если ответ = шаблон без персонализации | P2 |

---

## 5. Состояния отправки (Confirmation Flow)

### 5.1 State Machine

```
idle -> sending -> sent
                -> failed -> idle (retry)
                -> rejected (guardrail) -> idle (edit)
```

### 5.2 UI States

| State | UI | Кнопка | Описание |
|-------|----|--------|----------|
| `idle` | Textarea + кнопка "Отправить" | enabled | Готов к отправке |
| `validating` | Spinner на кнопке | disabled | Client-side + guardrails |
| `sending` | "Отправка..." + spinner | disabled | Запрос к WB API |
| `sent` | "Отправлено" + зеленая галочка | скрыта | Успех |
| `failed` | "Ошибка: ..." + кнопка "Повторить" | "Повторить" | WB ошибка |
| `rejected` | "Заблокировано: ..." + список violations | disabled до исправления | Guardrail block |

### 5.3 Review/Question: Синхронная отправка

Для review и question ответ отправляется **синхронно** (в рамках HTTP запроса):
- `POST /interactions/{id}/reply` ждет ответа WB API
- Timeout: 20 сек (настроен в коннекторах)
- Результат: сразу 200 (sent) или ошибка (502/422)

### 5.4 Chat: Асинхронная отправка

Для chat ответ отправляется **асинхронно** через Celery:
- `POST /interactions/{id}/reply` создает Message(status=pending) и возвращает 200
- Celery task `send_message_to_marketplace` отправляет в фоне
- Frontend: оптимистичный UI (сообщение сразу в ленте с индикатором pending)
- Polling или WebSocket для обновления статуса (TODO: пока нет)

### 5.5 Reply Pending Window

После отправки reply AgentIQ помечает interaction как `responded` с `wb_sync_state: pending`. Следующий цикл sync (ingest) может попытаться перезатереть это состояние, потому что WB API еще не отразил ответ (модерация, propagation delay).

Защита: `_reply_pending_override()` -- если `last_reply_source=agentiq` и `last_reply_at` < 180 мин назад, сохраняет статус `responded`.

Настраиваемый параметр: `reply_pending_window_minutes` (по умолчанию 180, можно менять через runtime settings).

---

## 6. Обработка ошибок (Error Handling)

### 6.1 Типы ошибок

| Ошибка | HTTP код | Причина | Действие |
|--------|----------|---------|----------|
| Guardrail violation | 422 | Banned phrase, unsolicited return | Показать violations, пользователь исправляет текст |
| WB Auth error | 502 (proxy) | Невалидный/отозванный токен | "Проверьте API ключ в настройках" |
| WB Rate limit | 502 (proxy) | > 3 req/sec | Retry с backoff (автоматически) |
| WB Moderation | 502 (proxy) | Ссылки, телефоны, email в тексте | Показать "WB отклонил: запрещенный контент" |
| WB Not Found | 502 (proxy) | Отзыв/вопрос удален | "Отзыв больше не доступен" |
| WB Forbidden | 502 (proxy) | Нет прав на этот вопрос/отзыв | "Нет доступа к этому элементу" |
| Network error | 502 (proxy) | Timeout, connection refused | Retry (для chat -- автоматически через Celery) |
| Empty text | 400 | Пустой текст | Client-side validation |

### 6.2 Error Response Format

Текущий формат ошибки guardrails:
```json
{
  "detail": {
    "message": "Reply blocked by guardrails",
    "violations": [
      {
        "type": "banned_phrase",
        "severity": "error",
        "message": "Запрещённая фраза: \"бот\" (категория: ai_mention)",
        "phrase": "бот",
        "category": "ai_mention"
      }
    ],
    "warnings": [...],
    "summary": "Запрещённая фраза: \"бот\"..."
  }
}
```

### 6.3 Retry Strategy

| Канал | Retry | Механизм | Max retries |
|-------|-------|----------|-------------|
| Review | Нет auto-retry | Пользователь нажимает "Повторить" | -- |
| Question | Нет auto-retry | Пользователь нажимает "Повторить" | -- |
| Chat | Auto-retry (Celery) | Exponential backoff: 10, 20, 40, 80, 160 сек | 5 |

**Рекомендация Sprint 2:** Добавить очередь отправки для review/question аналогично chat, чтобы retry был автоматическим.

---

## 7. Sprint Breakdown

### Sprint 1: UI Reply для Reviews/Questions (1.5 недели)

**Цель:** Пользователь может отправить ответ на отзыв или вопрос из Interaction Card в UI.

**Задачи:**

1. **Interaction Detail Panel** (фронтенд)
   - Компонент InteractionDetailPanel с текстом покупателя, рейтингом, продуктом
   - Textarea для ответа + кнопка "Отправить"
   - Кнопка "AI черновик" -> `POST /interactions/{id}/ai-draft`
   - Отображение guardrail warnings inline (severity=warning -- желтые, severity=error -- красные)

2. **Send Reply Flow** (фронтенд)
   - Client-side validation (не пустой, длина)
   - `POST /interactions/{id}/reply`
   - Состояния: idle -> sending -> sent / failed / rejected
   - При rejected (422): показать violations, подсветить проблемные фразы в textarea
   - При failed (502): показать сообщение об ошибке WB + кнопка "Повторить"

3. **Status Update** (фронтенд)
   - После успешной отправки: обновить interaction в списке (status=responded, needs_response=false)
   - Визуальное подтверждение: зеленая галочка + "Отправлено"
   - Переход к следующему interaction с needs_response=true (optional UX)

4. **Tests:**
   - E2E: отправка reply через API (mock WB)
   - Unit: guardrail validation на фронтенде
   - Тест reply pending window (уже есть: `test_reply_pending_window.py`)

**Файлы:**
- Frontend: новый компонент `InteractionDetail.tsx` (или интеграция в существующий)
- Backend: изменений не нужно (все endpoints готовы)
- Tests: `test_interactions_api_integration.py` (дополнить)

---

### Sprint 2: Error Handling + Client-Side Guardrails (1 неделя)

**Цель:** Robust error handling, предотвращение ошибок модерации WB до отправки.

**Задачи:**

1. **Client-side Pre-validation** (фронтенд)
   - Детектор URL (regex) -> предупреждение "WB заблокирует ссылки"
   - Детектор телефонов -> предупреждение "WB заблокирует номера телефонов"
   - Детектор email -> предупреждение "WB заблокирует email адреса"
   - Счетчик символов с визуализацией лимита (review: 5000, question: ~5000, chat: 1000)

2. **Rate Limiter (client-side)**
   - Backend: middleware или decorator для rate limiting write operations
   - 3 req/sec для feedbacks/questions, 1 req/sec для chat
   - При throttle -> 429 с Retry-After header
   - Frontend: показать "Подождите..." при rate limit

3. **Structured WB Error Parsing** (backend)
   - Парсить `errors[]` из WB response
   - Маппинг WB error codes -> user-friendly сообщения
   - PROHIBITED_CONTENT -> "WB отклонил: запрещенный контент (ссылки, телефоны, email)"
   - UNAUTHORIZED -> "API ключ недействителен. Обновите в настройках."
   - RATE_LIMIT_EXCEEDED -> "Слишком частые запросы. Повторите через минуту."

4. **Reply Queue для Review/Question** (backend)
   - Celery task `send_reply_to_wb` (аналог `send_message_to_marketplace`)
   - Создавать Interaction с `wb_sync_state=pending`
   - Auto-retry при network errors
   - Notification при финальном success/failure

5. **Tests:**
   - Mock WB moderation errors
   - Rate limit behavior
   - URL/phone/email detection accuracy

**Файлы:**
- Backend: `guardrails.py` (добавить URL/phone/email detection)
- Backend: `sync.py` (новый Celery task для review/question reply queue)
- Frontend: validation utils
- Tests: `test_guardrails.py` (дополнить)

---

### Sprint 3: Reply Analytics + Edit Reply (1 неделя)

**Цель:** Аналитика качества ответов, возможность редактирования отправленного ответа.

**Задачи:**

1. **Reply Quality Dashboard** (фронтенд)
   - Метрики из `GET /interactions/metrics/quality`:
     - accept_rate (% draft accepted as-is)
     - edit_rate (% draft edited before send)
     - manual_rate (% typed manually without draft)
   - Breakdown по каналам (review vs question vs chat)
   - Trend chart (по дням)

2. **Edit Reply** (backend + frontend)
   - `PATCH /interactions/{id}/reply` -- новый endpoint
   - Для review: `PATCH /api/v1/feedbacks/answer` (WB limit: 1 раз за 60 дней)
   - Для question: `PATCH /api/v1/questions` (повторный PATCH с новым answer)
   - Для chat: отправить новое сообщение (чат -- это поток)
   - UI: кнопка "Редактировать ответ" на отправленных interaction, warning "Можно изменить 1 раз за 60 дней" для reviews

3. **Reply History** (backend)
   - Хранить историю ответов в `extra_data.reply_history[]`
   - Показывать в interaction detail: "Ответ отправлен 15.02.2026 14:30, отредактирован 16.02.2026 10:15"

4. **Duplicate Detection** (backend)
   - При отправке: проверить, не отправлялся ли точно такой же текст в последние 24h
   - Если дубликат -> warning (не blocking)

5. **Tests:**
   - Edit reply flow
   - Reply history accumulation
   - Duplicate detection

**Файлы:**
- Backend: `interactions.py` (новый PATCH endpoint)
- Backend: `wb_feedbacks_connector.py` (добавить `edit_answer()` -- PATCH variant)
- Frontend: reply history component
- Tests: новый `test_edit_reply.py`

---

### Sprint 4: Bulk Operations + Auto-Send Pilot (1 неделя)

**Цель:** Массовые операции и подготовка к автоматической отправке (assist mode).

**Задачи:**

1. **Bulk AI Draft Generation** (backend + frontend)
   - `POST /interactions/bulk/ai-draft` -- генерация черновиков для N interactions
   - UI: "Сгенерировать для всех" кнопка в списке interactions
   - Throttle: max 10 concurrent draft generations

2. **Bulk Review/Approve** (frontend)
   - Checklist UI: выбрать несколько interactions
   - "Утвердить все" -> отправить все выбранные drafts
   - Sequential sending с rate limit (3 req/sec)
   - Progress bar: "Отправлено 5 из 12..."

3. **Auto-Send Pilot (Assist Mode)** (backend)
   - Runtime setting: `auto_send_enabled` (per seller, per channel)
   - Только для `sla_priority=low` (positive feedback, 4-5 star reviews)
   - Только если guardrails pass и confidence > threshold
   - Require seller opt-in через настройки
   - Audit log: все auto-sent replies записываются в InteractionEvent

4. **Monitoring & Alerting** (backend)
   - Ops alert: если > 5 replies failed за последний час
   - Ops alert: если accept_rate < 50% (draft quality too low)
   - Dashboard widget: "Статус отправки" (pending/sent/failed counts)

5. **Tests:**
   - Bulk operations
   - Auto-send policy enforcement
   - Rate limit compliance during bulk send

**Файлы:**
- Backend: `interactions.py` (bulk endpoints)
- Backend: `interaction_linking.py` (auto-action policy расширение)
- Backend: `interaction_metrics.py` (failure alerting)
- Frontend: bulk selection UI, auto-send settings
- Tests: `test_bulk_reply.py`, `test_auto_send.py`

---

## 8. Риски и Mitigation

| Риск | Вероятность | Последствие | Mitigation |
|------|-------------|-------------|------------|
| WB меняет API без предупреждения | Средняя | Ответы перестают отправляться | Monitoring + alert при > 3 failures/hour |
| Rate limit при bulk send | Высокая | 429 errors | Client-side throttle + exponential backoff |
| Модерация WB отклоняет ответы | Средняя | Пользователь не понимает причину | Parse WB errors + pre-validation на нашей стороне |
| Два API ключа (feedbacks + chat) | Высокая | Пользователь путается при onboarding | UI wizard с проверкой каждого ключа |
| Reply pending window слишком короткое | Низкая | Re-ingestion перезатирает responded status | Настраиваемый window (180 мин default, до 1440) |
| WB изменит токенную политику | Низкая | Массовая потеря доступа | Notification пользователям + auto-detect 401 |

---

## 9. Ключевые файлы (Reference)

| Файл | Назначение |
|------|-----------|
| `apps/chat-center/backend/app/api/interactions.py` | Reply endpoint (lines 506-676) |
| `apps/chat-center/backend/app/api/messages.py` | Chat message endpoint |
| `apps/chat-center/backend/app/services/wb_feedbacks_connector.py` | Review reply connector |
| `apps/chat-center/backend/app/services/wb_questions_connector.py` | Question reply connector |
| `apps/chat-center/backend/app/services/wb_connector.py` | Chat send connector |
| `apps/chat-center/backend/app/services/guardrails.py` | Pre-send validation |
| `apps/chat-center/backend/app/services/interaction_drafts.py` | AI draft generation |
| `apps/chat-center/backend/app/services/interaction_metrics.py` | Reply quality tracking |
| `apps/chat-center/backend/app/tasks/sync.py` | Celery send task (lines 1145-1256) |
| `apps/chat-center/backend/app/services/interaction_ingest.py` | Reply pending window |
| `apps/chat-center/backend/app/schemas/interaction.py` | Request/response schemas |
| `apps/chat-center/backend/tests/test_reply_pending_window.py` | Pending window tests |
| `docs/chat-center/WB_CHAT_API_RESEARCH.md` | WB Chat API documentation |
| `docs/GUARDRAILS.md` | Guardrails documentation |
