# Marketplace Communication APIs — Research

**Last updated:** 2026-02-18
**Status:** Research (план, не реализовано)
**Author:** AgentIQ

Сравнительный анализ API коммуникаций на **Яндекс Маркет** и **Авито** для повторных продаж и роста конверсии. Контекст: уже есть WB Chat API (см. `WB_CHAT_API_RESEARCH.md`).

---

## 1. Яндекс Маркет Partner API — Коммуникации

### 1.1 Аутентификация
- **Метод:** API-Key в заголовке
- **Ключ создаётся:** в ЛК партнёра → Настройки → API
- **Необходимые scope:** `communication` (или `all-methods`)
- **Base URL:** `https://api.partner.market.yandex.ru`
- **Rate limit:** 10 000 запросов/час

### 1.2 Чат с покупателем — Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/v2/businesses/{businessId}/chats` | Список чатов (с фильтрацией) |
| `GET` | `/v2/businesses/{businessId}/chat` | Получить один чат |
| `POST` | `/v2/businesses/{businessId}/chats/new` | Создать новый чат |
| `POST` | `/v2/businesses/{businessId}/chats/history` | История сообщений |
| `GET` | `/v2/businesses/{businessId}/chats/message` | Конкретное сообщение |
| `POST` | `/v2/businesses/{businessId}/chats/message` | **Отправить сообщение** |
| `POST` | `/v2/businesses/{businessId}/chats/file/send` | Отправить файл |

### 1.3 Типы чатов
- **ORDER** — обсуждение заказа (FBY, FBS, Экспресс)
- **RETURN** — по возвратам
- **DIRECT** — покупатель сам начал чат по вопросу о товаре (продавец не может инициировать)

**Ключевое:** продавец МОЖЕТ создавать чаты по заказам/возвратам (`/chats/new`). Контекст чата содержит `orderId`, тип, данные покупателя.

### 1.4 Данные в чате (response)
```json
{
  "orderId": 123,
  "context": {
    "type": "ORDER|RETURN|DIRECT",
    "customer": {"name": "string", "publicId": "string"},
    "campaignId": 1,
    "orderId": 1,
    "returnId": 1
  },
  "messages": [{
    "messageId": 1,
    "createdAt": "ISO8601",
    "sender": "PARTNER|CUSTOMER|MARKET|SUPPORT",
    "message": "string",
    "payload": [{"name": "string", "url": "string", "size": 0}]
  }]
}
```

**Gap vs WB:** YM ДАЁТ orderId в чате → можно автоматически связывать чат с заказом.

### 1.5 Фильтрация чатов
```json
{"statuses": ["WAITING_FOR_PARTNER"]}
```
Фильтр `WAITING_FOR_PARTNER` — найти все чаты, где нужен ответ продавца.

### 1.6 Webhook-уведомления (Push Notifications)
Настройка: в ЛК партнёра указать HTTPS-endpoint.

| Тип события | Когда | Что делать |
|-------------|-------|------------|
| `CHAT_CREATED` | Создан новый чат | Сохранить chatId, вызвать `GET /chat` |
| `CHAT_MESSAGE_SENT` | Новое сообщение | Получить через `/chats/history` или `/chats/message` |
| `NEW_FEEDBACK` | Новый отзыв/комментарий | Получить через `/goods-feedback/comments` |
| `PING` | Проверка интеграции | Ответить 200 |

**Timeout:** 10 секунд на ответ.
**Retry-логика:** если Маркет получил не-200, повторит запрос.
**Задержка активации:** уведомления начинают приходить через ~2 минуты после настройки.

**Код ошибок для ответа:**
- `WRONG_EVENT_FORMAT` — неправильный тип
- `DUPLICATED_EVENT` — дубль (нужен dedup по eventId!)
- `UNKNOWN` — прочие ошибки

### 1.7 Отзывы о товарах — Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/v2/businesses/{businessId}/goods-feedback` | Список отзывов (50/стр) |
| `POST` | `/v2/businesses/{businessId}/goods-feedback/comments` | Комментарии к отзывам |
| `POST` | `/v2/businesses/{businessId}/goods-feedback/comments/update` | Добавить/изменить ответ |
| `POST` | `/v2/businesses/{businessId}/goods-feedback/comments/delete` | Удалить ответ |
| `POST` | `/v2/businesses/{businessId}/goods-feedback/skip-reaction` | Отметить как обработанный |

**Фильтр:** `NEED_REACTION` — отзывы без ответа продавца.
**Автоуведомления:** webhook `NEW_FEEDBACK` при появлении нового отзыва.

---

## 2. Авито Messenger API — Коммуникации

### 2.1 Аутентификация
- **Метод:** OAuth 2.0
- **Base URL:** `https://api.avito.ru`
- **Scopes:**
  - `messenger:read` — чтение сообщений
  - `messenger:write` — отправка сообщений

