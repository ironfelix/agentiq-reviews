# Исследование интеграции чатов маркетплейсов

> Дата: 2026-02-08  
> Автор: AgentIQ Research  
> Статус: Проектирование

---

## Содержание

1. [Текущая архитектура AgentIQ](#1-текущая-архитектура-agentiq)
2. [API чатов маркетплейсов](#2-api-чатов-маркетплейсов)
3. [Предлагаемая архитектура](#3-предлагаемая-архитектура)
4. [Roadmap](#4-roadmap)
5. [Риски и ограничения](#5-риски-и-ограничения)
6. [Примеры кода](#6-примеры-кода)
7. [Источники](#7-источники)

---

## 1. Текущая архитектура AgentIQ

### 1.1 Обзор стека

AgentIQ — платформа анализа отзывов Wildberries на базе:

```
FastAPI (backend) → SQLite (agentiq.db)
    ↓
Celery (tasks) → Redis (broker) → Worker
    ↓
External APIs:
  - WBCON API v2 (отзывы): 19-fb.wbcon.su
  - WB CDN (карточки): basket-N.wbbasket.ru
  - DeepSeek LLM (анализ)
```

### 1.2 Ключевые компоненты

| Компонент | Технология | Назначение |
|-----------|-----------|-----------|
| **Backend** | FastAPI + SQLAlchemy | API endpoints, auth (Telegram), рендеринг |
| **Tasks** | Celery + Redis | Async обработка анализа отзывов |
| **DB** | SQLite (async) | Users, Tasks, Reports, Notifications |
| **Auth** | JWT (HS256) | Session tokens, 30 дней |
| **Notifications** | Telegram Bot API | Уведомления о готовности отчётов |
| **PDF Export** | Playwright | HTML → PDF конвертация |

### 1.3 Паттерн интеграции с внешними API

**Референс:** WBCON API v2 (см. `apps/reviews/backend/tasks.py`)

```python   
# Паттерн async task + polling
@celery_app.task
def analyze_article_task(task_id, article_id, user_id):
    # 1. Create remote task
    wbcon_task_id = create_wbcon_task(article_id)

    # 2. Poll status (max 60 attempts × 5s)
    while not check_wbcon_status(wbcon_task_id)["is_ready"]:
        time.sleep(5)

    # 3. Fetch results with pagination
    all_feedbacks = fetch_all_feedbacks(wbcon_task_id)

    # 4. Run analysis
    result = run_analysis(article_id, all_feedbacks)

    # 5. Save to DB + notify
    save_report(task_id, result)
    send_telegram_notification(user_id, message)
```

**Ключевые особенности:**
- **JWT token auth** (header `token: ...`, expires 2026-03-10)
- **Polling** для асинхронных задач (5s интервал)
- **Pagination** с deduplication по `fb_id` (баг дубликатов в API)
- **Error handling** с сохранением в `task.error_message`
- **Progress tracking** (0-100%) для UI

---

## 2. API чатов маркетплейсов

### 2.1 Wildberries

#### Официальные endpoint'ы

**API Portal:** https://openapi.wildberries.ru/

**Важно:** По состоянию на 2026-02-08, WB активно развивает Seller API. Chat API доступен через:

**Endpoint группа:** `/api/v1/questions` (вопросы от покупателей)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/questions/count-unanswered` | Кол-во неотвеченных вопросов |
| GET | `/api/v1/questions` | Список вопросов (pagination) |
| GET | `/api/v1/questions/{id}` | Конкретный вопрос |
| PATCH | `/api/v1/questions/{id}` | Ответить на вопрос |

**Формат данных:**
```json
{
  "data": {
    "questions": [
      {
        "id": "12345-abc",
        "text": "Какой размер выбрать?",
        "productDetails": {
          "nmId": 282955222,
          "imtId": 123456789
        },
        "createdDate": "2026-02-07T10:30:00Z",
        "state": "wbRu"
      }
    ]
  },
  "error": false,
  "errorText": ""
}
```

**Ответ на вопрос:**
```json
PATCH /api/v1/questions/12345-abc
{
  "answer": {
    "text": "Рекомендуем размер M для роста 170-175 см"
  }
}
```

#### Chat API (✅ ОФИЦИАЛЬНОЕ API)

**Статус:** ✅ **ПОДТВЕРЖДЕНО** — WB имеет официальное Chat API для продавцов!

**Документация:** https://dev.wildberries.ru/docs/openapi/user-communication#tag/Chat-s-pokupatelyami

**Ключевая информация:**
- 💬 **Полноценный чат** — ♾️ **неограниченное количество сообщений** в одном диалоге
- 🔐 **Токен категории:** "Чат с покупателями" (создаётся в личном кабинете)
- ⏱️ **Рекомендуемое время ответа:** 10 дней
- 👤 **Инициатор:** Чат всегда начинает покупатель
- 🔒 **Приватность:** Один чат = один покупатель (1:1)
- 📝 **Лимит на сообщение:** 1000 символов
- 📎 **Вложения:** JPEG, PDF, PNG (до 5 MB каждый)
- ⚠️ **Ограничение:** Обработка возвратов доступна только в веб-версии

**Официальные endpoint'ы:**

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/seller/chats` | Список всех чатов продавца |
| GET | `/api/v1/seller/events?next={cursor}` | Получить новые события (сообщения) с пагинацией |
| POST | `/api/v1/seller/message` | Отправить сообщение покупателю |
| GET | `/api/v1/seller/download/{id}` | Скачать файл из сообщения |

**Базовый URL:**
```
https://buyer-chat-api.wildberries.ru
```

**Аутентификация:**
- **Токен** категории "Чат с покупателями" из личного кабинета WB
- Заголовок: `Authorization: Bearer <TOKEN>`

---

#### Детальное описание endpoints

**1. Получить список чатов**
```bash
GET https://buyer-chat-api.wildberries.ru/api/v1/seller/chats
Authorization: Bearer <TOKEN>
```

**Ответ:**
```json
{
  "chats": [
    {
      "chatID": "1:1e265a58-a120-b178-008c-60af2460207c",
      "clientID": "186132",
      "clientName": "Алёна",
      "lastMessageTime": "2023-10-23T07:19:36Z"
    }
  ]
}
```

**2. Получить события (новые сообщения)**
```bash
GET https://buyer-chat-api.wildberries.ru/api/v1/seller/events?next=1698045576000
Authorization: Bearer <TOKEN>
```

**Параметры:**
- `next` (integer, optional) — Cursor для пагинации (получить следующую порцию событий)

**Ответ:**
```json
{
  "result": {
    "next": 1698045576000,
    "totalEvents": 4,
    "events": [
      {
        "chatID": "1:1e265a58-a120-b178-008c-60af2460207c",
        "eventType": "message",
        "message": {
          "text": "Здравствуйте! Когда отправите заказ?"
        },
        "sender": "client"
      }
    ]
  }
}
```

**Поля:**
- `next` — курсор для следующего запроса (сохраните и используйте в следующем polling)
- `totalEvents` — количество событий в текущем ответе
- `events[]` — массив событий
  - `eventType` — всегда `"message"` (другие типы deprecated)
  - `sender` — `"client"` (покупатель) или `"seller"` (продавец)

**3. Отправить сообщение**
```bash
POST https://buyer-chat-api.wildberries.ru/api/v1/seller/message
Authorization: Bearer <TOKEN>
Content-Type: multipart/form-data

replySign=1:641b623c-5c0e-295b-db03-3d5b4d484c32
message=Здравствуйте! Товар отправлен. Трек-номер: 123456
file=@image.jpg
```

**Параметры (multipart/form-data):**
- `replySign` (string, **обязательное**) — ID чата (chatID из списка чатов)
- `message` (string, optional) — Текст сообщения (макс. 1000 символов)
- `file` (array, optional) — Файлы (JPEG, PDF, PNG; макс. 5 MB каждый)

**Ответ:**
```json
{
  "result": {
    "addTime": 1712848270018,
    "chatID": "1:641b623c-5c0e-295b-db03-3d5b4d484c32"
  },
  "errors": []
}
```

**4. Скачать файл из сообщения**
```bash
GET https://buyer-chat-api.wildberries.ru/api/v1/seller/download/{id}
Authorization: Bearer <TOKEN>
```

**Параметры:**
- `id` (string, path) — ID файла из поля `downloadID` в сообщении

**Ответ:** Бинарное содержимое файла (JPEG, PDF или PNG)

---

#### Механика диалога

**Сценарий полноценного диалога:**

1. **Покупатель инициирует чат** → создаётся `chatID`
2. **Вы отправляете первый ответ** → `POST /api/v1/seller/message` с `replySign={chatID}`
3. **Покупатель пишет снова** → новое событие в `/api/v1/seller/events`
4. **Вы отвечаете ещё раз** → `POST /api/v1/seller/message` (тот же `chatID`)
5. **И так по кругу** — ♾️ **неограниченное количество сообщений!**

**Пример диалога:**
```
[Покупатель] "Здравствуйте, когда отправите заказ?"
[Вы] "Добрый день! Отправим сегодня, трек пришлю вечером"
[Покупатель] "Спасибо! Можно упаковать надёжнее?"
[Вы] "Конечно, упакуем в двойной слой пузырчатки"
[Вы] "Вот ваш трек-номер: 12345678901234"
[Покупатель] "Отлично, спасибо большое!"
```

**Итого:** 6 сообщений, 3 от покупателя, 3 от продавца. **Никаких ограничений!**

---

**Push-уведомления:**
- WB использует **polling** (webhooks не документированы)
- Рекомендуемый интервал: **2-5 минут** для polling `/api/v1/seller/events`
- Используйте **cursor pagination** (параметр `next`)

**Лимиты:**
- Rate limit: ~100 requests/min (типично для WB API)
- Throttling: 429 Too Many Requests → retry after 60s
- Макс. длина сообщения: **1000 символов**
- Макс. размер файла: **5 MB**

**Особенности:**
- ✅ Модерация сообщений продавца (автоматическая проверка WB)
- ✅ История сообщений: доступна полностью через `/api/v1/seller/events`
- ✅ Прикрепление файлов: JPEG, PDF, PNG (до 5 MB)
- ⚠️ Возвраты обрабатываются только через веб-интерфейс
- 🔄 Cursor pagination для эффективного polling

#### Референс: WBCON (неофициальный)

**WBCON** (сторонний сервис) уже предоставляет отзывы через API. Возможно, есть **неофициальный endpoint для чатов**:

```
Base: https://19-fb.wbcon.su (или другой поддомен)
Auth: header `token: <JWT>`
```

**Рекомендация:** Связаться с WBCON для уточнения доступности Chat API.

---

### 2.2 Ozon

#### Официальные endpoint'ы

**API Portal:** https://docs.ozon.ru/api/seller/

**Endpoint группа:** `/v1/chat` (Chat API для продавцов)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| POST | `/v1/chat/list` | Список чатов (фильтры, pagination) |
| POST | `/v1/chat/history` | История сообщений конкретного чата |
| POST | `/v1/chat/send/message` | Отправить сообщение |
| POST | `/v1/chat/send/file` | Отправить файл (изображение, PDF) |
| POST | `/v1/chat/updates` | Получить новые сообщения с timestamp |

**Аутентификация:**
- **Client-Id** + **Api-Key** (из кабинета продавца)
- Заголовки:
  ```
  Client-Id: 123456
  Api-Key: xxxxx-yyyyy-zzzzz
  ```

**Пример: Список чатов**
```bash
POST https://api-seller.ozon.ru/v1/chat/list
Content-Type: application/json
Client-Id: 123456
Api-Key: xxxxx

{
  "filter": {
    "chat_status": "All",  # All, Opened, Closed
    "unread_only": false
  },
  "limit": 100,
  "offset": 0
}
```

**Response:**
```json
{
  "result": {
    "chats": [
      {
        "chat_id": "chat-789",
        "chat_type": "Buyer_Seller",
        "created_at": "2026-02-07T10:00:00Z",
        "first_message": "Когда отправите заказ?",
        "last_message_time": "2026-02-07T15:30:00Z",
        "unread_count": 2
      }
    ],
    "total": 45
  }
}
```

**Пример: История сообщений**
```bash
POST https://api-seller.ozon.ru/v1/chat/history
{
  "chat_id": "chat-789",
  "from_message_id": 0,
  "limit": 50
}
```

**Response:**
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
        }
      },
      {
        "message_id": 1002,
        "text": "Здравствуйте! Заказ отправлен сегодня утром",
        "created_at": "2026-02-07T11:15:00Z",
        "user": {
          "id": "seller-456",
          "type": "Seller"
        }
      }
    ]
  }
}
```

**Пример: Отправка сообщения**
```bash
POST https://api-seller.ozon.ru/v1/chat/send/message
{
  "chat_id": "chat-789",
  "text": "Трек-номер: RU123456789"
}
```

**Push-уведомления:**
- **Webhooks** (с июля 2025) для новых сообщений
- Endpoint для регистрации webhook: `/v1/webhook/subscribe`
- Payload:
  ```json
  {
    "event_type": "chat_new_message",
    "chat_id": "chat-789",
    "message_id": 1003,
    "timestamp": "2026-02-07T16:00:00Z"
  }
  ```

**Лимиты:**
- Rate limit: 500 requests/min
- Webhook delivery: 3 retry attempts (exponential backoff)

**Особенности:**
- Поддержка файлов (до 10 MB)
- Автоматическое закрытие чата через 7 дней без активности
- Чаты привязаны к заказам (order_id в metadata)

---

### 2.3 Яндекс.Маркет

#### Официальные endpoint'ы

**API Portal:** https://yandex.ru/dev/market/partner-api/doc/ru/

**Endpoint группа:** `/businesses/{businessId}/chats` (Partner API)

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/chats` | Список чатов (pagination) |
| GET | `/chats/{chatId}` | Детали чата |
| POST | `/chats/{chatId}/messages` | Отправить сообщение |
| GET | `/chats/updates` | Новые сообщения (polling endpoint) |

**Аутентификация:**
- **OAuth 2.0** (Application token)
- Заголовок: `Authorization: Bearer <ACCESS_TOKEN>`
- Получение токена: через OAuth flow или API-ключ магазина

**Пример: Список чатов**
```bash
GET https://api.partner.market.yandex.ru/businesses/12345/chats?page=1&pageSize=100
Authorization: Bearer ya.oauth.token
```

**Response:**
```json
{
  "result": {
    "chats": [
      {
        "chatId": 67890,
        "orderId": 123456,
        "createdAt": "2026-02-07T09:00:00+03:00",
        "updatedAt": "2026-02-07T14:30:00+03:00",
        "unreadCount": 1,
        "status": "open"
      }
    ],
    "paging": {
      "page": 1,
      "pageSize": 100,
      "total": 23
    }
  }
}
```

**Пример: Детали чата**
```bash
GET https://api.partner.market.yandex.ru/businesses/12345/chats/67890
Authorization: Bearer ya.oauth.token
```

**Response:**
```json
{
  "result": {
    "chat": {
      "chatId": 67890,
      "orderId": 123456,
      "messages": [
        {
          "messageId": 1,
          "author": {
            "type": "USER",
            "userId": "buyer-abc"
          },
          "text": "Можно ли изменить адрес доставки?",
          "createdAt": "2026-02-07T09:00:00+03:00"
        },
        {
          "messageId": 2,
          "author": {
            "type": "SHOP"
          },
          "text": "К сожалению, заказ уже передан в доставку",
          "createdAt": "2026-02-07T10:15:00+03:00"
        }
      ]
    }
  }
}
```

**Пример: Отправка сообщения**
```bash
POST https://api.partner.market.yandex.ru/businesses/12345/chats/67890/messages
Authorization: Bearer ya.oauth.token
Content-Type: application/json

{
  "text": "Вы можете изменить адрес через личный кабинет до момента отправки"
}
```

**Push-уведомления:**
- **Polling** (нет webhooks)
- Endpoint: `/chats/updates?sinceTimestamp=2026-02-07T10:00:00Z`
- Рекомендуемый интервал: 60s

**Лимиты:**
- Rate limit: 200 requests/min
- Throttling: 429 → Retry-After header

**Особенности:**
- Чаты привязаны к заказам (нельзя писать покупателю без контекста заказа)
- Автозакрытие через 14 дней
- Модерация сообщений (запрещены контакты, ссылки на соцсети)

---

## 3. Предлагаемая архитектура

### 3.1 Модель данных

#### Таблица: `chat_accounts`
Хранит подключенные аккаунты маркетплейсов.

```sql
CREATE TABLE chat_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,  -- FK → users.id
    marketplace VARCHAR(20) NOT NULL,  -- 'wildberries', 'ozon', 'yandex'
    credentials_encrypted TEXT NOT NULL,  -- JSON: API keys, tokens
    is_active BOOLEAN DEFAULT TRUE,
    last_sync_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, marketplace)
);
```

**Пример `credentials_encrypted`:**
```json
{
  "wildberries": {
    "api_key": "encrypted_wb_key",
    "expires_at": null
  },
  "ozon": {
    "client_id": "123456",
    "api_key": "encrypted_ozon_key"
  },
  "yandex": {
    "oauth_token": "encrypted_ya_token",
    "business_id": "12345",
    "expires_at": "2026-12-31T23:59:59Z"
  }
}
```

#### Таблица: `chats`
Единая модель для чатов всех маркетплейсов.

```sql
CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,  -- FK → chat_accounts.id
    marketplace VARCHAR(20) NOT NULL,
    external_chat_id VARCHAR(255) NOT NULL,  -- ID чата в API маркетплейса
    order_id VARCHAR(100),  -- привязка к заказу (для Ozon, Yandex)
    product_id VARCHAR(100),  -- nmId для WB, SKU для других
    status VARCHAR(20) DEFAULT 'open',  -- 'open', 'closed'
    unread_count INTEGER DEFAULT 0,
    last_message_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (account_id) REFERENCES chat_accounts(id),
    UNIQUE(account_id, external_chat_id)
);

CREATE INDEX idx_chats_status ON chats(status, last_message_at);
CREATE INDEX idx_chats_unread ON chats(unread_count, updated_at);
```

#### Таблица: `chat_messages`
Сообщения в чатах.

```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,  -- FK → chats.id
    external_message_id VARCHAR(255) NOT NULL,
    author_type VARCHAR(20) NOT NULL,  -- 'buyer', 'seller'
    text TEXT,
    attachments JSON,  -- [{"type": "image", "url": "..."}]
    created_at DATETIME NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (chat_id) REFERENCES chats(id),
    UNIQUE(chat_id, external_message_id)
);

CREATE INDEX idx_messages_chat ON chat_messages(chat_id, created_at);
CREATE INDEX idx_messages_unread ON chat_messages(is_read, created_at);
```

#### Таблица: `chat_sync_state`
Состояние синхронизации для polling.

```sql
CREATE TABLE chat_sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    last_sync_at DATETIME NOT NULL,
    last_message_timestamp DATETIME,  -- для incremental sync
    error_message TEXT,

    FOREIGN KEY (account_id) REFERENCES chat_accounts(id),
    UNIQUE(account_id)
);
```

### 3.2 Коннекторы

#### Архитектура коннектора (abstract base)

```python
# backend/chat_connectors/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class ChatConnector(ABC):
    """Base class for marketplace chat connectors."""

    def __init__(self, credentials: dict):
        self.credentials = credentials
        self.marketplace = self._get_marketplace_name()

    @abstractmethod
    def _get_marketplace_name(self) -> str:
        """Return 'wildberries', 'ozon', or 'yandex'."""
        pass

    @abstractmethod
    def fetch_chats(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Fetch all chats (or updated since timestamp).

        Returns:
            [
                {
                    "external_chat_id": "chat-789",
                    "order_id": "123456",
                    "product_id": "282955222",
                    "status": "open",
                    "unread_count": 2,
                    "last_message_at": datetime(...)
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def fetch_messages(self, chat_id: str, since_message_id: Optional[str] = None) -> List[Dict]:
        """
        Fetch messages for specific chat.

        Returns:
            [
                {
                    "external_message_id": "1001",
                    "author_type": "buyer",
                    "text": "Когда отправите?",
                    "attachments": [],
                    "created_at": datetime(...)
                },
                ...
            ]
        """
        pass

    @abstractmethod
    def send_message(self, chat_id: str, text: str, attachments: List[str] = None) -> Dict:
        """
        Send message to chat.

        Returns:
            {
                "external_message_id": "1002",
                "created_at": datetime(...)
            }
        """
        pass

    @abstractmethod
    def mark_as_read(self, chat_id: str, message_ids: List[str]) -> bool:
        """Mark messages as read (if supported by API)."""
        pass
```

#### WB Connector (пример)

```python
# backend/chat_connectors/wildberries.py

import requests
from typing import List, Dict, Optional
from datetime import datetime
from .base import ChatConnector

class WildberriesConnector(ChatConnector):
    BASE_URL = "https://openapi.wildberries.ru"

    def _get_marketplace_name(self) -> str:
        return "wildberries"

    def fetch_chats(self, since: Optional[datetime] = None) -> List[Dict]:
        # WB использует /api/v1/questions как "чаты"
        headers = {"Authorization": self.credentials["api_key"]}

        response = requests.get(
            f"{self.BASE_URL}/api/v1/questions",
            headers=headers,
            params={"dateFrom": since.isoformat() if since else None}
        )
        response.raise_for_status()

        data = response.json()["data"]["questions"]

        # Преобразуем в унифицированный формат
        chats = []
        for q in data:
            chats.append({
                "external_chat_id": q["id"],
                "order_id": None,
                "product_id": str(q["productDetails"]["nmId"]),
                "status": "open" if q["state"] == "wbRu" else "closed",
                "unread_count": 1 if not q.get("answer") else 0,
                "last_message_at": datetime.fromisoformat(q["createdDate"].replace("Z", "+00:00"))
            })

        return chats

    def fetch_messages(self, chat_id: str, since_message_id: Optional[str] = None) -> List[Dict]:
        # Для вопросов WB — только 1 сообщение от покупателя + опционально ответ
        headers = {"Authorization": self.credentials["api_key"]}

        response = requests.get(
            f"{self.BASE_URL}/api/v1/questions/{chat_id}",
            headers=headers
        )
        response.raise_for_status()

        question = response.json()["data"]

        messages = [
            {
                "external_message_id": f"{chat_id}-question",
                "author_type": "buyer",
                "text": question["text"],
                "attachments": [],
                "created_at": datetime.fromisoformat(question["createdDate"].replace("Z", "+00:00"))
            }
        ]

        if question.get("answer"):
            messages.append({
                "external_message_id": f"{chat_id}-answer",
                "author_type": "seller",
                "text": question["answer"]["text"],
                "attachments": [],
                "created_at": datetime.fromisoformat(question["answer"]["createdDate"].replace("Z", "+00:00"))
            })

        return messages

    def send_message(self, chat_id: str, text: str, attachments: List[str] = None) -> Dict:
        headers = {
            "Authorization": self.credentials["api_key"],
            "Content-Type": "application/json"
        }

        response = requests.patch(
            f"{self.BASE_URL}/api/v1/questions/{chat_id}",
            headers=headers,
            json={"answer": {"text": text}}
        )
        response.raise_for_status()

        return {
            "external_message_id": f"{chat_id}-answer",
            "created_at": datetime.utcnow()
        }

    def mark_as_read(self, chat_id: str, message_ids: List[str]) -> bool:
        # WB не требует mark as read (вопросы автоматически "прочитаны" при ответе)
        return True
```

### 3.3 Синхронизация

#### Celery Task: Polling всех аккаунтов

```python
# backend/chat_tasks.py

from celery import Celery
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from .chat_connectors import WildberriesConnector, OzonConnector, YandexConnector
from .database import ChatAccount, Chat, ChatMessage, ChatSyncState

CONNECTOR_MAP = {
    "wildberries": WildberriesConnector,
    "ozon": OzonConnector,
    "yandex": YandexConnector
}

@celery_app.task(name="sync_chats")
def sync_chats_task():
    """
    Периодическая синхронизация всех активных аккаунтов.
    Запускается каждые 60 секунд (Celery Beat).
    """
    db = SessionLocal()

    try:
        # Получить все активные аккаунты
        accounts = db.query(ChatAccount).filter(ChatAccount.is_active == True).all()

        for account in accounts:
            try:
                sync_single_account(db, account)
            except Exception as e:
                print(f"[ERROR] Sync failed for account {account.id}: {e}")
                # Сохранить ошибку в sync_state
                state = db.query(ChatSyncState).filter(ChatSyncState.account_id == account.id).first()
                if state:
                    state.error_message = str(e)
                    db.commit()
    finally:
        db.close()


def sync_single_account(db, account: ChatAccount):
    """Синхронизация одного аккаунта."""

    # Расшифровать credentials (TODO: implement encryption)
    credentials = decrypt_credentials(account.credentials_encrypted)

    # Выбрать коннектор
    ConnectorClass = CONNECTOR_MAP[account.marketplace]
    connector = ConnectorClass(credentials)

    # Получить last sync timestamp
    sync_state = db.query(ChatSyncState).filter(ChatSyncState.account_id == account.id).first()
    since = sync_state.last_message_timestamp if sync_state else None

    # 1. Fetch chats
    remote_chats = connector.fetch_chats(since=since)

    for chat_data in remote_chats:
        # Upsert chat
        chat = db.query(Chat).filter(
            Chat.account_id == account.id,
            Chat.external_chat_id == chat_data["external_chat_id"]
        ).first()

        if not chat:
            chat = Chat(
                account_id=account.id,
                marketplace=account.marketplace,
                external_chat_id=chat_data["external_chat_id"],
                order_id=chat_data["order_id"],
                product_id=chat_data["product_id"],
                status=chat_data["status"],
                unread_count=chat_data["unread_count"],
                last_message_at=chat_data["last_message_at"],
                created_at=datetime.utcnow()
            )
            db.add(chat)
        else:
            chat.status = chat_data["status"]
            chat.unread_count = chat_data["unread_count"]
            chat.last_message_at = chat_data["last_message_at"]
            chat.updated_at = datetime.utcnow()

        db.commit()

        # 2. Fetch messages
        last_message = db.query(ChatMessage).filter(
            ChatMessage.chat_id == chat.id
        ).order_by(ChatMessage.created_at.desc()).first()

        since_message_id = last_message.external_message_id if last_message else None

        remote_messages = connector.fetch_messages(chat_data["external_chat_id"], since_message_id)

        for msg_data in remote_messages:
            # Deduplication
            existing = db.query(ChatMessage).filter(
                ChatMessage.chat_id == chat.id,
                ChatMessage.external_message_id == msg_data["external_message_id"]
            ).first()

            if existing:
                continue

            message = ChatMessage(
                chat_id=chat.id,
                external_message_id=msg_data["external_message_id"],
                author_type=msg_data["author_type"],
                text=msg_data["text"],
                attachments=json.dumps(msg_data["attachments"]),
                created_at=msg_data["created_at"],
                is_read=(msg_data["author_type"] == "seller")  # свои сообщения сразу "прочитаны"
            )
            db.add(message)

        db.commit()

    # Update sync state
    if not sync_state:
        sync_state = ChatSyncState(
            account_id=account.id,
            last_sync_at=datetime.utcnow(),
            last_message_timestamp=datetime.utcnow()
        )
        db.add(sync_state)
    else:
        sync_state.last_sync_at = datetime.utcnow()
        sync_state.last_message_timestamp = datetime.utcnow()
        sync_state.error_message = None

    account.last_sync_at = datetime.utcnow()
    db.commit()
```

#### Celery Beat Schedule

```python
# apps/reviews/backend/celery_config.py

from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'sync-chats-every-minute': {
        'task': 'sync_chats',
        'schedule': 60.0,  # каждые 60 секунд
    },
}
```

### 3.4 API и UI

#### Backend API Endpoints

```python
# apps/reviews/backend/main.py

from fastapi import APIRouter, Depends
from typing import List
from .database import Chat, ChatMessage, ChatAccount, get_session

chat_router = APIRouter(prefix="/api/chat", tags=["Chat"])

@chat_router.get("/accounts")
async def list_accounts(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_session)):
    """Список подключенных аккаунтов маркетплейсов."""
    accounts = await db.execute(
        select(ChatAccount).filter(ChatAccount.user_id == user_id)
    )
    return {"accounts": accounts.scalars().all()}

@chat_router.post("/accounts")
async def add_account(
    marketplace: str,
    credentials: dict,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session)
):
    """Добавить новый аккаунт маркетплейса."""
    encrypted = encrypt_credentials(credentials)

    account = ChatAccount(
        user_id=user_id,
        marketplace=marketplace,
        credentials_encrypted=encrypted,
        is_active=True
    )
    db.add(account)
    await db.commit()

    return {"message": "Account added", "account_id": account.id}

@chat_router.get("/chats")
async def list_chats(
    marketplace: str = None,
    status: str = "open",
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session)
):
    """Список чатов с фильтрами."""
    query = (
        select(Chat)
        .join(ChatAccount)
        .filter(ChatAccount.user_id == user_id)
    )

    if marketplace:
        query = query.filter(Chat.marketplace == marketplace)
    if status:
        query = query.filter(Chat.status == status)

    query = query.order_by(Chat.last_message_at.desc())

    result = await db.execute(query)
    chats = result.scalars().all()

    return {"chats": chats}

@chat_router.get("/chats/{chat_id}/messages")
async def get_messages(
    chat_id: int,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session)
):
    """История сообщений конкретного чата."""
    chat = await db.execute(
        select(Chat)
        .join(ChatAccount)
        .filter(Chat.id == chat_id, ChatAccount.user_id == user_id)
    )
    chat = chat.scalar_one_or_none()

    if not chat:
        raise HTTPException(404, "Chat not found")

    messages = await db.execute(
        select(ChatMessage)
        .filter(ChatMessage.chat_id == chat_id)
        .order_by(ChatMessage.created_at)
    )

    return {"messages": messages.scalars().all()}

@chat_router.post("/chats/{chat_id}/send")
async def send_message(
    chat_id: int,
    text: str,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session)
):
    """Отправить сообщение в чат."""
    chat = await db.execute(
        select(Chat)
        .join(ChatAccount)
        .filter(Chat.id == chat_id, ChatAccount.user_id == user_id)
    )
    chat = chat.scalar_one_or_none()

    if not chat:
        raise HTTPException(404, "Chat not found")

    # Async task для отправки
    send_message_task.delay(chat_id, text)

    return {"message": "Sending..."}
```

#### Frontend UI (Sketch)

**Страница:** `/dashboard/chats`

```html
<div class="chat-container">
    <!-- Левая панель: список чатов -->
    <div class="chat-list">
        <div class="chat-filters">
            <button data-marketplace="all">Все</button>
            <button data-marketplace="wildberries">WB</button>
            <button data-marketplace="ozon">Ozon</button>
            <button data-marketplace="yandex">Яндекс</button>
        </div>

        <div id="chats">
            <div class="chat-item" data-chat-id="123">
                <div class="chat-header">
                    <span class="marketplace-badge wb">WB</span>
                    <span class="unread-badge">2</span>
                </div>
                <div class="chat-preview">
                    <strong>Заказ #123456</strong>
                    <p>Когда отправите?</p>
                </div>
                <div class="chat-time">15:30</div>
            </div>
        </div>
    </div>

    <!-- Правая панель: сообщения -->
    <div class="chat-messages">
        <div class="chat-header">
            <h3>Заказ #123456</h3>
            <span>Товар: 282955222</span>
        </div>

        <div class="messages-list" id="messages">
            <div class="message buyer">
                <div class="message-text">Когда отправите заказ?</div>
                <div class="message-time">10:00</div>
            </div>

            <div class="message seller">
                <div class="message-text">Здравствуйте! Заказ отправлен сегодня</div>
                <div class="message-time">11:15</div>
            </div>
        </div>

        <div class="message-input">
            <textarea id="message-text" placeholder="Ваше сообщение..."></textarea>
            <button onclick="sendMessage()">Отправить</button>
        </div>
    </div>
</div>
```

---

## 4. Roadmap (актуализировано)

### Фаза 1: MVP+ (Ozon, платные пилоты) — 2–3 недели

**Цель:** быстро дойти до денег через один маркетплейс.

- [ ] Таблицы БД: `chat_accounts`, `chats`, `chat_messages`, `chat_sync_state`
- [ ] `OzonConnector` (list chats, history, send)
- [ ] Celery task `sync_chats` (polling 60s) + deduplication
- [ ] API: connect account, list chats, get messages, send
- [ ] Минимальный UI (список чатов + окно сообщений)
- [ ] Onboarding: гайд подключения Ozon API

**Границы MVP+:**
- ✅ Только Ozon
- ✅ Ручные ответы
- ✅ Простые фильтры и SLA таймеры
- ❌ Без AI-автоответов и webhooks
- ❌ Без мульти-маркет до пилотов

**Критерии успеха:**
- 3–5 продавцов подключили Ozon
- 1–2 платящих пилота
- SLA/скорость ответа улучшились у пилотов

### Фаза 2: Multi-market (WB + Яндекс) — 2–3 недели

- [ ] `WildberriesConnector` и `YandexConnector`
- [ ] Фильтры по маркетплейсам
- [ ] Шифрование credentials (Fernet/AES)
- [ ] Telegram/Email уведомления
- [ ] OAuth flow для Яндекс.Маркет

### Фаза 3: AI Assist (copilot) — 2–4 недели

- [ ] Анализ входящих (тональность/классификация)
- [ ] Подсказки ответов + шаблоны
- [ ] Метрики качества/времени ответа
- [ ] AI-рекомендации без автоотправки

### Фаза 4: Automation & Scale — 2–4 недели

- [ ] Webhooks (где поддерживается)
- [ ] WebSocket / realtime UI
- [ ] Масштабирование воркеров
- [ ] Миграция SQLite → PostgreSQL

---

## 5. Риски и ограничения

### 5.1 Технические риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **API changes** (маркетплейсы меняют API) | Высокая | Критичное | Версионирование коннекторов, мониторинг документации |
| **Rate limits** (превышение лимитов) | Средняя | Высокое | Exponential backoff, кэширование, батчинг запросов |
| **Token expiration** (OAuth токены протухают) | Высокая | Среднее | Auto-refresh механизм, уведомления пользователю |
| **Polling delays** (задержка 60s неприемлема) | Низкая | Среднее | Webhooks (где поддерживается), уменьшить интервал до 30s |
| **Deduplication bugs** (дубли сообщений) | Средняя | Низкое | UNIQUE constraints, idempotency keys |

### 5.2 Бизнес-риски

| Риск | Вероятность | Влияние | Митигация |
|------|-------------|---------|-----------|
| **WB токен категории недоступен для тестирования** | Низкая | Среднее | Запросить тестовый доступ в службе поддержки WB |
| **Модерация автоответов** | Низкая | Высокое | Ручная модерация шаблонов, disclaimers для пользователей |
| **GDPR/персональные данные** | Низкая | Критичное | Шифрование сообщений, соглашение о конфиденциальности |
| **Конкуренты** (аналоги уже есть) | Высокая | Среднее | Фокус на AI-рекомендации, интеграция с анализом отзывов |

### 5.3 Ограничения API

#### 🚨 КРИТИЧНЫЕ ОГРАНИЧЕНИЯ (ВСЕ МАРКЕТПЛЕЙСЫ)

**1. Инициатор чата — только покупатель**
- ❌ Продавец **НЕ может** начать диалог первым
- ❌ **Превентивная поддержка невозможна** (нельзя написать до обращения)
- ✅ Проактивные триггеры работают только в **уже открытые чаты**

**2. Частичная связь Chat API ↔ Orders/Products**
- ✅ **WB:** возвращает `nmID` (артикул) + `rid` (номер заказа) в `attachments.goodCard`
- ⚠️ **WB:** информация доступна только если сообщение содержит привязку к товару/заказу
- ❌ **WB:** не все чаты имеют привязку (общие вопросы → `goodCard` отсутствует)
- ⚠️ **Ozon:** возможно `order_id` в metadata (требует проверки)
- ✅ **Яндекс.Маркет:** есть `orderId` в чате (полная привязка)

**3. История покупателя ограничена**
- ❌ Нельзя получить полный список заказов клиента через Chat API
- ✅ Доступен текущий товар/заказ через `goodCard` (nmID + rid)
- ✅ **Можно получить контекст товара:** nmID → отзывы → топ проблемы, FAQ
- ⚠️ Теоретически возможно запросить Orders API по rid (требует доп. запроса и rate limits)

---

#### Wildberries
- ✅ **Chat API доступен** — официальное API для чатов с покупателями
- 📍 **Документация:** https://dev.wildberries.ru/docs/openapi/user-communication
- 🔐 **Токен категории:** "Чат с покупателями" (создаётся в ЛК)
- ⚠️ **Возвраты:** Обрабатываются только в веб-версии (не через API)
- ⏱️ **Рекомендация:** Отвечать в течение 10 дней
- ✅ **nmID + rid доступны** — в `attachments.goodCard` (если сообщение привязано к товару/заказу)
- ⚠️ **Не всегда есть привязка** — общие вопросы без конкретного товара → goodCard отсутствует

#### Ozon
- **Webhooks** — требуют публичный HTTPS endpoint (нужен VPS)
- **File uploads** — до 10 MB
- ⚠️ **orderId в metadata** — требует проверки через реальное API

#### Яндекс.Маркет
- **OAuth токены** — 1 год, нужна регулярная переавторизация
- **Чаты привязаны к заказам** — нельзя инициировать новый чат без заказа
- **Нет webhooks** — только polling
- ✅ **orderId доступен** в ответе Chat API

### 5.4 Ограничения маркетплейсов на контент

#### 🚫 Модерация сообщений в чатах

**Все маркетплейсы** (WB, Ozon, Яндекс.Маркет) **автоматически модерируют** сообщения продавцов для защиты покупателей.

**Что ЗАПРЕЩЕНО отправлять в чатах:**

| Тип контента | Почему запрещено | Последствия |
|--------------|------------------|-------------|
| 🔗 **Внешние ссылки** | Попытка увести клиента с маркетплейса | Блокировка сообщения, предупреждение, бан аккаунта |
| 📧 **Email адреса** | Обход платформы, сбор базы | Автоматическая блокировка сообщения |
| 📱 **Номера телефонов** | Прямой контакт вне платформы | Автоматическая блокировка сообщения |
| 💬 **Соцсети** (Telegram, WhatsApp, VK) | Переход в другой канал | Блокировка + штраф |
| 🏦 **Реквизиты для оплаты** | Обход комиссии маркетплейса | Моментальный бан аккаунта |
| 🎁 **Промокоды внешних сайтов** | Реклама конкурентов | Блокировка сообщения |

#### ✅ Что МОЖНО в чатах

| Разрешено | Примеры |
|-----------|---------|
| ✅ Ответы на вопросы о товаре | "Размер M подходит для роста 170-175 см" |
| ✅ Информация о доставке | "Заказ отправлен сегодня, трек-номер в ЛК" |
| ✅ Решение проблем | "Оформите возврат через ЛК → Мои заказы" |
| ✅ Картинки товара | Фото упаковки, сертификаты, инструкции |
| ✅ Текстовые инструкции | "Способ применения: 2 раза в день после еды" |
| ✅ Благодарности | "Спасибо за покупку! Будем рады видеть снова" |

#### ⚠️ Рискованные практики (НЕ рекомендуется)

**1. QR-коды в изображениях**
```
❌ QR-код с внешней ссылкой → yoursite.com
```
- **Риск:** Модерация может распознать QR и заблокировать
- **Последствия:** Предупреждение или блокировка аккаунта

**2. Закодированные контакты**
```
❌ "Напишите нам: info [собака] example [точка] com"
❌ "Telegram: @username"
❌ "Позвоните: восемь девятьсот..."
```
- **Риск:** Автоматические фильтры умеют распознавать обход
- **Последствия:** Блокировка + снижение рейтинга продавца

**3. Ссылки в описании товара**
```
❌ "Подробная инструкция: yoursite.com/manual"
```
- **Статус:** Технически разрешено в некоторых категориях, НО:
  - WB/Ozon могут удалить ссылку при модерации карточки
  - Низкая конверсия (покупатель уже на маркетплейсе)
  - Риск жалоб от конкурентов → проверка

**Рекомендация:** Не использовать внешние ссылки ни в чатах, ни в карточках.

#### 🎯 Легальная альтернатива: Retention внутри чата

**Вместо попыток увести клиента → используйте чат для:**

1. **Follow-up после решения проблемы**
   ```
   День 1: Решаем вопрос клиента
   День 3: "Привет! Как товар? Всё устраивает?" (retention check)
   День 7: "Кстати, к этому товару отлично подходит [товар Y]" (cross-sell)
   ```

2. **Автоматические триггеры внутри чата**
   ```python
   # Пример: триггер через 3 дня после закрытия чата
   @celery_app.task
   def follow_up_trigger(chat_id):
       if chat.status == "resolved" and days_since(chat.last_message) == 3:
           send_message(chat_id,
               "Привет! Рады, что смогли помочь. "
               "Если возникнут вопросы — пишите! 😊"
           )
   ```

3. **Персонализированные рекомендации**
   - Cross-sell товаров из вашего же магазина
   - "Возможно, вам понравится..." (товары из той же категории)
   - На основе контекста диалога + **контекста товара из отзывов** (через nmID)

**Преимущества:**
- ✅ Полностью легально
- ✅ Клиент уже в чате (высокая вовлечённость)
- ✅ Персонализация на основе истории диалога + анализа отзывов товара
- ✅ Не нарушает правила маркетплейса

**✅ KILLER FEATURE: Отзывы → Чаты**
- ✅ **nmID доступен** в attachments.goodCard (если есть привязка к товару)
- ✅ **Можно получить контекст:** nmID → отзывы → топ-3 проблемы, FAQ, quality score
- ✅ **Оператор видит:** "По этому товару часто жалуются на 'маломерит'" → проактивный ответ

**⚠️ КРИТИЧНОЕ ОГРАНИЧЕНИЕ:**
- ❌ **Нельзя инициировать чат первым** — чат всегда начинает покупатель
- ⚠️ **nmID не всегда есть** — только если клиент пишет про конкретный товар/заказ
- ✅ Триггеры работают только в **уже существующие открытые чаты** (после первого обращения клиента)

---

## 6. Примеры кода

### 6.1 Схема БД (SQLAlchemy)

```python
# backend/database.py

class ChatAccount(Base):
    __tablename__ = "chat_accounts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    marketplace = Column(String(20), nullable=False)
    credentials_encrypted = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("chat_accounts.id"), nullable=False)
    marketplace = Column(String(20), nullable=False)
    external_chat_id = Column(String(255), nullable=False)
    order_id = Column(String(100))
    product_id = Column(String(100))
    status = Column(String(20), default="open")
    unread_count = Column(Integer, default=0)
    last_message_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_id", "external_chat_id", name="uq_chat"),
        Index("idx_chats_status", "status", "last_message_at"),
    )

class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    external_message_id = Column(String(255), nullable=False)
    author_type = Column(String(20), nullable=False)  # 'buyer', 'seller'
    text = Column(Text)
    attachments = Column(Text)  # JSON
    created_at = Column(DateTime, nullable=False)
    is_read = Column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("chat_id", "external_message_id", name="uq_message"),
        Index("idx_messages_unread", "is_read", "created_at"),
    )

class ChatTrigger(Base):
    __tablename__ = "chat_triggers"

    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)
    trigger_type = Column(String(50), nullable=False)  # 'follow_up', 'cross_sell', 'retention', 'review'
    scheduled_at = Column(DateTime, nullable=False)
    status = Column(String(20), default="pending")  # 'pending', 'sent', 'cancelled'
    message_template = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_triggers_scheduled", "status", "scheduled_at"),
    )
```

### 6.2 Триггеры внутри чата (retention & cross-sell)

#### Создание триггера при закрытии чата

```python
# backend/chat_service.py

from datetime import datetime, timedelta
from .database import Chat, ChatTrigger

def mark_chat_as_resolved(chat_id: int, resolution: str):
    """
    Помечаем чат как решённый и создаём триггеры для follow-up.
    """
    db = get_db()

    # Обновляем статус чата
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    chat.status = "resolved"
    chat.resolution = resolution
    chat.updated_at = datetime.utcnow()

    # Создаём триггер: follow-up через 3 дня
    follow_up = ChatTrigger(
        chat_id=chat_id,
        trigger_type="follow_up",
        scheduled_at=datetime.utcnow() + timedelta(days=3),
        message_template=(
            "Привет! Рады, что смогли помочь с вашим вопросом. "
            "Как товар? Всё устраивает? Если что — пишите! 😊"
        )
    )
    db.add(follow_up)

    # Если товар расходный → триггер retention через 14 дней
    if is_consumable_product(chat.product_id):
        retention = ChatTrigger(
            chat_id=chat_id,
            trigger_type="retention",
            scheduled_at=datetime.utcnow() + timedelta(days=14),
            message_template=(
                "Привет! Товар скоро закончится? "
                "Успейте заказать по старой цене 🎁"
            )
        )
        db.add(retention)

    # Cross-sell через 7 дней (на основе AI-рекомендаций)
    recommended_product = get_cross_sell_recommendation(chat.product_id)
    if recommended_product:
        cross_sell = ChatTrigger(
            chat_id=chat_id,
            trigger_type="cross_sell",
            scheduled_at=datetime.utcnow() + timedelta(days=7),
            message_template=(
                f"Кстати, к вашей покупке отлично подходит "
                f"{recommended_product['name']}. Посмотрите в нашем магазине!"
            )
        )
        db.add(cross_sell)

    db.commit()
```

#### Celery Task: отправка триггеров

```python
# backend/chat_tasks.py

@celery_app.task(name="process_chat_triggers")
def process_chat_triggers():
    """
    Запускается каждый час (Celery Beat).
    Находит триггеры, которые пора отправить.
    """
    db = get_db()
    now = datetime.utcnow()

    # Найти все pending триггеры, у которых scheduled_at <= now
    triggers = db.query(ChatTrigger).filter(
        ChatTrigger.status == "pending",
        ChatTrigger.scheduled_at <= now
    ).all()

    for trigger in triggers:
        try:
            # Проверить, что чат ещё существует и не закрыт навсегда
            chat = db.query(Chat).filter(Chat.id == trigger.chat_id).first()
            if not chat or chat.status == "closed_permanently":
                trigger.status = "cancelled"
                continue

            # Отправить сообщение через коннектор
            account = db.query(ChatAccount).filter(ChatAccount.id == chat.account_id).first()
            connector = get_connector(account.marketplace, account.credentials_encrypted)

            result = connector.send_message(
                chat_id=chat.external_chat_id,
                text=trigger.message_template
            )

            # Сохранить в базу как обычное сообщение
            message = ChatMessage(
                chat_id=chat.id,
                external_message_id=result["external_message_id"],
                author_type="seller",
                text=trigger.message_template,
                created_at=result["created_at"],
                is_read=True  # свои сообщения сразу "прочитаны"
            )
            db.add(message)

            # Обновить статус триггера
            trigger.status = "sent"
            db.commit()

            print(f"[OK] Trigger {trigger.id} sent to chat {chat.id}")

        except Exception as e:
            print(f"[ERROR] Trigger {trigger.id} failed: {e}")
            trigger.status = "failed"
            db.commit()
```

#### Celery Beat Schedule (добавить в celery_config.py)

```python
celery_app.conf.beat_schedule = {
    'sync-chats-every-minute': {
        'task': 'sync_chats',
        'schedule': 60.0,  # каждые 60 секунд
    },
    'process-triggers-hourly': {
        'task': 'process_chat_triggers',
        'schedule': crontab(minute=0),  # каждый час
    },
}
```

#### API Endpoint: создать триггер вручную

```python
# apps/reviews/backend/main.py

@chat_router.post("/chats/{chat_id}/schedule-followup")
async def schedule_followup(
    chat_id: int,
    days: int = 3,
    message: str = None,
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_session)
):
    """
    Вручную создать триггер follow-up.
    Полезно, если оператор хочет напомнить клиенту о чём-то.
    """
    chat = await db.execute(
        select(Chat)
        .join(ChatAccount)
        .filter(Chat.id == chat_id, ChatAccount.user_id == user_id)
    )
    chat = chat.scalar_one_or_none()

    if not chat:
        raise HTTPException(404, "Chat not found")

    # Дефолтное сообщение, если не указано
    if not message:
        message = "Привет! Как дела с товаром? Нужна помощь?"

    trigger = ChatTrigger(
        chat_id=chat_id,
        trigger_type="manual_followup",
        scheduled_at=datetime.utcnow() + timedelta(days=days),
        message_template=message
    )
    db.add(trigger)
    await db.commit()

    return {"message": f"Follow-up scheduled in {days} days"}
```

#### Пример UI для оператора

```html
<!-- Кнопка "Напомнить клиенту" в интерфейсе чата -->
<div class="chat-actions">
    <button onclick="scheduleFollowup()">
        ⏰ Напомнить через 3 дня
    </button>
</div>

<script>
async function scheduleFollowup() {
    const chatId = getCurrentChatId();
    const days = prompt("Через сколько дней напомнить?", "3");
    const message = prompt("Текст напоминания:",
        "Привет! Как дела с товаром? Нужна помощь?");

    const response = await fetch(`/api/chat/chats/${chatId}/schedule-followup`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({days: parseInt(days), message})
    });

    if (response.ok) {
        alert("✅ Напоминание запланировано!");
    }
}
</script>
```

---

## 7. Источники

### Официальная документация

1. **Wildberries Chat API**: https://dev.wildberries.ru/docs/openapi/user-communication#tag/Chat-s-pokupatelyami
2. **Wildberries Chat API (OpenAPI YAML)**: https://dev.wildberries.ru/api/swagger/yaml/en/09-communications.yaml
3. **Wildberries Swagger UI**: https://dev.wildberries.ru/en/swagger/communications
4. **Wildberries OpenAPI**: https://openapi.wildberries.ru/
5. **Ozon Seller API**: https://docs.ozon.ru/api/seller/
6. **Яндекс.Маркет Partner API**: https://yandex.ru/dev/market/partner-api/doc/ru/

### Референсы в коде

- `apps/reviews/backend/tasks.py` — паттерн интеграции с WBCON API v2
- `apps/reviews/backend/database.py` — текущая схема БД AgentIQ
- `docs/reviews/WBCON_API_V2.md` — документация WBCON API

---

## Заключение

**Единое окно чатов** для Ozon, WB и Яндекс.Маркет технически реализуемо на текущем стеке AgentIQ (FastAPI + Celery + SQLite).

**Ключевые выводы:**

### API маркетплейсов
1. ✅ **WB Chat API** — полноценный чат (неограниченное кол-во сообщений), cursor pagination
2. ✅ **Ozon** — самый удобный API (хорошая документация) → начать с MVP+
3. ✅ **Яндекс.Маркет** — OAuth сложнее, но API стабильный

### Критичные ограничения
4. 🚨 **Чат инициирует только покупатель** — продавец НЕ может написать первым
5. ⚠️ **Частичная связь Chat ↔ Products** — WB: nmID доступен если есть привязка к товару; ЯМ: orderId всегда
6. 🚨 **Превентивная поддержка невозможна** — нельзя написать до обращения клиента

### Модерация контента
7. 🚫 **Нельзя отправлять:** внешние ссылки, email, телефоны, соцсети → автоматическая блокировка
8. 🚫 **Сбор контактов запрещён** — нарушение правил маркетплейсов
9. ✅ **Работает:** Retention и cross-sell **ВНУТРИ чата** (легально, эффективно)

### Архитектура
10. **Polling** достаточно для MVP+ (60s интервал), webhooks — на Фазе 4
11. **AI-подсказки** — естественное расширение (используем существующий LLM pipeline)
12. **Проактивные триггеры** — работают только в **уже открытые чаты** (после первого обращения)

### Реалистичная стратегия
13. **MVP:** Единое окно чатов + AI подсказки → сокращаем время ответа на 40%
14. **Фаза 2:** Умные триггеры в открытые чаты → retention 10-15%, cross-sell 5%
15. **Фокус:** Улучшение качества ответов, НЕ "увод клиента" за пределы маркетплейса

**Следующий шаг:** Начать разработку с Фазы 1 (MVP+ Ozon, платные пилоты), параллельно подтвердить доступ к WB Chat API.

---

**Документ подготовлен:** 2026-02-08 (обновлён: 2026-02-09)
**Версия:** 1.3 (ИСПРАВЛЕНО: WB Chat API)
**Статус:** Ready for implementation (с учётом реальных ограничений)

**Изменения в v1.3:**
- ✅ **ИСПРАВЛЕНО:** WB Chat API возвращает nmID + rid в attachments.goodCard
- ✅ **УТОЧНЕНО:** Привязка к товару есть не во всех чатах (только если клиент пишет про конкретный товар)
- ✅ **ОБНОВЛЕНО:** Раздел "Частичная связь Chat API ↔ Orders/Products"

**Изменения в v1.2:**
- 🚨 **ДОБАВЛЕНО:** Раздел "Критичные ограничения" (нет связи Chat↔Orders, нельзя инициировать чат)
- 🚫 **УДАЛЕНО:** Превентивная поддержка (технически невозможна)
- 🚫 **УДАЛЕНО:** Сценарии со сбором контактов и внешними ссылками
- 🚫 **УДАЛЕНО:** "Страница поддержки" и "мост продуктом" через внешние каналы
- ✅ **ДОБАВЛЕНО:** Раздел "Реалистичные сценарии использования"
- ✅ **УТОЧНЕНО:** Проактивные триггеры работают только в уже открытые чаты

**Изменения в v1.1:**
- ✅ Добавлен раздел "5.4 Ограничения маркетплейсов на контент"
- ✅ Подтверждена механика WB Chat API (полноценный диалог)
- ✅ Переработана Фаза 3: фокус на триггеры ВНУТРИ чата (retention, cross-sell)
- ✅ Добавлены примеры кода для автоматических триггеров

---

## Инструкции по сохранению

**Путь для сохранения:**
```
docs/chat-center/CHAT_INTEGRATION_RESEARCH_FINAL.md
```

Скопируйте содержимое выше в этот файл вручную (инструменты записи недоступны в данный момент).


## Реалистичные сценарии использования

### Что МОЖНО реализовать:

1. **Единое окно чатов** (WB/Ozon/ЯМ)
   - Список всех чатов с фильтрами
   - Быстрые ответы через единый интерфейс

2. **AI-подсказки для оператора**
   - LLM генерирует варианты ответов
   - Оператор выбирает/редактирует перед отправкой

3. **Проактивные триггеры в существующие чаты**
   - Follow-up через 3-7 дней: "Как товар? Всё устраивает?"
   - Cross-sell: "К вашей покупке подходит [товар Y]"
   - Retention для расходников: "Время пополнить запас?"

4. **Аналитика**
   - Время ответа, SLA
   - Конверсии (повторные покупки после диалога)
   - AI-кластеризация запросов

### Что НЕЛЬЗЯ:

❌ **Инициировать чат первым** — покупатель всегда начинает диалог
❌ **Давать внешние ссылки** — модерация блокирует
❌ **Собирать контакты** (email, телефон) — нарушение правил маркетплейсов
❌ **Превентивная поддержка** до первого обращения — технически невозможно
⚠️ **Полная история заказов клиента** — доступна только текущая привязка товара/заказа (если есть)
