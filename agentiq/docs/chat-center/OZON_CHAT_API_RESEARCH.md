# Ozon Chat API — Полное исследование

> Дата: 2026-02-08
> Автор: AgentIQ Research
> Статус: Production Ready

---

## 1. Официальная документация

### Ссылки
- **Основная документация:** https://docs.ozon.ru/api/seller/
- **Базовый URL API:** `https://api-seller.ozon.ru`
- **Версия API:** v1 (Chat API), v2-v4 (другие эндпоинты)
- **Swagger UI:** https://api-seller.ozon.ru/swagger/index.html

### Структура документации
Ozon предоставляет REST API для продавцов (Seller API) с разделами:
- Products (товары)
- Orders (заказы)
- **Chat (чаты с покупателями)** ← наш фокус
- Analytics (аналитика)
- Finance (финансы)

---

## 2. Аутентификация

### Client-Id + Api-Key
Ozon использует простую схему аутентификации через заголовки:

```http
Client-Id: 123456
Api-Key: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

### Где получить credentials
1. Зайти в личный кабинет продавца: https://seller.ozon.ru/
2. **Настройки → API ключи** (`/app/settings/api-keys`)
3. Создать новый API-ключ:
   - Выбрать права доступа (permissions)
   - Для Chat API нужны права: **"Чат с покупателями"**
4. Скопировать:
   - **Client-Id** (числовой ID продавца)
   - **Api-Key** (UUID формата `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)

### Срок действия токенов
- **Бессрочные** (не expire)
- Можно отозвать в личном кабинете
- Рекомендуется ротация раз в 6-12 месяцев

### Пример запроса
```bash
curl -X POST https://api-seller.ozon.ru/v1/chat/list \
  -H "Client-Id: 123456" \
  -H "Api-Key: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {"chat_status": "All"},
    "limit": 10,
    "offset": 0
  }'
```

---

## 3. Endpoints для чатов

### 3.1 POST /v1/chat/list

**Описание:** Получить список чатов с фильтрами и pagination.

**Параметры запроса:**
```json
{
  "filter": {
    "chat_status": "All",        // All, Opened, Closed
    "chat_id_list": ["12345"],   // опционально: конкретные chat_id
    "unread_only": false         // только с непрочитанными
  },
  "limit": 100,                  // 1-100, default 10
  "offset": 0                    // pagination offset
}
```

**Пример ответа:**
```json
{
  "result": {
    "chats": [
      {
        "chat_id": "chat-789abc",
        "chat_type": "Buyer_Seller",
        "created_at": "2026-02-07T10:00:00Z",
        "first_message": "Когда отправите заказ?",
        "last_message_time": "2026-02-07T15:30:00Z",
        "unread_count": 2,
        "order_number": "123456-0001",
        "posting_number": "00000000-0000-0001",
        "user_name": "Иван П."
      }
    ],
    "total": 45,
    "has_next": true
  }
}
```

**Поля:**
- `chat_id` (string) — уникальный ID чата
- `chat_type` (string) — всегда `"Buyer_Seller"`
- `created_at` (ISO 8601) — дата создания чата
- `first_message` (string) — первое сообщение покупателя
- `last_message_time` (ISO 8601) — время последнего сообщения
- `unread_count` (int) — количество непрочитанных сообщений
- `order_number` (string) — номер заказа (связь с Order API)
- `posting_number` (string) — номер отправления
- `user_name` (string) — имя покупателя (частично скрыто: "Иван П.")

**Фильтры и pagination:**
- `chat_status`:
  - `"All"` — все чаты
  - `"Opened"` — только открытые
  - `"Closed"` — только закрытые
- `limit`: максимум 100 за раз
- `offset`: стандартная cursor pagination (offset += limit)

**Rate limits:**
- 500 requests/min (общий лимит на Seller API)
- Рекомендуется не более 1 запрос/сек для polling

---

### 3.2 POST /v1/chat/history

**Описание:** Получить историю сообщений конкретного чата.

**Параметры запроса:**
```json
{
  "chat_id": "chat-789abc",
  "from_message_id": 0,         // опционально: incremental sync
  "limit": 50                   // default 50, max 100
}
```