### 2.2 Messenger API v3 — Endpoints

| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/messenger/v3/accounts/{user_id}/chats` | Список чатов |
| `GET` | `/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages` | Сообщения в чате |
| `POST` | `/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages` | **Отправить сообщение** |
| `POST` | `/messenger/v3/webhook` | Зарегистрировать webhook |
| `GET` | `/messenger/v1/subscriptions` | Активные подписки |

### 2.3 Webhooks
- Регистрация: `POST /messenger/v3/webhook` → возвращает `"ok"`
- Проверка: `GET /messenger/v1/subscriptions` → текущий webhook URL
- **Retry:** до 10 попыток с задержкой 60 сек при non-200 ответе
- **Требование:** webhook URL должен быть публично доступен из интернета

### 2.4 Особенности Авито vs маркетплейсы
- **Авито — C2C + B2C:** много объявлений на частных лиц, покупатель часто не знает что покупает у бизнеса
- **Контекст чата:** привязан к объявлению (`item_id`), не к заказу
- **Нет отдельного API отзывов** в открытом доступе — только профиль продавца с рейтингом
- **Нет тарифов на чат** — общение бесплатно
- **Сила:** огромная аудитория, особенно б/у товары, авто, недвижимость, локальные услуги

---

## 3. Сравнительная таблица: WB vs Яндекс Маркет vs Авито

| Параметр | Wildberries | Яндекс Маркет | Авито |
|----------|-------------|---------------|-------|
| **Chat API** | ✅ v1 | ✅ v2 | ✅ v3 |
| **Webhooks** | ❌ (polling) | ✅ HTTPS push | ✅ HTTPS push |
| **orderId в чате** | ❌ Gap | ✅ Есть | N/A (item_id) |
| **Инициирование чата продавцом** | ❌ | ✅ (по заказу/возврату) | ❌ |
| **Отзывы API** | ✅ WBCON | ✅ goods-feedback | ❌ нет публичного |
| **Ответ на отзыв** | ✅ | ✅ | ❌ |
| **Фильтр "нужен ответ"** | Нет | ✅ WAITING_FOR_PARTNER | N/A |
| **Rate limit** | Не задокументирован | 10 000 req/h | Не задокументирован |
| **Auth** | Bearer JWT | API-Key | OAuth 2.0 |
| **Тариф на чат** | +0.5-0.7% комиссии | Включён | Бесплатно |
| **Тариф на отложенный негатив** | +~1% | Нет такого | Нет такого |

---

## 4. Возможности для повторных продаж и роста конверсии

### 4.1 Яндекс Маркет — сильные стороны для повторных продаж

#### Связь чат → заказ → CRM
YM единственный из трёх даёт `orderId` в контексте чата. Это позволяет:
1. Автоматически тегировать покупателя в CRM по истории заказов
2. Персонализировать ответ ("Ваш заказ #123 с доставкой 15 февраля...")
3. Проактивно открыть чат при проблеме (returns, delay)

#### Проактивные чаты по заказам
Продавец может СНАЧАЛА написать покупателю по заказу:
```
POST /v2/businesses/{businessId}/chats/new
{"type": "ORDER", "orderId": 123}
```
Сценарии:
- Уведомить о задержке до того, как покупатель напишет сам
- Напомнить об условиях ухода за товаром после доставки (cross-sell)
- Попросить оставить отзыв (осторожно — не нарушать правила YM)

#### Webhook-воронка для конверсии
`CHAT_CREATED` с типом `DIRECT` = покупатель СЕЙЧАС смотрит товар и задаёт вопрос.
→ SLA критичный: ответ за <2 минут → +20-30% к конверсии в покупку.
→ AI auto-response при наличии шаблонных вопросов (размер, наличие, доставка)

#### Отзывы: автоматизация ответов
- Webhook `NEW_FEEDBACK` → сразу анализ тональности → AI драфт ответа
- Фильтр `NEED_REACTION` → очередь необработанных отзывов
- YM позволяет редактировать свой ответ (в отличие от WB)

### 4.2 Авито — сильные стороны

#### Аудитория и охват
- 50М+ активных пользователей в месяц
- Уникальная ниша: вещи, б/у, авто, недвижимость, услуги
- Не конкурирует с WB/YM — дополняет (другой покупательский intent)

#### Чат как основной канал продаж
На Авито 80%+ продаж происходят через чат. Каждый запрос в чате — горячий лид.
- Скорость ответа = прямая конверсия
- Webhook + AI auto-response → отвечать 24/7 без менеджера

#### Повторные продажи через чат
Авито не запрещает писать покупателям, которые уже писали вам:
- После покупки: напомнить о расходниках, аксессуарах (если уместно)
- При новых поступлениях похожих товаров
- Сезонные предложения

**Ограничение:** нет order-based связи, только item-based история чатов.

### 4.3 Сравнение ROI для AgentIQ

| Сценарий | WB | YM | Авито |
|----------|----|----|-------|
| AI ответ на отзыв | Высокий ROI | Высокий ROI | Нет API |
| AI ответ в чат | Высокий ROI | Высокий ROI | Высокий ROI |
| Проактивный чат продавца | ❌ | ✅ HIGH | ❌ |
| Webhook-driven (реальный RT) | ❌ polling | ✅ | ✅ |
| Связь с заказом в CRM | Вручную | Автоматически | По item |

---

## 5. Технические требования для интеграции

### 5.1 Яндекс Маркет
```python
# Базовая структура коннектора
YM_BASE_URL = "https://api.partner.market.yandex.ru"
YM_HEADERS = {"Api-Key": "<seller_api_key>"}

