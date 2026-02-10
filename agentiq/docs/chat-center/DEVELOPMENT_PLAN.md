# Development Plan — 4 недели до MVP+

## Week 1: Foundation (БД + Backend skeleton + Ozon API)

### Day 1-2: Database & Models
- [ ] Setup PostgreSQL (local + Docker)
- [ ] Применить schema.sql (sellers, chats, messages, sla_rules, filters)
- [ ] SQLAlchemy models (app/models/)
- [ ] Alembic migrations setup
- [ ] Seed data для тестирования

### Day 3-4: Ozon Connector
- [ ] Реализовать OzonConnector (services/ozon_connector.py)
  - list_chats()
  - get_messages()
  - send_message()
  - send_file()
- [ ] Unit tests для connector
- [ ] Mock Ozon API responses

### Day 5-7: FastAPI Skeleton
- [ ] Setup FastAPI app (main.py, config.py)
- [ ] Auth middleware (JWT)
- [ ] API endpoints (sellers, chats, messages)
- [ ] Pydantic schemas
- [ ] API documentation (Swagger)
- [ ] Error handling middleware

**Milestone 1:** Backend запускается, можно добавить seller и вызвать Ozon API

---

## Week 2: Sync + React UI

### Day 8-9: Background Sync
- [ ] Setup Celery + Redis
- [ ] Реализовать sync_chats_task
  - Polling каждые 60s
  - Incremental sync (timestamp-based)
  - Deduplication по message_id
- [ ] Реализовать process_sla_task
- [ ] Celery Beat schedule
- [ ] Monitoring (logs, Flower)

### Day 10-12: React Setup + ChatList
- [ ] Create React app (Vite + TypeScript)
- [ ] Адаптировать CSS из HTML прототипа
- [ ] Реализовать ChatList компонент
  - ChatItem с marketplace icon
  - UnreadBadge
  - SLATimer
  - SearchBox
- [ ] Zustand store (chatStore)
- [ ] API integration (axios/fetch)

### Day 13-14: ChatWindow + MessageList
- [ ] Реализовать ChatWindow компонент
- [ ] MessageList с auto-scroll
- [ ] Message с attachments
- [ ] MessageInput (textarea + send button)
- [ ] Polling messages (каждые 10s для активного чата)

**Milestone 2:** UI показывает чаты и сообщения, можно читать историю

---

## Week 3: Sending + AI + SLA

### Day 15-16: Отправка сообщений
- [ ] POST /chats/{id}/messages endpoint
- [ ] Optimistic updates в UI
- [ ] Message status (sending → sent → delivered → read)
- [ ] Error handling (retry logic)
- [ ] File upload (POST /chats/{id}/messages/file)

### Day 17-18: AI Suggestions
- [ ] AIService (DeepSeek integration)
  - Analyze chat context
  - Generate suggestion
  - Format response
- [ ] POST /ai/suggest endpoint
- [ ] AISuggestion компонент в UI
- [ ] Copy to input / Edit before send

### Day 19-21: SLA система
- [ ] SLACalculator (calculate_sla_deadline)
- [ ] SLA rules CRUD API
- [ ] process_sla_task (проверка дедлайнов)
- [ ] SLA timer UI (countdown, progress bar)
- [ ] Уведомления при истечении SLA
- [ ] Urgent filter в ChatList

**Milestone 3:** Можно отправлять сообщения, получать AI suggestions, видеть SLA таймеры

---

## Week 4: Filters + Multi-seller + Polish + Testing

### Day 22-23: Фильтры
- [ ] Filters API (GET /chats с query params)
- [ ] Saved filters CRUD
- [ ] Filters UI (quick filters + advanced)
- [ ] Sorting (по дате, SLA, unread count)

### Day 24-25: Multi-seller
- [ ] Multi-seller support в UI
- [ ] Switch между sellers (dropdown)
- [ ] Seller management page
- [ ] Credentials encryption (Fernet)

### Day 26-27: Polish & Testing
- [ ] Bug fixes
- [ ] UI polish (animations, loading states)
- [ ] Unit tests (backend)
- [ ] Component tests (frontend)
- [ ] E2E tests (Playwright)
- [ ] Documentation (README, API docs)

### Day 28: Demo & Deploy
- [ ] Docker compose (PostgreSQL + Redis + FastAPI + Celery)
- [ ] .env.example
- [ ] QUICKSTART.md
- [ ] Demo video / screenshots
- [ ] Deploy на VPS (DigitalOcean/Hetzner)

**Milestone 4 (MVP+):** Полнофункциональный чат-центр готов для пилотов

---

## Риски и митигация

### Риск 1: Ozon API лимиты
**Вероятность:** Средняя
**Влияние:** Высокое
**Митигация:**
- Exponential backoff при 429 ошибках
- Rate limiter на стороне приложения
- Batch requests где возможно

### Риск 2: Polling delays (60s слишком медленно)
**Вероятность:** Низкая
**Влияние:** Среднее
**Митигация:**
- Уменьшить до 30s для urgent чатов
- WebSocket fallback (Phase 2)

### Риск 3: DeepSeek медленный / дорогой
**Вероятность:** Средняя
**Влияние:** Среднее
**Митигация:**
- Кэширование suggestions для похожих запросов
- Fallback на простые шаблоны
- Rate limiting на AI requests

### Риск 4: Недостаток времени (4 недели мало)
**Вероятность:** Высокая
**Влияние:** Критичное
**Митигация:**
- Приоритизация фич (MVP+ scope)
- Убрать nice-to-have (файлы, webhooks)
- Parallel работа (backend + frontend)

### Риск 5: Ozon credentials недоступны для тестирования
**Вероятность:** Средняя
**Влияние:** Высокое
**Митигация:**
- Mock Ozon API для разработки
- Sandbox credentials от Ozon (запросить в поддержке)
- Fallback на WB API (есть доступ)

---

## Post-MVP+ (Phase 2+)

### Phase 2: Multi-marketplace (WB + Яндекс)
- WildberriesConnector
- YandexConnector
- Unified connector interface

### Phase 3: Advanced AI
- Auto-categorization (complaint / question / review)
- Sentiment analysis
- Smart templates based on history

### Phase 4: Webhooks & Realtime
- WebSocket для realtime updates
- Webhook endpoints для Ozon
- Push notifications

### Phase 5: Analytics & Insights
- Response time metrics
- SLA compliance dashboard
- AI performance tracking