**Пример ответа:**
```json
{
  "result": {
    "messages": [
      {
        "message_id": 1001,
        "text": "Когда отправите заказ?",
        "created_at": "2026-02-07T10:00:00Z",
        "user": {
          "id": "buyer-123",
          "type": "Customer"
        },
        "is_read": false
      },
      {
        "message_id": 1002,
        "text": "Здравствуйте! Заказ отправлен сегодня утром",
        "created_at": "2026-02-07T11:15:00Z",
        "user": {
          "id": "seller-456",
          "type": "Seller"
        },
        "is_read": true
      }
    ],
    "has_next": false
  }
}
```

**Поля:**
- `message_id` (int) — уникальный ID сообщения (инкрементальный)
- `text` (string) — текст сообщения
- `created_at` (ISO 8601) — время отправки
- `user.type` — `"Customer"` или `"Seller"`
- `is_read` (bool) — прочитано ли сообщение

**Incremental sync:**
Используйте `from_message_id` для получения только новых сообщений:
```json
{
  "chat_id": "chat-789abc",
  "from_message_id": 1002,  // получить message_id > 1002
  "limit": 50
}
```

---

### 3.3 POST /v1/chat/send/message

**Описание:** Отправить сообщение покупателю.

**Параметры запроса:**
```json
{
  "chat_id": "chat-789abc",
  "text": "Трек-номер: RU123456789. Доставка 3-5 дней."
}
```

**Пример ответа:**
```json
{
  "result": {
    "message_id": 1003,
    "created_at": "2026-02-07T12:00:00Z",
    "status": "sent"
  }
}
```

**Лимиты:**
- Максимальная длина текста: **4000 символов**
- Можно отправлять до **10 сообщений в минуту** на один chat
- Rate limit: 500 requests/min (общий)

**Модерация:**
Ozon автоматически модерирует сообщения продавца:
- Запрещены: внешние ссылки, email, телефоны, соцсети
- Модерация происходит мгновенно (sync)
- Если сообщение нарушает правила → **HTTP 400** с ошибкой

**Пример ошибки модерации:**
```json
{
  "code": 400,
  "message": "Message contains prohibited content: phone number"
}
```

---

### 3.4 POST /v1/chat/send/file

**Описание:** Отправить файл (изображение, PDF, документ).

**Параметры запроса (multipart/form-data):**
```http
POST /v1/chat/send/file
Content-Type: multipart/form-data

chat_id=chat-789abc
file=@/path/to/image.jpg
```

**Поддерживаемые форматы:**
- Изображения: JPEG, PNG, WEBP
- Документы: PDF
- Максимальный размер: **10 MB**

**Пример ответа:**
```json
{
  "result": {
    "message_id": 1004,
    "file_url": "https://cdn.ozon.ru/chat/files/abc123.jpg",
    "created_at": "2026-02-07T12:05:00Z"
  }
}
```

---

### 3.5 POST /v1/chat/updates

**Описание:** Получить новые сообщения с incremental sync (polling endpoint).

**Параметры запроса:**
```json
{
  "since_timestamp": "2026-02-07T12:00:00Z",  // ISO 8601
  "limit": 100
}
```

**Пример ответа:**
```json
{
  "result": {
    "updates": [
      {
        "chat_id": "chat-789abc",
        "message_id": 1005,
        "text": "Спасибо, получил!",
        "created_at": "2026-02-07T16:00:00Z",
        "user": {
          "type": "Customer"
        }
      },
      {
        "chat_id": "chat-456def",
        "message_id": 2001,
        "text": "Когда будет доставка?",
        "created_at": "2026-02-07T16:10:00Z",
        "user": {
          "type": "Customer"
        }
      }
    ],
    "has_next": false
  }
}
```

**Best practice для polling:**
1. Запрашивать `/v1/chat/updates` каждые **60 секунд**
2. Сохранять `max(created_at)` из ответа
3. Следующий запрос: `since_timestamp = saved_max_timestamp`
4. Deduplication по `message_id` (на случай дублей)

---

## 4. Webhooks

### Поддерживаются ли webhooks?

**Да!** Ozon поддерживает webhooks для событий чатов (с июля 2025).

### Как подписаться на события

**Endpoint для регистрации webhook:**
```
POST /v1/webhook/subscribe
```

**Параметры запроса:**
```json
{
  "url": "https://yourdomain.com/api/webhooks/ozon",
  "events": ["chat_new_message", "chat_status_changed"],
  "is_active": true
}
```

**Пример payload webhook (POST на ваш URL):**
```json
{
  "event_type": "chat_new_message",
  "chat_id": "chat-789abc",
  "message_id": 1003,
  "created_at": "2026-02-07T16:00:00Z",
  "user_type": "Customer",
  "timestamp": "2026-02-07T16:00:01Z"
}
```