# Получить чаты требующие ответа
POST /v2/businesses/{businessId}/chats
{"statuses": ["WAITING_FOR_PARTNER"]}

# Отправить сообщение
POST /v2/businesses/{businessId}/chats/message
{"chatId": 123, "message": "Добрый день! ..."}

# Webhook handler
POST /notification
{
  "type": "CHAT_CREATED|CHAT_MESSAGE_SENT|NEW_FEEDBACK|PING",
  "chatId": 123,
  "businessId": 456
}
```

### 5.2 Авито
```python
# OAuth flow
AVITO_AUTH_URL = "https://avito.ru/oauth"
AVITO_BASE_URL = "https://api.avito.ru"

# Scopes: messenger:read messenger:write

# Получить список чатов
GET /messenger/v3/accounts/{user_id}/chats

# Отправить сообщение
POST /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages
{"message": {"text": "Добрый день!"}}

# Зарегистрировать webhook
POST /messenger/v3/webhook
{"url": "https://agentiq.ru/api/webhooks/avito"}
```

### 5.3 Deduplication (ОБЯЗАТЕЛЬНО)
Оба API могут слать дублирующие webhook-события:
- YM: код ошибки `DUPLICATED_EVENT` → ответить 400
- Авито: dedup по `chat_id` + `message_id` + timestamp

---

## 6. Приоритеты интеграции для AgentIQ MVP

### Фаза 1 (сейчас): WB только ✅
- WB Chat API + WBCON уже работают
- Фокус на качестве AI ответов

### Фаза 2 (после MVP): Яндекс Маркет
**Почему YM вторым:**
1. Webhook (не нужен polling каждые 30 сек) → меньше нагрузки на Celery
2. orderId в чате → лучший CRM-контекст
3. Проактивные чаты → уникальная фича
4. Отзывы API → аналогичен WB workflow

**Трудозатраты:** ~3-5 дней (новый connector + webhook handler + тесты)

### Фаза 3: Авито
**Почему Авито третьим:**
1. OAuth сложнее Bearer (per-seller flows)
2. Нет API отзывов (половина ценности AgentIQ отрезана)
3. Другая бизнес-модель (C2C) — нужны новые шаблоны
4. Но: огромная аудитория, уникальная ниша

**Трудозатраты:** ~5-7 дней (OAuth + connector + AI шаблоны под C2C tone)

---

## 7. Критические ограничения

### Яндекс Маркет
- ❌ **Нет чата с покупателями на FBY** (только FBS, DBS, Экспресс для ORDER)
- ❌ **DIRECT чат** — продавец не может создавать, только отвечать
- ⚠️ Timeout webhook — 10 сек (AI ответ нужно генерить асинхронно)
- ⚠️ Rate limit 10K/h — при большом объёме нужна очередь

### Авито
- ❌ **Нет API отзывов** — ключевой пробел
- ❌ **Нет order-контекста** в чатах — только item
- ⚠️ OAuth per-user — каждый продавец проходит авторизацию отдельно
- ⚠️ Webhook должен быть публично доступен (prod-only, не localhost)

---

## Sources
- [YM Chat API docs](https://yandex.ru/dev/market/partner-api/doc/ru/step-by-step/chats)
- [YM Goods Feedback](https://yandex.ru/dev/market/partner-api/doc/ru/step-by-step/goods-feedback)
- [YM Push Notifications](https://yandex.ru/dev/market/partner-api/doc/ru/push-notifications/)
- [YM Notification API GitHub](https://github.com/yandex-market/yandex-market-notification-api)
- [Avito API Portal](https://developers.avito.ru)
- [Avito Messenger Docs](https://developers.avito.ru/api-catalog/messenger/documentation)
- [WB Chat API Research](../chat-center/WB_CHAT_API_RESEARCH.md)
