# AgentIQ Chat Center — План реализации MVP

**Цель:** Sierra для РФ, старт с Wildberries
**Дата:** 2026-02-10

---

## Текущее состояние

| Компонент | Готовность | Статус |
|-----------|-----------|--------|
| FastAPI Backend | 80% | Нет отправки, нет auth |
| React Frontend | 70% | Нет реальной отправки |
| PostgreSQL Schema | 95% | ✅ Готово |
| Ozon Connector | 90% | ✅ Готово (`chat-center/backend/app/services/ozon_connector.py`) |
| **WB Connector** | **95%** | ✅ Готово (`reviews/backend/connectors.py`) |
| Sync Service | 0% | ❌ Не реализовано |
| SLA Calculator | 0% | ❌ Не реализовано |
| AI Suggestions | 0% | ❌ Не реализовано |
| Auth | 0% | ❌ Не реализовано |

### WB Connector — уже реализован

**Файл:** `agentiq/apps/reviews/backend/connectors.py`

```python
class WildberriesConnector:
    fetch_chats()              # GET /api/v1/seller/chats
    fetch_messages()           # GET /api/v1/seller/events (cursor pagination)
    fetch_messages_as_chats()  # Построить чаты из событий (надёжнее)
    send_message()             # POST /api/v1/seller/message
    download_file()            # Скачать вложения
    get_statistics()           # Статистика для dashboard
```

**TODO:** Скопировать в `chat-center/backend/app/services/wb_connector.py` и переписать на async (httpx)

---

## Фаза 1: WB Connector (0.5 дня) ✅ ПОЧТИ ГОТОВО

**Существующий файл:** `agentiq/apps/reviews/backend/connectors.py`
**Целевой файл:** `backend/app/services/wb_connector.py`

### Что уже есть (sync версия)

```python
class WildberriesConnector:
    BASE_URL = "https://buyer-chat-api.wildberries.ru"

    fetch_chats()              # GET /api/v1/seller/chats
    fetch_messages()           # GET /api/v1/seller/events + cursor
    fetch_messages_as_chats()  # Построить чаты из событий
    send_message()             # POST /api/v1/seller/message
    download_file()            # Скачать вложения
    get_statistics()           # Агрегация для dashboard
```

### Что нужно сделать

1. Скопировать в `chat-center/backend/app/services/wb_connector.py`
2. Переписать на async (httpx вместо requests)
3. Добавить retry + exponential backoff
4. Добавить типизацию (Pydantic models)

### Особенности WB API

- **Cursor pagination:** events возвращают cursor для следующей страницы
- **Dedup обязателен:** API может возвращать дубликаты
- **Rate limits:** ~100 req/min (нужен exponential backoff)
- **Формат chat_id:** строка вида "1:UUID"
- **/chats может быть пустой** — использовать `fetch_messages_as_chats()`

---

## Фаза 2: Sync Service (2-3 дня)

**Файл:** `backend/app/tasks/sync.py`

### Celery Tasks

```python
@celery.task
def sync_all_sellers():
    """Запускается каждые 30 секунд"""
    sellers = get_active_sellers()
    for seller in sellers:
        sync_seller_chats.delay(seller.id)

@celery.task(bind=True, max_retries=3)
def sync_seller_chats(self, seller_id: int):
    """Синхронизация чатов одного продавца"""
    # 1. Получить chats из WB API
    # 2. Upsert в БД (by marketplace_chat_id)
    # 3. Получить новые messages (cursor из chat_sync_state)
    # 4. Dedup by external_message_id
    # 5. Обновить chat_sync_state.last_sync_at
```

### Таблица `chat_sync_state`

```sql
-- Уже есть в schema.sql
CREATE TABLE chat_sync_state (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER REFERENCES sellers(id),
    marketplace VARCHAR(20),
    last_cursor TEXT,
    last_sync_at TIMESTAMPTZ,
    error_count INTEGER DEFAULT 0,
    last_error_at TIMESTAMPTZ
);
```

### Celery Beat Schedule

```python
CELERYBEAT_SCHEDULE = {
    'sync-all-sellers': {
        'task': 'app.tasks.sync.sync_all_sellers',
        'schedule': 30.0,  # каждые 30 секунд
    },
}
```