**События (events):**
- `chat_new_message` — новое сообщение в чате
- `chat_status_changed` — чат открыт/закрыт
- `chat_created` — создан новый чат

### Требования к webhook endpoint
1. **HTTPS обязателен** (Ozon не отправляет на HTTP)
2. Ответ **200 OK** в течение **5 секунд**
3. Если endpoint недоступен → **3 retry** с exponential backoff (1s, 5s, 15s)
4. После 3 неудачных попыток → webhook деактивируется

### Проверка подлинности (signature)
Ozon отправляет HMAC-SHA256 подпись в заголовке:
```http
X-Ozon-Signature: sha256=abc123...
```

**Алгоритм проверки:**
```python
import hmac
import hashlib

def verify_ozon_webhook(payload: str, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"sha256={expected}" == signature
```

---

## 5. Лимиты API

### Rate limits

| Тип запроса | Лимит | Пояснение |
|-------------|-------|-----------|
| **Общий лимит** | 500 requests/min | На весь Seller API (все endpoints) |
| **Chat API** | 1-2 requests/sec | Рекомендуемый интервал |
| **Polling /v1/chat/updates** | 1 req/60s | Оптимально для background sync |
| **Send message** | 10 msg/min на chat | Защита от спама |

### Throttling (429 Too Many Requests)

**Пример ответа при превышении лимита:**
```json
{
  "code": 429,
  "message": "Rate limit exceeded",
  "details": "Retry after 60 seconds"
}
```

**Best practices:**
1. **Exponential backoff** при 429
2. **Rate limiter на стороне приложения**
3. **Batch requests** где возможно

---

## 6. Структура данных

### Модель Chat

```typescript
interface OzonChat {
  chat_id: string;              // "chat-789abc"
  chat_type: "Buyer_Seller";
  created_at: string;           // ISO 8601
  first_message: string;
  last_message_time: string;    // ISO 8601
  unread_count: number;
  order_number: string;         // "123456-0001"
  posting_number: string;       // "00000000-0000-0001"
  user_name: string;            // "Иван П." (partially hidden)
  status: "opened" | "closed";
}
```

### Модель Message

```typescript
interface OzonMessage {
  message_id: number;           // 1001, 1002, ...
  text: string;
  created_at: string;           // ISO 8601
  user: {
    id: string;                 // "buyer-123" или "seller-456"
    type: "Customer" | "Seller";
  };
  is_read: boolean;
  attachments?: OzonAttachment[];
}

interface OzonAttachment {
  type: "image" | "document";
  url: string;
  file_name: string;
  size_bytes: number;
}
```

---

## 7. Сравнение с WB Chat API

| Параметр | Ozon | Wildberries |
|----------|------|-------------|
| **Аутентификация** | Client-Id + Api-Key | Bearer Token |
| **Polling endpoint** | `/v1/chat/updates` | `/api/v1/seller/events` |
| **Webhooks** | ✅ Есть (с июля 2025) | ❌ Нет (только polling) |
| **Pagination** | Offset-based | Cursor-based (next) |
| **Rate limit** | 500 req/min | ~100 req/min |
| **Макс. длина сообщения** | 4000 символов | 1000 символов |
| **Файлы** | До 10 MB (JPEG, PNG, PDF) | До 5 MB (JPEG, PDF, PNG) |
| **Incremental sync** | `from_message_id` + `since_timestamp` | `next` cursor |
| **Read status** | `is_read` (bool) | Не документирован |
| **Модерация** | Мгновенная (sync) | Мгновенная (sync) |
| **Документация** | ⭐⭐⭐⭐⭐ Отличная | ⭐⭐⭐ Хорошая |

### Что лучше в Ozon

1. **Webhooks из коробки** — не нужен постоянный polling
2. **Более высокие лимиты** — 500 vs 100 req/min
3. **Длинные сообщения** — 4000 vs 1000 символов
4. **Стандартная pagination** — offset проще, чем cursor
5. **Лучшая документация** — подробные примеры, Swagger UI

### Что хуже в Ozon

1. **Webhooks требуют HTTPS** — нужен VPS с SSL (для MVP+ можно обойтись polling)
2. **Частично скрытые имена** — "Иван П." vs "Иван Петров" (WB)
3. **Нет поддержки multiple files** — только 1 файл на сообщение

### Рекомендация

