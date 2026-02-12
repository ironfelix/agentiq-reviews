# План тестирования WB Chat API

**Дата:** 2026-02-09
**Цель:** Проверить интеграцию с официальным WB Chat API для забора чатов из личного кабинета продавца

---

## Этап 1: Получение API токена

### Где получить токен:
1. Зайти в [личный кабинет продавца Wildberries](https://seller.wildberries.ru/)
2. Перейти в **Настройки → API → Токены**
3. Создать новый токен с правами:
   - `Вопросы и отзывы` (обязательно)
   - `Чат с покупателями` (обязательно)
4. Скопировать токен (показывается только один раз!)

### Проверка токена:
```bash
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
  https://buyer-chat-api.wildberries.ru/api/v1/seller/chats
```

Если токен валидный → HTTP 200 + JSON с чатами
Если невалидный → HTTP 401

---

## Этап 2: Быстрый тест через curl

### 1. Получить список чатов:
```bash
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
  https://buyer-chat-api.wildberries.ru/api/v1/seller/chats
```

**Ожидаемый результат:**
```json
{
  "chats": [
    {
      "chatID": "1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "clientName": "Иван И.",
      "clientID": "12345",
      "lastMessageTime": "2026-02-09T12:30:00Z"
    }
  ]
}
```

### 2. Получить события (сообщения):
```bash
curl -H "Authorization: Bearer ВАШ_ТОКЕН" \
  https://buyer-chat-api.wildberries.ru/api/v1/seller/events
```

**Ожидаемый результат:**
```json
{
  "result": {
    "next": 1234567890,
    "events": [
      {
        "chatID": "1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
        "sender": "client",
        "message": {
          "text": "Когда придет мой заказ?",
          "files": []
        }
      }
    ]
  }
}
```

---

## Этап 3: Тест через Python

Создайте файл `test_wb_chat.py`:

```python
#!/usr/bin/env python3
import requests
import json

# Вставьте ваш токен сюда
WB_TOKEN = "YOUR_TOKEN_HERE"

BASE_URL = "https://buyer-chat-api.wildberries.ru"
HEADERS = {"Authorization": f"Bearer {WB_TOKEN}"}

print("=" * 60)
print("Тест 1: Получение списка чатов")
print("=" * 60)

response = requests.get(f"{BASE_URL}/api/v1/seller/chats", headers=HEADERS)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    chats = data.get("chats", [])
    print(f"✅ Чатов получено: {len(chats)}")

    if chats:
        print("\nПример чата:")
        print(json.dumps(chats[0], indent=2, ensure_ascii=False))
else:
    print(f"❌ Ошибка: {response.text}")
    exit(1)

print("\n" + "=" * 60)
print("Тест 2: Получение событий")
print("=" * 60)

response = requests.get(f"{BASE_URL}/api/v1/seller/events", headers=HEADERS)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    result = data.get("result", {})
    events = result.get("events", [])
    next_cursor = result.get("next")

    print(f"✅ Событий получено: {len(events)}")
    print(f"Next cursor: {next_cursor}")

    if events:
        print("\nПример события:")
        print(json.dumps(events[0], indent=2, ensure_ascii=False))
else:
    print(f"❌ Ошибка: {response.text}")
    exit(1)

print("\n✅ Все тесты прошли успешно!")
```

**Запуск:**
```bash
python3 test_wb_chat.py
```

---

## Этап 4: Тест интеграции с существующим кодом

### Проверить WildberriesConnector из документации:

Согласно [WB_CHAT_API_RESEARCH.md](./WB_CHAT_API_RESEARCH.md), класс `WildberriesConnector` должен быть в `backend/connectors.py`.

**Проверить структуру:**
```bash
cd apps/reviews
find . -name "connectors.py" -o -name "*connector*"
```

Если файл не существует, создать:

```python
# backend/connectors.py
import requests
from datetime import datetime
from typing import Dict, List, Optional

class WildberriesConnector:
    BASE_URL = "https://buyer-chat-api.wildberries.ru"

    def __init__(self, credentials: Dict[str, str]):
        self.token = credentials.get("api_token")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_chats(self, since: Optional[datetime] = None) -> List[Dict]:
        """Получить список чатов."""
        response = requests.get(
            f"{self.BASE_URL}/api/v1/seller/chats",
            headers=self.headers,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        chats = []

        for chat in data.get("chats", []):
            last_message_at = datetime.fromisoformat(
                chat["lastMessageTime"].replace("Z", "+00:00")
            )

            if since and last_message_at < since:
                continue

            chats.append({
                "external_chat_id": chat["chatID"],
                "client_name": chat["clientName"],
                "client_id": chat["clientID"],
                "status": "open",
                "last_message_at": last_message_at
            })

        return chats

    def fetch_messages(
        self,
        chat_id: Optional[str] = None,
        since_cursor: Optional[int] = None
    ) -> Dict:
        """Получить новые события (сообщения)."""
        params = {"next": since_cursor} if since_cursor else {}

        response = requests.get(
            f"{self.BASE_URL}/api/v1/seller/events",
            headers=self.headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", {})

        messages = []
        for event in result.get("events", []):
            if chat_id and event["chatID"] != chat_id:
                continue

            messages.append({
                "external_message_id": f"{event['chatID']}-{result['next']}",
                "chat_id": event["chatID"],
                "author_type": "buyer" if event["sender"] == "client" else "seller",
                "text": event["message"].get("text", ""),
                "attachments": event["message"].get("files", []),
                "created_at": datetime.utcnow()
            })

        return {
            "messages": messages,
            "next_cursor": result.get("next")
        }

    def send_message(
        self,
        chat_id: str,
        text: str,
        attachments: List[str] = None
    ) -> Dict:
        """Отправить сообщение в чат."""
        files = []
        data = {
            "replySign": chat_id,
            "message": text[:1000]
        }

        if attachments:
            for file_path in attachments:
                files.append(("file", open(file_path, "rb")))

        response = requests.post(
            f"{self.BASE_URL}/api/v1/seller/message",
            headers={"Authorization": f"Bearer {self.token}"},
            data=data,
            files=files if files else None,
            timeout=15
        )

        for _, file_obj in files:
            file_obj.close()

        response.raise_for_status()
        result = response.json()

        if result.get("errors"):
            error_msg = result["errors"][0]["message"]
            raise ValueError(f"WB moderation error: {error_msg}")

        return {
            "external_message_id": f"{chat_id}-{result['result']['addTime']}",
            "created_at": datetime.fromtimestamp(result['result']['addTime'] / 1000)
        }
```

**Тест коннектора:**
```python
# test_connector.py
from backend.connectors import WildberriesConnector

credentials = {"api_token": "YOUR_TOKEN_HERE"}
connector = WildberriesConnector(credentials)

# Тест 1: Получить чаты
print("Тест 1: Получение чатов")
chats = connector.fetch_chats()
print(f"✅ Получено чатов: {len(chats)}")

# Тест 2: Получить сообщения
print("\nТест 2: Получение сообщений")
result = connector.fetch_messages()
print(f"✅ Получено сообщений: {len(result['messages'])}")
print(f"Next cursor: {result['next_cursor']}")
```

---

## Этап 5: Чек-лист для полного тестирования

### 5.1 Базовые сценарии

- [ ] **Подключение к API**
  - Валидный токен → HTTP 200
  - Невалидный токен → HTTP 401
  - Отсутствие токена → HTTP 401

- [ ] **Получение чатов**
  - Пустой кабинет → `{"chats": []}`
  - Есть чаты → массив с данными
  - Формат `chatID`: `"1:UUID"`
  - Есть `clientName`, `clientID`, `lastMessageTime`

- [ ] **Получение событий (messages)**
  - Нет новых событий → `{"result": {"next": cursor, "events": []}}`
  - Есть события → массив с данными
  - Формат `sender`: `"client"` или `"seller"`
  - Есть `message.text` и `message.files`

- [ ] **Cursor pagination**
  - Первый запрос без cursor → получить `next`
  - Второй запрос с cursor → получить новые события
  - Повторный запрос с тем же cursor → пустые события

### 5.2 Граничные случаи

- [ ] **Пустой кабинет** (нет чатов вообще)
- [ ] **Старые чаты** (последнее сообщение > 30 дней назад)
- [ ] **Чаты без новых событий** (все прочитаны ранее)
- [ ] **Лимит сообщений** (проверить, есть ли лимит за запрос)

### 5.3 Проверка данных

- [ ] **Тайминги:**
  - `lastMessageTime` в ISO 8601 формате (с `Z`)
  - Конвертация в `datetime` работает корректно

- [ ] **Chat ID:**
  - Формат: `"1:UUID"`
  - UUID валидный (RFC 4122)

- [ ] **Client info:**
  - `clientName` может быть "Иван И." (замаскированное имя)
  - `clientID` — числовой идентификатор

- [ ] **Attachments:**
  - Проверить структуру `files` в сообщениях
  - `fileName` и `downloadID` присутствуют

### 5.4 Проблемы, описанные в документации

Согласно [WB_CHAT_API_RESEARCH.md](./WB_CHAT_API_RESEARCH.md), проверить:

- [ ] **Order ID отсутствует** → workaround через Feedbacks API
- [ ] **Unread count = 0** → вычислять локально
- [ ] **Timestamp сообщений отсутствует** → использовать cursor как timestamp
- [ ] **Связь с негативными отзывами не видна** → интегрировать Feedbacks API

---

## Этап 6: Интеграция с backend

### 6.1 Проверить наличие файлов:
```bash
ls -la apps/reviews/backend/
# Ожидаем: main.py, tasks.py, database.py
```

### 6.2 Проверить модели БД:
```bash
grep -n "class Chat" apps/reviews/backend/database.py
grep -n "class ChatMessage" apps/reviews/backend/database.py
grep -n "class ChatAccount" apps/reviews/backend/database.py
```

### 6.3 Запустить тестовую синхронизацию:
```python
# test_sync.py
from backend.tasks import sync_wb_chats
from backend.database import SessionLocal

db = SessionLocal()
try:
    sync_wb_chats(db)
    print("✅ Синхронизация завершена")
except Exception as e:
    print(f"❌ Ошибка синхронизации: {e}")
finally:
    db.close()
```

---

## Ожидаемые результаты

### Успешная интеграция:
1. ✅ API токен работает
2. ✅ Чаты загружаются из кабинета
3. ✅ События (сообщения) загружаются с cursor pagination
4. ✅ Данные сохраняются в БД (таблицы `chats`, `chat_messages`)
5. ✅ Инкрементальная синхронизация работает (cursor сохраняется)

### Проблемы, требующие workaround:
1. ⚠️ Order ID не приходит → нужна интеграция с Feedbacks API
2. ⚠️ Unread count = 0 → вычислять локально по author_type
3. ⚠️ Timestamp сообщений отсутствует → использовать cursor
4. ⚠️ Негативные отзывы не помечены → интегрировать Feedbacks API

---

## Следующие шаги

После успешного тестирования Chat API:

1. **Интеграция Feedbacks API** (для pending negative reviews)
2. **Интеграция Questions API** (для вопросов от покупателей)
3. **Webhook setup** (если WB добавит в будущем)
4. **UI для просмотра чатов** (frontend)
5. **LLM для автоответов** (интеграция с llm_analyzer.py)

---

## Контакты и ресурсы

- [WB Chat API Documentation](https://dev.wildberries.ru/docs/openapi/user-communication#tag/Chat-s-pokupatelyami)
- [WB Swagger UI](https://dev.wildberries.ru/en/swagger/communications)
- [WB Seller Cabinet](https://seller.wildberries.ru/)
- [Полная документация в проекте](./WB_CHAT_API_RESEARCH.md)