---

## Фаза 3: Message Sending (2 дня)

**Изменить:** `backend/app/api/messages.py`

### Текущее состояние

```python
# Сейчас: только сохраняет в БД
@router.post("/messages")
async def send_message(payload: MessageCreate):
    message = Message(**payload.dict())
    db.add(message)
    return message
```

### Целевое состояние

```python
@router.post("/messages")
async def send_message(payload: MessageCreate, db: AsyncSession):
    # 1. Сохранить в БД со status=pending
    message = Message(**payload.dict(), status="pending")
    db.add(message)
    await db.commit()

    # 2. Получить chat и seller
    chat = await db.get(Chat, payload.chat_id)
    seller = await db.get(Seller, chat.seller_id)

    # 3. Отправить в маркетплейс
    if chat.marketplace == "wildberries":
        connector = WBConnector(seller.api_key)
        result = await connector.send_message(chat.marketplace_chat_id, payload.text)
    elif chat.marketplace == "ozon":
        connector = OzonConnector(seller.client_id, seller.api_key)
        result = await connector.send_message(chat.marketplace_chat_id, payload.text)

    # 4. Обновить статус
    message.status = "sent"
    message.external_message_id = result.get("message_id")
    await db.commit()

    return message
```

### Обработка ошибок

```python
@celery.task(bind=True, max_retries=5)
def retry_send_message(self, message_id: int):
    """Retry отправки при ошибке"""
    try:
        # ... send logic
    except APIError as e:
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
```

---

## Фаза 4: SLA Calculator (1-2 дня)

**Файл:** `backend/app/services/sla_calculator.py`

### Логика приоритизации

```python
class SLACalculator:

    PRIORITY_MINUTES = {
        "urgent": 30,      # Негатив, жалоба
        "high": 120,       # Вопрос по заказу
        "normal": 1440,    # Общий вопрос (24 часа)
    }

    async def calculate(self, chat: Chat, first_message: str) -> tuple[str, datetime]:
        """Возвращает (priority, deadline)"""

        # Проверить SLA rules продавца
        rules = await self.get_seller_rules(chat.seller_id)

        for rule in rules:  # отсортированы по priority
            if self._matches_rule(first_message, rule):
                priority = rule.priority
                deadline = datetime.utcnow() + timedelta(minutes=rule.deadline_minutes)
                return priority, deadline

        # Default: normal priority
        return "normal", datetime.utcnow() + timedelta(minutes=1440)

    def _matches_rule(self, text: str, rule: SLARule) -> bool:
        """Проверка keywords в тексте"""
        if rule.keywords:
            pattern = "|".join(rule.keywords)
            return bool(re.search(pattern, text, re.IGNORECASE))
        return True  # time_based rule без keywords
```

### Фоновая задача: эскалация

```python
@celery.task
def check_sla_escalation():
    """Каждые 5 минут: повышаем приоритет если deadline близко"""

    # Найти чаты где deadline < 30 минут и priority != urgent
    chats = db.query(Chat).filter(
        Chat.sla_deadline_at < datetime.utcnow() + timedelta(minutes=30),
        Chat.sla_priority != "urgent",
        Chat.chat_status.in_(["waiting", "client-replied"])
    ).all()

    for chat in chats:
        chat.sla_priority = "urgent"

    db.commit()
```

### Бизнес-правила (defaults)

| Триггер | Приоритет | Deadline |
|---------|-----------|----------|
| "возврат", "брак", "сломан" | urgent | 30 мин |
| "где заказ", "статус", "доставка" | high | 2 часа |
| Все остальное | normal | 24 часа |
| Нерабочие часы (22:00-09:00) | +1 level | +50% времени |

---

## Фаза 5: AI Suggestions (3-4 дня) ⭐

**Файл:** `backend/app/services/ai_analyzer.py`

### Структура