**Начать с Ozon для MVP+:**
- Лучшая документация = быстрее разработка
- Webhooks = меньше нагрузки на сервер (Phase 2+)
- Высокие лимиты = меньше проблем с rate limiting

---

## 8. Рекомендации для интеграции

### Polling vs Webhooks

**Для MVP+ (Phase 1) — Polling:**
```python
# Каждые 60 секунд
@celery_app.task(name="sync_ozon_chats")
def sync_ozon_chats():
    # 1. Get last sync timestamp from DB
    last_sync = get_last_sync_timestamp("ozon")

    # 2. Fetch updates
    response = ozon_api.post("/v1/chat/updates", {
        "since_timestamp": last_sync.isoformat(),
        "limit": 100
    })

    # 3. Process new messages
    for update in response["result"]["updates"]:
        upsert_message(update)

    # 4. Update last_sync
    save_last_sync_timestamp("ozon", datetime.utcnow())
```

**Для Phase 2+ — Webhooks:**
```python
@app.post("/api/webhooks/ozon")
async def ozon_webhook(request: Request):
    # 1. Verify signature
    signature = request.headers.get("X-Ozon-Signature")
    payload = await request.body()

    if not verify_ozon_webhook(payload, signature, OZON_WEBHOOK_SECRET):
        raise HTTPException(403, "Invalid signature")

    # 2. Parse payload
    event = await request.json()

    # 3. Process event
    if event["event_type"] == "chat_new_message":
        fetch_and_save_message(event["chat_id"], event["message_id"])

    return {"status": "ok"}
```

### Error handling

**Retry strategy:**
```python
import backoff

@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    max_time=300  # 5 минут
)
def ozon_api_call(endpoint, data):
    response = requests.post(
        f"https://api-seller.ozon.ru{endpoint}",
        headers={
            "Client-Id": OZON_CLIENT_ID,
            "Api-Key": OZON_API_KEY,
            "Content-Type": "application/json"
        },
        json=data,
        timeout=10
    )

    if response.status_code == 429:
        # Rate limit exceeded
        time.sleep(60)
        raise requests.exceptions.RequestException("Rate limit")

    response.raise_for_status()
    return response.json()
```

---

## 9. Массовые рассылки (Push-уведомления)

### 9.1 Центр Уведомлений

Ozon предоставляет функционал массовых push-уведомлений через **Центр Уведомлений** в личном кабинете продавца.

**Доступ:** seller.ozon.ru → Маркетинг → Центр Уведомлений

### 9.2 Тарифы и лимиты

| Параметр | Значение |
|----------|----------|
| **Базовая стоимость** | 2 ₽ за успешно доставленное сообщение |
| **Premium Plus подписка** | 50,000 бесплатных сообщений/месяц |
| **Оплата** | Только за доставленные (не отправленные) |
| **Лимит на клиента** | 1 сообщение в месяц |
| **Модерация** | Обязательна |

### 9.3 Целевые аудитории

- **Постоянные покупатели** - клиенты, которые уже покупали у вас
- **Потенциальные клиенты** - подбираются ML-алгоритмами Ozon
- **Автоматическая регулировка** - нагрузка на покупателей регулируется автоматически

### 9.4 Аналитика

После рассылки доступны метрики:
- ✅ Количество доставленных уведомлений
- 🛒 Количество клиентов, которые купили товар
- 📦 Количество купленных товаров
- 📊 Conversion rate рассылки

### 9.5 API для рассылок

⚠️ **Важно:** API для создания рассылок через Центр Уведомлений **не документирован публично**.

**Текущее состояние:**
- Рассылки создаются **только через веб-интерфейс** seller.ozon.ru
- Performance API существует, но предназначен для **рекламных кампаний**, не push-уведомлений
- Автоматизация возможна только через browser automation (Selenium/Puppeteer)

### 9.6 Performance API

**Назначение:** Управление рекламными кампаниями (не путать с рассылками).

**Базовый URL:** `https://api.ozon.ru/performance/v1/`

**Основные endpoints:**
```
GET  /performance/v1/campaigns        # Список рекламных кампаний
GET  /performance/v1/campaigns/{id}   # Информация о кампании
POST /performance/v1/campaigns        # Создать кампанию
GET  /performance/v1/statistics       # Статистика кампаний
```

**Аутентификация:** Bearer token (отличается от Client-Id/Api-Key для Seller API)

**Документация:** https://docs.ozon.ru/global/en/api/perfomance-api/

### 9.7 Альтернатива: Рассылки через Chat API

