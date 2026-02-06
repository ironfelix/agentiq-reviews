# AgentIQ AI Core — Architecture

## Vision

AI-платформа для customer service в РФ. Аналог Sierra.ai для российского рынка.

---

## Sierra.ai — Reference Architecture (полная)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              SIERRA PLATFORM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         AGENT OS (ядро)                             │   │
│  │  • Constellation of Models (15+ моделей под разные задачи)          │   │
│  │  • Orchestration (оркестрация между моделями)                       │   │
│  │  • Memory (память о клиенте между сессиями)                         │   │
│  │  • Supervisors (контроль качества в реалтайме)                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌───────────────────────┬───────────────────────┬─────────────────────┐   │
│  │     AGENT STUDIO      │      AGENT SDK        │   AGENT DATA        │   │
│  │     (no-code)         │      (developers)     │   PLATFORM          │   │
│  ├───────────────────────┼───────────────────────┼─────────────────────┤   │
│  │ • Journeys (сценарии) │ • Declarative code    │ • Memory store      │   │
│  │ • Knowledge mgmt      │ • CI/CD интеграция    │ • Data warehouse    │   │
│  │ • Brand настройки     │ • Multi-agent         │   (Snowflake,       │   │
│  │ • Simulations         │   orchestration       │    Databricks)      │   │
│  │ • Workspaces (git     │ • Custom skills       │ • Recommendations   │   │
│  │   для агентов)        │ • Fine-tuning         │ • Personalization   │   │
│  └───────────────────────┴───────────────────────┴─────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          КАНАЛЫ                                     │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐ │   │
│  │  │  Chat   │ │  Voice  │ │  Email  │ │   SMS   │ │   WhatsApp    │ │   │
│  │  │ (web)   │ │(телефон)│ │         │ │         │ │   + ChatGPT   │ │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌───────────────────────┬─────────────────────────────────────────────┐   │
│  │        VOICE          │              LIVE ASSIST                    │   │
│  │   (отдельный модуль)  │         (copilot для людей)                 │   │
│  ├───────────────────────┼─────────────────────────────────────────────┤   │
│  │ • Inbound calls       │ • Real-time подсказки оператору             │   │
│  │ • Outbound calls      │ • Авто-генерация ответов                    │   │
│  │ • Language detection  │ • One-click actions                         │   │
│  │ • Sentiment по голосу │ • Customer context                          │   │
│  │ • Voicemail handling  │ • Обучение из каждого диалога              │   │
│  │ • IVR интеграция      │                                             │   │
│  └───────────────────────┴─────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                          INSIGHTS                                   │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐  │   │
│  │  │  Explorer   │ │  Monitors   │ │ Experiments │ │  Dashboards  │  │   │
│  │  │ (deep       │ │ (real-time  │ │ (A/B тесты) │ │  (метрики)   │  │   │
│  │  │  research)  │ │  alerts)    │ │             │ │              │  │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘  │   │
│  │                                                                     │   │
│  │  • CSAT, Resolution rate, Handle time                              │   │
│  │  • Conversation tagging & categorization                           │   │
│  │  • Pattern recognition                                              │   │
│  │  • Expert Answers (AI отвечает на вопросы о данных)                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                       INTEGRATIONS                                  │   │
│  │  CRM: Salesforce, Zendesk, ServiceNow                              │   │
│  │  Data: Snowflake, Databricks, BigQuery                             │   │
│  │  Commerce: Shopify, BigCommerce                                     │   │
│  │  Call Centers: любая платформа                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    ↓                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TRUST & SECURITY                                 │   │
│  │  SOC 2 · ISO 27001 · HIPAA · GDPR · Data governance                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sierra — Детали модулей

### Agent OS (ядро)

**Constellation of Models:**
- 15+ моделей (frontier, open-source, proprietary)
- Каждая модель для своей задачи
- Автоматическая оркестрация

**Skills (навыки):**
- Triage — понять intent
- Respond — сгенерировать ответ
- Confirm — уточнить детали
- Escalate — передать человеку
- Action — выполнить действие в системе

**Journeys (сценарии):**
- Описываются на plain English
- "Когда клиент хочет вернуть товар: спросить номер заказа → проверить → оформить"
- Composable — можно комбинировать

**Supervisors:**
- Guardrails (что нельзя говорить)
- Policy compliance
- Brand tone enforcement

### Agent Studio (no-code)

- Создание Journeys без кода
- Knowledge management (FAQ, docs, policies)
- Brand настройки (имя, тон, цвета)
- Simulations — тестирование на 1000 диалогов
- Workspaces — git-подобная система для команд

### Agent SDK (developers)