```python
class AIAnalyzer:

    def __init__(self):
        self.client = httpx.AsyncClient(
            base_url="https://api.deepseek.com/v1",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"}
        )

    async def analyze_chat(self, chat: Chat, messages: list[Message]) -> dict:
        """Анализ чата и генерация рекомендации"""

        # 1. Собрать контекст
        context = await self._build_context(chat, messages)

        # 2. Вызвать LLM
        response = await self._call_llm(context)

        # 3. Парсить результат
        analysis = self._parse_response(response)

        # 4. Сохранить в БД
        chat.ai_analysis_json = analysis
        await self._save_suggestion(chat.id, analysis)

        return analysis

    async def _build_context(self, chat: Chat, messages: list[Message]) -> str:
        """Собрать контекст для LLM"""

        # Последние 10 сообщений
        recent = messages[-10:]

        # Информация о товаре (если есть product_id)
        product_info = await self._fetch_product_info(chat.product_id)

        return f"""
        Товар: {product_info}

        История переписки:
        {self._format_messages(recent)}
        """

    async def _call_llm(self, context: str) -> dict:
        """Вызов DeepSeek API"""

        response = await self.client.post("/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context}
            ],
            "temperature": 0.3,
            "response_format": {"type": "json_object"}
        })

        return response.json()
```

### System Prompt

```python
SYSTEM_PROMPT = """
Ты — эксперт по клиентскому сервису для маркетплейсов.

Проанализируй переписку и верни JSON:
{
    "sentiment": "positive" | "negative" | "neutral",
    "categories": ["complaint", "question", "order_status", ...],
    "urgency": "normal" | "high" | "critical",
    "recommendation": "Готовый текст ответа от лица продавца"
}

ПРАВИЛА для recommendation:
1. Пиши ГОТОВЫЙ текст ответа, НЕ инструкции
2. НИКОГДА не обещай возврат/замену если клиент не просил
3. НИКОГДА не пиши: "вернём деньги", "гарантируем возврат", "ваша вина"
4. НИКОГДА не упоминай: "ИИ", "бот", "автоматический ответ"
5. Если клиент просит возврат → "Оформите возврат через ЛК WB"
6. Тон: профессиональный, эмпатичный, конкретный
"""
```

### Guardrails (из RESPONSE_GUARDRAILS.md)

```python
BANNED_PHRASES = [
    "вернём деньги",
    "гарантируем возврат",
    "полный возврат",
    "бесплатную замену",
    "вы неправильно",
    "ваша вина",
    "обратитесь в поддержку",
    "ИИ", "бот", "нейросеть", "GPT", "ChatGPT",
]

def validate_recommendation(text: str) -> bool:
    """Проверка на banned phrases"""
    for phrase in BANNED_PHRASES:
        if phrase.lower() in text.lower():
            return False
    return True
```

### Формат ai_analysis_json

```json
{
    "sentiment": "negative",
    "categories": ["complaint", "product_quality"],
    "urgency": "high",
    "recommendation": "Благодарим за обратную связь! Нам очень жаль, что товар не оправдал ожиданий. Подскажите, пожалуйста, в чём именно проявился дефект? Мы обязательно передадим информацию в отдел качества.",
    "confidence": 0.85,
    "analyzed_at": "2026-02-10T12:30:00Z"
}
```

---

## Фаза 6: Authentication (2-3 дня)

**Файлы:**
- `backend/app/middleware/auth.py`
- `backend/app/api/auth.py`

### JWT Authentication

```python
# backend/app/api/auth.py

from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

@router.post("/auth/register")
async def register(payload: RegisterRequest, db: AsyncSession):
    """Регистрация нового продавца"""

    # Проверить что email не занят
    existing = await db.execute(
        select(Seller).where(Seller.email == payload.email)
    )
    if existing.scalar():
        raise HTTPException(400, "Email already registered")

    # Создать seller
    seller = Seller(
        email=payload.email,
        password_hash=pwd_context.hash(payload.password),
        company_name=payload.company_name
    )
    db.add(seller)
    await db.commit()

    # Вернуть JWT
    token = create_access_token(seller.id)
    return {"access_token": token, "token_type": "bearer"}

@router.post("/auth/login")
async def login(payload: LoginRequest, db: AsyncSession):
    """Авторизация"""

    seller = await db.execute(
        select(Seller).where(Seller.email == payload.email)
    )
    seller = seller.scalar()

    if not seller or not pwd_context.verify(payload.password, seller.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(seller.id)
    return {"access_token": token, "token_type": "bearer"}
```

