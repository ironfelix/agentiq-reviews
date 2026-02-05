# AgentIQ AI Core — Architecture

## Vision

AI-платформа для customer service в РФ. Аналог Sierra.ai для российского рынка.

---

## Core Architecture

```
┌─────────────────────────────────────────────┐
│            AgentIQ AI Core                  │
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────────────────────────────────┐  │
│  │         Unified Inbox                 │  │
│  │   Telegram · Email · WB · Ozon · VK   │  │
│  │   WhatsApp · Website Widget           │  │
│  └───────────────────────────────────────┘  │
│                     ↓                       │
│  ┌───────────────────────────────────────┐  │
│  │           AI Agent Engine             │  │
│  │  • Intent detection                   │  │
│  │  • Context retrieval (заказы, CRM)    │  │
│  │  • Response generation                │  │
│  │  • Action execution                   │  │
│  └───────────────────────────────────────┘  │
│                     ↓                       │
│  ┌───────────────────────────────────────┐  │
│  │           Analytics Module            │  │
│  │  • Паттерны жалоб                     │  │
│  │  • Тренды по товарам                  │  │
│  │  • Рекомендации                       │  │
│  └───────────────────────────────────────┘  │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Modules

### 1. Unified Inbox
Единое окно для всех каналов коммуникации.

**Каналы:**
| Категория | Каналы |
|-----------|--------|
| Мессенджеры | Telegram, WhatsApp Business, VK |
| Маркетплейсы | WB чат + отзывы, Ozon чат + отзывы, Яндекс.Маркет |
| Классика | Email (IMAP/SMTP), Website widget |

### 2. AI Agent Engine
Ядро обработки обращений.

**Capabilities:**
- **Intent Detection** — понимание намерения клиента
- **Context Retrieval** — получение данных о заказе, клиенте из CRM
- **Response Generation** — генерация персонализированного ответа
- **Action Execution** — выполнение действий (возврат, статус, эскалация)

**Integrations:**
| US (Sierra) | РФ (AgentIQ) |
|-------------|--------------|
| Zendesk, Salesforce | Bitrix24, AmoCRM, RetailCRM |
| Shopify, BigCommerce | WB, Ozon, Яндекс.Маркет |
| Stripe | ЮKassa, Тинькофф |

### 3. Analytics Module
Аналитика обращений и отзывов (текущий AgentIQ).

**Features:**
- Классификация жалоб по паттернам
- Сравнение вариантов товара
- Тренды и аномалии
- Рекомендации по действиям
- Генерация ответов

---

## Product Structure

**AgentIQ** = бренд платформы

| Модуль | Описание |
|--------|----------|
| **AgentIQ Core** | AI движок для обработки обращений |
| **AgentIQ Inbox** | Unified inbox всех каналов |
| **AgentIQ Analytics** | Анализ отзывов и обращений |
| **AgentIQ Studio** | No-code builder для настройки агентов |

---

## MVP Roadmap

### Phase 1: Analytics (current)
- [x] Анализ отзывов WB
- [x] Классификация по паттернам
- [x] Генерация ответов
- [ ] Dashboard

### Phase 2: First Channel
- [ ] Telegram-бот для селлеров
- [ ] Дайджест новых отзывов
- [ ] One-click ответы

### Phase 3: Unified Inbox
- [ ] Email integration
- [ ] WB/Ozon чат
- [ ] Web widget

### Phase 4: AI Agent Engine
- [ ] Intent detection
- [ ] CRM integration (Bitrix24)
- [ ] Action execution

---

## Tech Stack (planned)

| Layer | Technology |
|-------|------------|
| Frontend | React / Next.js |
| Backend | Python (FastAPI) |
| AI/LLM | Claude API / OpenAI |
| Database | PostgreSQL + Redis |
| Queue | Celery / RabbitMQ |
| Hosting | Yandex Cloud / VPS |

---

## Reference

- [Sierra.ai](https://sierra.ai) — US reference product
- Agent OS, Agent Studio, Agent SDK concepts
