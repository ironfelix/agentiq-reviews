# Ozon Chat API — Тестирование

## 🔐 Получение credentials

1. Зайти в личный кабинет продавца: https://seller.ozon.ru/
2. **Настройки → API ключи** (`/app/settings/api-keys`)
3. Создать новый API-ключ с правами **"Чат с покупателями"**
4. Скопировать:
   - **Client-Id** (числовой ID)
   - **Api-Key** (UUID формат)

---

## 🧪 Sandbox окружение

**Статус**: Ozon sandbox (`http://cb-api.ozonru.me`) **недоступен** (403 Forbidden по состоянию на 2026-02-08).

**Альтернативы**:
- Использовать реальные credentials с production API (`https://api-seller.ozon.ru`)
- Mock-тесты (см. `test_ozon_mock.py`)
- Unit-тесты с pytest (Week 2)

---

## 📝 Ручное тестирование через curl

### 1. Получить список чатов

```bash
curl -X POST https://api-seller.ozon.ru/v1/chat/list \
  -H "Client-Id: YOUR_CLIENT_ID" \
  -H "Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "offset": 0
  }'
```

**Ожидаемый ответ**:
```json
{
  "result": {
    "chats": [
      {
        "chat_id": "chat-12345",
        "chat_type": "Buyer_Seller",
        "chat_status": "opened",
        "created_at": "2026-02-07T10:00:00Z",
        "unread_count": 2
      }
    ],
    "total": 1
  }
}
```

### 2. Получить историю чата

```bash
# Замените CHAT_ID на реальный chat_id из предыдущего запроса
curl -X POST https://api-seller.ozon.ru/v1/chat/history \
  -H "Client-Id: YOUR_CLIENT_ID" \
  -H "Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "CHAT_ID",
    "limit": 50
  }'
```

### 3. Получить новые сообщения (updates)

```bash
curl -X POST https://api-seller.ozon.ru/v1/chat/updates \
  -H "Client-Id: YOUR_CLIENT_ID" \
  -H "Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 50
  }'
```

### 4. Отправить сообщение

```bash
curl -X POST https://api-seller.ozon.ru/v1/chat/send/message \
  -H "Client-Id: YOUR_CLIENT_ID" \
  -H "Api-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "chat_id": "CHAT_ID",
    "text": "Здравствуйте! Чем могу помочь?"
  }'
```

---

## 🐍 Тестирование через Python

### Вариант 1: Standalone скрипт (без установки backend)

```python
#!/usr/bin/env python3
import asyncio
import httpx
import json

CLIENT_ID = "YOUR_CLIENT_ID"
API_KEY = "YOUR_API_KEY"
BASE_URL = "https://api-seller.ozon.ru"

async def test_api():
    headers = {
        "Client-Id": CLIENT_ID,
        "Api-Key": API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        # Получить список чатов
        response = await client.post(
            f"{BASE_URL}/v1/chat/list",
            headers=headers,
            json={"limit": 10, "offset": 0}
        )

        print(json.dumps(response.json(), indent=2, ensure_ascii=False))

asyncio.run(test_api())
```

### Вариант 2: Через OzonConnector (нужен backend)

```python
import asyncio
from app.services.ozon_connector import OzonConnector

async def test():
    connector = OzonConnector(
        client_id="YOUR_CLIENT_ID",
        api_key="YOUR_API_KEY"
    )

    # Получить чаты
    chats = await connector.list_chats(limit=10)
    print(chats)

    # Получить историю
    if chats.get("result", {}).get("chats"):
        chat_id = chats["result"]["chats"][0]["chat_id"]
        history = await connector.get_chat_history(chat_id, limit=20)
        print(history)

asyncio.run(test())
```

---

## 🧪 Mock-тесты (без реального API)

```bash
cd backend
python3 test_ozon_mock.py
```

Mock-тесты проверяют логику OzonConnector с поддельными ответами (без реальных запросов к Ozon).

---

## ⚠️ Rate Limits

- **Production**: 500 запросов/минуту
- **Рекомендация**: Polling каждые 60 секунд (Celery task)

---

## 📚 Дополнительно

- **Ozon Docs**: https://docs.ozon.ru/api/seller/
- **Swagger UI**: https://api-seller.ozon.ru/swagger/index.html
- **Backend README**: `README.md`
- **OzonConnector код**: `app/services/ozon_connector.py`

---

## 🔒 Безопасность

**ВАЖНО**: Никогда не коммитьте реальные credentials в Git!

```bash
# Добавьте в .gitignore
.env
*.env
*_credentials.txt
```

Используйте:
- `.env` файл для локальной разработки
- Environment variables для production
- Encrypted storage в БД (Fernet) для multi-seller