### Auth Middleware

```python
# backend/app/middleware/auth.py

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_seller(
    token: str = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Seller:
    """Middleware: проверка JWT и получение текущего seller"""

    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=["HS256"])
        seller_id = payload.get("sub")
    except JWTError:
        raise HTTPException(401, "Invalid token")

    seller = await db.get(Seller, seller_id)
    if not seller:
        raise HTTPException(401, "Seller not found")

    return seller
```

### Seller Isolation

```python
# Все endpoints проверяют ownership

@router.get("/chats/{chat_id}")
async def get_chat(
    chat_id: int,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db)
):
    chat = await db.get(Chat, chat_id)

    # Проверить что чат принадлежит текущему seller
    if chat.seller_id != seller.id:
        raise HTTPException(403, "Access denied")

    return chat
```

### Frontend Auth

```typescript
// frontend/src/services/auth.ts

export const login = async (email: string, password: string) => {
  const response = await axios.post('/api/auth/login', { email, password });
  localStorage.setItem('access_token', response.data.access_token);
  return response.data;
};

// Axios interceptor
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

---

## Фаза 7: Frontend Polish (2 дня)

**Файлы:** `frontend/src/components/*`

### Задачи

1. **Реальная отправка сообщений**
   ```typescript
   const sendMessage = async () => {
     await api.post('/messages', {
       chat_id: selectedChat.id,
       text: messageText,
       direction: 'outgoing'
     });
     setMessageText('');
     refetchMessages();
   };
   ```

2. **AI Suggestion в AIPanel**
   ```tsx
   <div className="ai-suggestion">
     <h4>Рекомендация AI</h4>
     <p>{chat.ai_analysis_json?.recommendation}</p>
     <div className="suggestion-actions">
       <button onClick={() => setMessageText(recommendation)}>
         Вставить
       </button>
       <button onClick={() => sendWithText(recommendation)}>
         Отправить
       </button>
     </div>
   </div>
   ```

3. **Mark as read при открытии**
   ```typescript
   useEffect(() => {
     if (selectedChat?.unread_count > 0) {
       api.post(`/chats/${selectedChat.id}/mark-read`);
     }
   }, [selectedChat?.id]);
   ```

4. **Keyboard shortcuts**
   ```typescript
   const handleKeyDown = (e: KeyboardEvent) => {
     if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
       sendMessage();
     }
   };
   ```

5. **Улучшенный polling / WebSocket**
   ```typescript
   // Вместо polling каждые 10 сек — WebSocket
   const ws = new WebSocket('wss://api.agentiq.ru/ws');
   ws.onmessage = (event) => {
     const data = JSON.parse(event.data);
     if (data.type === 'new_message') {
       addMessage(data.message);
     }
   };
   ```

---

## Архитектура итогового решения

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                              │
│  React 19 + TypeScript + Vite                               │
│  ┌──────────┐ ┌──────────────┐ ┌─────────────┐              │
│  │ ChatList │ │ ChatWindow   │ │ AIPanel     │              │
│  │ 3 queues │ │ messages     │ │ suggestions │              │
│  └──────────┘ └──────────────┘ └─────────────┘              │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                     FastAPI Backend                          │
│  ┌─────────┐ ┌─────────────┐ ┌───────────────┐              │
│  │ Auth    │ │ Chat/Msg API│ │ Seller API    │              │
│  │ JWT     │ │ CRUD        │ │ onboarding    │              │
│  └─────────┘ └──────┬──────┘ └───────────────┘              │
│                     │                                        │
│  ┌──────────────────▼──────────────────────┐                │
│  │           Services Layer                 │                │
│  │  ┌────────────┐ ┌────────────┐          │                │
│  │  │WBConnector │ │OzonConnect │          │                │
│  │  └────────────┘ └────────────┘          │                │
│  │  ┌────────────┐ ┌────────────┐          │                │
│  │  │SLACalc     │ │AIAnalyzer  │──────────┼─► DeepSeek API │
│  │  └────────────┘ └────────────┘          │                │
│  └─────────────────────────────────────────┘                │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Celery + Redis                              │
│  ┌─────────────────┐ ┌─────────────────┐                    │
│  │ sync_chats      │ │ send_message    │                    │
│  │ every 30s       │ │ async + retry   │                    │
│  └─────────────────┘ └─────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   PostgreSQL                                 │
│  sellers │ chats │ messages │ sla_rules │ ai_suggestions    │
└─────────────────────────────────────────────────────────────┘
```

---

## Timeline

| Фаза | Время | Результат | Статус |
|------|-------|-----------|--------|
| 1. WB Connector | 0.5 дня | Async версия | ✅ ГОТОВО |
| 2. Sync Service | 2-3 дня | Автоматическое обновление | ✅ ГОТОВО |
| 3. Message Sending | 2 дня | Ответы уходят в WB | ✅ ГОТОВО |
| 4. SLA Calculator | 1-2 дня | Приоритизация | ✅ ГОТОВО |
| 5. AI Suggestions | 3-4 дня | Автоответы от LLM | ✅ ГОТОВО |
| 6. Auth | 2-3 дня | Безопасность | ✅ ГОТОВО |
| 7. Frontend Polish | 2 дня | UX | ❌ |
| **Итого** | **~2 дня** | **Рабочий MVP** |

---

## Команды для запуска

### Development

```bash
# Terminal 1: PostgreSQL + Redis
docker-compose up -d postgres redis

# Terminal 2: Backend
cd agentiq/apps/chat-center/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Terminal 3: Celery Worker
cd agentiq/apps/chat-center/backend
source venv/bin/activate
celery -A app.tasks worker -l info

# Terminal 4: Celery Beat (scheduler)
celery -A app.tasks beat -l info

# Terminal 5: Frontend
cd agentiq/apps/chat-center/frontend
npm run dev -- --host 0.0.0.0
```

### Production

```bash
# На VPS 79.137.175.164
cd /var/www/agentiq
./deploy.sh
```

---

## Чеклист готовности MVP

- [x] WB Connector: sync версия (list_chats, get_events, send_message)
- [x] WB Connector: async версия (httpx) → `app/services/wb_connector.py`
- [x] Sync: автоматическое обновление каждые 30 сек (Celery) → `app/tasks/sync.py`
- [x] Messages: отправка в WB API из chat-center → `send_message_to_marketplace` task
- [x] SLA: эскалация приоритета → `check_sla_escalation` task
- [x] SLA: расчёт priority в AI analyzer → `AIAnalyzer._calculate_sla_priority()`
- [x] AI: анализ + рекомендация (DeepSeek) → `app/services/ai_analyzer.py`
- [x] AI: periodic analysis → `analyze_pending_chats` task (каждые 2 мин)
- [x] AI: API endpoint → `POST /chats/{id}/analyze`
- [x] Auth: JWT tokens → `app/services/auth.py`
- [x] Auth: middleware → `app/middleware/auth.py`
- [x] Auth: API endpoints → `POST /auth/register`, `/login`, `/me`, `/refresh`
- [x] Auth: seller isolation → все endpoints проверяют ownership
- [ ] Frontend: отправка + AI panel + keyboard shortcuts
- [ ] Tests: unit + integration
- [ ] Deploy: nginx + certbot + systemd

---

## Следующие шаги

1. ~~**Сейчас:** Переписать WB Connector на async~~ ✅ ГОТОВО
2. ~~**Далее:** Фаза 2 (Sync Service) — Celery + Redis polling~~ ✅ ГОТОВО
3. ~~**Далее:** Фаза 3 (Message Sending) — async через Celery~~ ✅ ГОТОВО
4. ~~**Сейчас:** Фаза 5 (AI Suggestions) — DeepSeek интеграция~~ ✅ ГОТОВО
5. ~~**Сейчас:** Фаза 6 (Auth) — JWT + middleware~~ ✅ ГОТОВО
6. **Сейчас:** Фаза 7 (Frontend) — AI panel, keyboard shortcuts, login UI
7. **После MVP:** Ozon (уже есть connector), Yandex Market, Avito