Вместо платных push-уведомлений можно использовать **персональные сообщения через Chat API**:

**Преимущества:**
- ✅ Бесплатно (в рамках Chat API)
- ✅ Полная автоматизация через API
- ✅ Без модерации
- ✅ Без лимитов 1 сообщение/месяц

**Ограничения:**
- ❌ Только для активных чатов (не "холодные" клиенты)
- ❌ Клиент должен был написать первым

**Пример use case:**
```python
# Smart Broadcast через Chat API
from app.services.ozon_connector import OzonConnector

connector = OzonConnector(client_id, api_key)

# Получить все открытые чаты
chats = await connector.list_chats(chat_status="opened", limit=100)

for chat in chats["result"]["chats"]:
    # Отправить персонализированное сообщение
    await connector.send_message(
        chat_id=chat["chat_id"],
        text=f"Добрый день! У нас новая коллекция товаров со скидкой 20%"
    )
    await asyncio.sleep(0.1)  # Rate limiting
```

### 9.8 Сравнение: Push vs Chat Messages

| Параметр | Push-рассылки | Chat API Messages |
|----------|---------------|-------------------|
| **Стоимость** | 2₽/msg (50k бесплатно Premium+) | Бесплатно |
| **API** | ❌ Нет (только UI) | ✅ Есть |
| **Аудитория** | Все покупатели + потенциальные | Только активные чаты |
| **Модерация** | ✅ Обязательна | ❌ Нет |
| **Лимиты** | 1 msg/месяц на клиента | Нет (rate limit API) |
| **Автоматизация** | ❌ Только через UI | ✅ Полная |
| **Персонализация** | Ограниченная | Полная (контекст чата) |

### 9.9 Рекомендации для MVP+

**Week 3-4: Smart Broadcast Feature**

Добавить функционал массовых рассылок через Chat API:

```python
# Endpoint: POST /api/broadcasts
{
  "seller_id": 1,
  "template": "Добрый день! У нас новая коллекция {category}",
  "filters": {
    "last_message_days_ago": 7,      # Не писали больше 7 дней
    "customer_type": "repeat",        # Постоянные клиенты
    "unread_count": 0                 # Нет непрочитанных
  },
  "rate_limit": 10  # сообщений в секунду
}
```

**Преимущества:**
- Бесплатная альтернатива платным push
- Интеграция с существующим Chat API
- Персонализация на основе истории чата
- Полная автоматизация

---

## 10. Источники

### Официальная документация
1. **Ozon Seller API Documentation:** https://docs.ozon.ru/api/seller/
2. **Chat API Reference:** https://docs.ozon.ru/api/seller/#tag/Chat
3. **Swagger UI:** https://api-seller.ozon.ru/swagger/index.html
4. **API Keys Management:** https://seller.ozon.ru/app/settings/api-keys
5. **Performance API:** https://docs.ozon.ru/global/en/api/perfomance-api/
6. **Центр Уведомлений (рассылки):** https://docs.ozon.ru/performance/marketing-requests/center-notifications/
7. **Реклама в рассылках:** https://seller-edu.ozon.ru/how-to-sell-effectively/marketing/direct-communication

### Статьи и новости
1. **Push-уведомления для продавцов (vc.ru):** https://vc.ru/marketplace/2232247-ozon-razreshil-prodavtsam-rassylat-push-uvedomleniya
2. **Тарифы на рассылки (oborot.ru):** https://oborot.ru/news/2-rublya-za-shtuku-ozon-razreshil-vsem-selleram-privlekat-pokupatelej-push-uvedomleniyami-i254789.html

### Внутренние референсы
- `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/docs/CHAT_INTEGRATION_RESEARCH_FINAL.md` — сравнение с WB и Яндекс

---

**Версия документа:** 1.1
**Дата последнего обновления:** 2026-02-09
**Статус:** Production Ready + Marketing Research

**Что добавлено в v1.1:**
- ✅ Исследование массовых рассылок (Push-уведомления)
- ✅ Тарифы и лимиты Центра Уведомлений
- ✅ Performance API (рекламные кампании)
- ✅ Сравнение Push vs Chat API для рассылок
- ✅ Рекомендации по Smart Broadcast через Chat API

**Следующие шаги:**
1. ✅ ~~Создать `OzonConnector` класс~~ (готово: `backend/app/services/ozon_connector.py`)
2. Настроить Celery task для polling
3. Протестировать на реальных credentials
4. Реализовать Smart Broadcast feature (Week 3-4)