- Declarative development
- CI/CD tooling
- Multi-agent orchestration
- Custom skills
- Fine-tuning

### Voice

**Inbound:**
- Понимание естественной речи
- Auto language detection
- Sentiment analysis по голосу
- Entity extraction (даты, номера)

**Outbound:**
- Исходящие звонки
- Voicemail detection
- IVR navigation
- Мгновенный ответ (без пауз)

**Интеграция:**
- Работает с любым call center
- Может стоять перед/после IVR
- Эскалация на человека с саммари

### Live Assist (copilot)

- Real-time подсказки оператору
- Авто-генерация ответов
- One-click actions (возврат, статус)
- Customer context на экране
- Обучение из каждого диалога

### Insights

**Explorer:**
- Deep research по диалогам
- "Почему выросли запросы о возвратах?"
- Анализ тысяч разговоров за секунды

**Monitors:**
- Real-time алерты
- Отслеживание guardrails

**Experiments:**
- A/B тесты поведения агента
- Тестирование hand-off rules

**Dashboards:**
- CSAT, Resolution rate, Handle time
- Conversation tagging
- Pattern recognition

---

## AgentIQ — РФ адаптация

```
AgentIQ (РФ аналог Sierra)
│
├── Core
│   ├── Agent Engine (LLM оркестрация)
│   ├── Memory (Redis/Postgres)
│   └── Supervisors (guardrails)
│
├── Build
│   ├── Studio (no-code) ← потом
│   └── SDK (Python) ← сейчас
│
├── Channels
│   ├── Chat (Jivo webhook / свой SDK)
│   ├── Telegram
│   ├── WhatsApp Business
│   ├── Email
│   ├── WB/Ozon чаты
│   └── Voice ← потом
│
├── Assist
│   └── Live Assist (copilot для операторов) ← потом
│
├── Insights
│   ├── Analytics (текущий AgentIQ!) ✓
│   ├── Dashboards
│   └── Experiments
│
├── Integrations
│   ├── Bitrix24, AmoCRM, RetailCRM
│   ├── WB, Ozon, Яндекс.Маркет API
│   └── ЮKassa, Тинькофф
│
└── Trust
    └── 152-ФЗ compliance
```

---

## Сравнение Sierra vs AgentIQ

| Компонент | Sierra (US) | AgentIQ (РФ) |
|-----------|-------------|--------------|
| **CRM** | Salesforce, Zendesk | Bitrix24, AmoCRM, RetailCRM |
| **Commerce** | Shopify, BigCommerce | WB, Ozon, Яндекс.Маркет |
| **Payments** | Stripe | ЮKassa, Тинькофф |
| **Messengers** | WhatsApp, SMS | Telegram, WhatsApp, VK |
| **Compliance** | SOC 2, HIPAA, GDPR | 152-ФЗ |
| **Voice** | US telephony | РФ телефония (Mango, Sipuni) |

---

## MVP Roadmap

### Phase 1: Analytics (current) ✓
- [x] Анализ отзывов WB
- [x] Классификация по паттернам
- [x] Генерация ответов
- [ ] Dashboard

### Phase 2: Sales Agent
- [ ] Telegram-бот AI-продавец
- [ ] База знаний (knowledge.md)
- [ ] Jivo webhook интеграция
- [ ] CRM интеграция (Bitrix24)

### Phase 3: Support Agent
- [ ] Intent detection
- [ ] Multi-channel (Telegram + Email + Web)
- [ ] Action execution
- [ ] Escalation to human

### Phase 4: Voice
- [ ] Inbound calls
- [ ] РФ телефония интеграция
- [ ] Outbound calls

### Phase 5: Live Assist
- [ ] Copilot для операторов
- [ ] Real-time подсказки

### Phase 6: Studio
- [ ] No-code builder
- [ ] Journey designer
- [ ] Simulations

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React / Next.js |
| Backend | Python (FastAPI) |
| AI/LLM | Claude API / OpenAI |
| Database | PostgreSQL + Redis |
| Queue | Celery / RabbitMQ |
| Hosting | Yandex Cloud / VPS |
| Voice | Mango Office / Sipuni API |

---

## Reference

- [Sierra.ai](https://sierra.ai) — US reference
- [Agent Studio](https://sierra.ai/product/configure-your-agent)
- [Agent SDK](https://sierra.ai/product/develop-your-agent)
- [Voice](https://sierra.ai/product/voice)
- [Live Assist](https://sierra.ai/blog/live-assist)
- [Insights](https://sierra.ai/blog/insights)
- [Agent OS 2.0](https://sierra.ai/blog/agent-os-2-0)
- [Constellation of Models](https://sierra.ai/blog/constellation-of-models)
