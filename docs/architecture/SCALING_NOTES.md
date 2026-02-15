# Scaling Notes: AI Analysis in Sync Pipeline

> Status: MVP — inline analysis, single worker, DeepSeek API
> Last updated: 2026-02-15

## Текущая архитектура (MVP)

Inline LLM-вызов внутри sync: до 10 чатов × 3 сек = 30 сек макс.
Подходит для 1 seller, ~200 чатов, ~5 новых/цикл.

## Как масштабировать при росте нагрузки

### Уровень 1: 10-50 sellers (сотни чатов/мин)

**Проблема:** Inline analysis блокирует sync worker. При 50 sellers × 5 чатов = 250 LLM calls/мин.

**Решение: Dedicated AI worker pool**
- Выделить отдельную Celery queue `ai_analysis` с 4-8 workers
- Sync остаётся быстрым, анализ не блокирует fetch
- Priority queue: urgent чаты анализируются первыми
- Мировая практика: Shopify, Zendesk — отдельные worker pools для AI/ML tasks

### Уровень 2: 50-500 sellers (тысячи чатов/мин)

**Проблема:** DeepSeek API rate limits, latency spikes, cost.

**Решение: Tiered analysis + batch processing**
- **Tier 1 (instant, <100ms):** Keyword-based classifier (regex/fasttext)
  — определяет intent + priority без LLM
  — хватает для routing в правильную секцию
- **Tier 2 (fast, 1-3s):** Мелкая модель (Haiku/Gemini Flash) для draft
  — генерирует рекомендацию
- **Tier 3 (quality, 5-10s):** Полная модель (DeepSeek/Sonnet) для сложных кейсов
  — только urgent + negative sentiment
- Мировая практика: Intercom, Freshdesk — cascading AI tiers

**Batch LLM calls:**
- Собирать 10-20 сообщений → один LLM-вызов с batch prompt
- Снижает latency per item в 5-10x
- OpenAI Batch API, Anthropic Message Batches

### Уровень 3: 500+ sellers (enterprise scale)

**Проблема:** Синхронный polling не масштабируется.

**Решение: Event-driven architecture**
- **Webhooks** вместо polling (WB Chat API поддерживает)
  — webhook → message queue (Kafka/RabbitMQ) → consumer → AI → DB
- **CQRS:** Отдельные write (sync) и read (API) модели
  — Sync пишет в write DB
  — Projector строит read-оптимизированные views
- **Stream processing:** Apache Kafka / AWS Kinesis
  — Real-time pipeline: ingest → enrich (AI) → route → notify
- Мировая практика:
  - Slack: Event-driven + Kafka для message processing
  - Discord: Event sourcing + CQRS для чат-инфраструктуры
  - Twilio: Webhook-first, worker queues для AI enrichment

### Database scaling
- **Текущее:** PostgreSQL, single instance
- **Уровень 1:** Read replicas для API reads, primary для writes
- **Уровень 2:** Partitioning по seller_id, TimescaleDB для time-series analytics
- **Уровень 3:** Sharding по seller_id, отдельный analytics DB (ClickHouse)

### Кэширование
- **Текущее:** sessionStorage на клиенте
- **Уровень 1:** Redis для server-side cache (AI drafts, chat lists)
- **Уровень 2:** CDN для статики, Redis Cluster для sessions
- **Уровень 3:** Multi-layer: CDN → Redis → DB, cache invalidation через pub/sub

### Мониторинг AI quality
- **A/B testing:** Сравнивать модели по quality score (% harmful ответов)
- **Latency tracking:** p50/p95/p99 LLM response time
- **Cost tracking:** $/1000 analyses, alert если cost spike
- **Fallback rate:** % чатов где LLM timeout → fallback

## Мировые практики (reference)

| Компания | Подход | Масштаб |
|----------|--------|---------|
| Intercom | Cascading AI tiers (rule → fast model → full model) | 25K+ companies |
| Zendesk | Dedicated ML workers + batch inference | 100K+ companies |
| Freshdesk | Freddy AI — async enrichment + instant keyword routing | 60K+ companies |
| Shopify | Sidekiq workers + separate AI service | 2M+ merchants |
| Slack | Kafka event stream + ML enrichment pipeline | 750K+ orgs |
| HubSpot | Event-driven + queue-based AI processing | 200K+ companies |

## Ключевые принципы

1. **Separate concerns:** Sync (fetch) и Analysis (AI) — разные сервисы/workers
2. **Degrade gracefully:** AI сломался → данные всё равно показываются
3. **Prioritize by value:** Urgent первыми, positive последними
4. **Cache aggressively:** AI draft не меняется пока нет нового сообщения
5. **Measure everything:** Latency, cost, quality, fallback rate
