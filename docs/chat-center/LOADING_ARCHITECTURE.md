# Chat Center — Архитектура загрузки данных

> Status: MVP (production)
> Last updated: 2026-02-16

## Содержание

1. [Текущий flow загрузки](#текущий-flow-загрузки)
2. [Что видит пользователь](#что-видит-пользователь)
3. [Известные проблемы и риски](#известные-проблемы-и-риски)
4. [Мировая практика (Support Desk)](#мировая-практика-support-desk)
5. [План улучшений](#план-улучшений)

---

## Текущий flow загрузки

### Архитектура: Polling + Pagination + Client Cache

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐
│  localStorage │───▸│  React State │───▸│  UI Sections │
│   (cache)     │    │ interaction  │    │ В работе     │
└──────┬────────┘    │   Cache      │    │ Ожидают      │
       │             └──────▲───────┘    │ Все сообщ.   │
       │ restore            │ merge     └──────────────┘
       │ (sync init)        │
       │             ┌──────┴───────┐
       │             │ fetchInter-  │◂── usePolling(10s)
       │             │ actions()    │
       │             └──────┬───────┘
       │                    │ HTTP
       │             ┌──────▾───────┐
       │             │  Backend API │
       │             │ /interactions│
       │             │ page_size=50 │
       │             └──────────────┘
```

### Этапы загрузки (хронология)

#### 1. Mount + Auth Check (~200ms)

```
t=0ms    React mount → isCheckingAuth=true → полноэкранный спиннер
         ┌── одновременно ──┐
         │ Из localStorage: │
         │ • interactionCache restored (если есть)
         │ • paginationMeta restored
         │ • dismissedSyncOnboarding restored
         └──────────────────┘
t=200ms  authApi.getMe() → user set → isCheckingAuth=false
```

**Что происходит:** useState initializer синхронно читает localStorage cache. Данные есть в state ДО первого рендера, но `isCheckingAuth=true` показывает спиннер вместо UI.

#### 2. First Data Fetch (~200ms или ~2s)

**Если кэш есть (allLoaded=true):**
```
t=200ms  Спиннер пропадает → кэшированные данные показаны мгновенно
t=200ms  usePolling запускает fetchInteractions (page 1, 50 items)
t=400ms  isSame check → если данные не изменились, NO-OP
         → если изменились, merge (1417 items, единственный re-render)
```

**Если кэша нет (первая загрузка / очищен):**
```
t=200ms  Спиннер пропадает → isLoadingChats=true → скелетон/спиннер
t=200ms  fetchInteractions: hasExistingData=false
         → загружает ВСЕ страницы inline (pages 1-29)
t=2200ms Все 1417 items загружены → ОДИН state update → секции заполнены разом
```

#### 3. Polling Loop (каждые 10 сек)

```
t+10s    fetchInteractions: page 1 (50 items) → isSame check
         → true: NO-OP (99% случаев)
         → false: merge + re-render (новое сообщение, смена приоритета)
```

### Структура кэша (localStorage)

```json
{
  "all": {
    "ts": 1739680000000,
    "items": [/* 1417 slim interactions */],
    "allLoaded": true
  }
}
```

- **Key:** `agentiq_interactions_cache`
- **TTL:** 30 минут (`CACHE_TTL_MS`)
- **Slim format:** `slimForCache()` обрезает `extra_data` до полей нужных для `interactionToChat()`:
  - `chat_status`, `sla_due_at`, `product_name`, `user_name`, `customer_name`
  - `last_ai_draft.text/intent/sentiment/sla_priority`
  - `last_reply_text`, `is_auto_response`
- **Размер:** ~1.1MB для 1417 items (лимит localStorage: 5MB)
- **Per-channel split:** производится в памяти при restore, не сохраняется отдельно

### Секции и пагинация

API возвращает interactions отсортированные по `updated_at DESC`. Это значит:
- **Page 1** (50 newest) — почти всегда `responded` / `closed` → идут в "Все сообщения"
- **Pages 10-29** (older items) — содержат `urgent` и `waiting` items → "В работе" и "Ожидают ответа"

| Секция | Количество (prod) | Где в пагинации |
|--------|-------------------|-----------------|
| В работе (urgent) | 7 | Поздние страницы |
| Ожидают ответа | 13 | Поздние страницы |
| Все сообщения | 1397 | Везде |

**Критичный вывод:** при постраничной загрузке (page-by-page) секции "В работе" и "Ожидают ответа" пусты на первых рендерах и заполняются только после загрузки поздних страниц. Это создаёт эффект "постепенного появления" — основная UX-проблема.

**Текущее решение:** inline full-load — при отсутствии кэша загружаем ВСЕ страницы до первого рендера.

---

## Что видит пользователь

### Happy path (кэш есть, данные свежие)

```
[0ms]     Белый экран
[100ms]   Спиннер auth
[200ms]   Полный список чатов с заполненными секциями ← мгновенно из кэша
[10200ms] Фоновый poll — если есть новое сообщение, секции обновляются
```

**Время до контента: ~200ms**

### First load (кэша нет)

```
[0ms]     Белый экран
[100ms]   Спиннер auth
[200ms]   Спиннер загрузки (isLoadingChats)
[2200ms]  Все 1417 items → секции заполнены разом
```

**Время до контента: ~2.2 сек**

### Worst case (кэш протух + медленная сеть)

```
[0ms]     Белый экран
[500ms]   Спиннер auth (медленный getMe)
[1000ms]  Спиннер загрузки
[5000ms]  Все items загружены (29 pages × 150ms каждая)
```

**Время до контента: ~5 сек**

---

## Известные проблемы и риски

### P0: Cache reliability (localStorage)

**Проблема:** localStorage может не работать:
- iOS Private Browsing (quota = 0 в старых версиях)
- Пользователь очистил данные браузера
- Другие данные на домене заняли место

**Текущий mitigation:** inline full-load (все 29 страниц до первого рендера)

**Риск:** при 5000+ interactions inline full-load займёт 10+ сек

### P1: Sorting mismatch — urgent items на поздних страницах

**Проблема:** API сортирует по `updated_at DESC`. Urgent items с давним updated_at оказываются на страницах 10-29. При page-by-page загрузке секция "В работе" пуста первые секунды.

**Варианты решения:**
1. **Backend:** Отдельный endpoint `/interactions/urgent` (TOP-N urgent items, без пагинации)
2. **Backend:** Composite sort: `ORDER BY CASE WHEN sla_priority='urgent' THEN 0 ... END, updated_at DESC`
3. **Backend:** Параллельные запросы: page 1 + urgent items одновременно
4. **Frontend:** Preload urgent items в отдельном запросе при mount

### P2: Polling overhead — 1 HTTP request / 10 сек

**Проблема:** каждые 10 сек делается запрос на 50 items, даже если ничего не изменилось.

**При 100 users:** 10 req/sec = 600 req/min = 36K req/hour

**Варианты решения:**
- Server-Sent Events (SSE) — push уведомлений о новых сообщениях
- WebSockets — bidirectional (но overhead для простого списка)
- Conditional polling: `If-Modified-Since` / ETag / `?since=<timestamp>`
- Adaptive polling: 10s при активности → 60s при idle → 300s при background tab

### P3: Cache staleness — 30 минут TTL

**Проблема:** кэш живёт 30 минут. Если пользователь вернулся через 31 минуту — full reload.

**Риск:** для мобильных пользователей (закрыл вкладку, вернулся через час) кэш всегда протух.

**Варианты:**
- Увеличить TTL до 2-4 часов (данные всё равно обновляются при первом poll)
- Использовать кэш как "instant preview" даже если протух (показать + обновить в фоне)
- IndexedDB вместо localStorage (нет лимита 5MB, не протухает)

### P4: Масштаб — текущая схема НЕ масштабируется

**Проблема:** текущая архитектура "загрузи всё в кэш" линейно зависит от кол-ва interactions. 1417 items у маленького селлера — уже ощутимо. У среднего/крупного — ломается всё.

#### Расчёт по размерам селлеров

| Тип селлера | Interactions | Pages (50/pg) | Full load | Slim cache | localStorage |
|-------------|-------------|---------------|-----------|------------|-------------|
| **Маленький** (1 товар, мало продаж) | 1,400 | 28 | ~2 сек | ~1.1 MB | OK |
| **Средний** (10-50 товаров) | 10,000-30,000 | 200-600 | 15-45 сек | 6-18 MB | **СЛОМАН** (>5MB) |
| **Крупный** (100+ товаров, высокий оборот) | 100,000-500,000 | 2K-10K | 3-15 мин | 60-300 MB | **невозможно** |
| **Топ-селлер** (1000+ SKU) | 1,000,000+ | 20K+ | **часы** | гигабайты | **абсурд** |

#### Что конкретно сломается

**При 10K interactions (средний селлер):**
- Inline full-load: 200 pages × 70ms = **14 сек** → пользователь уходит
- localStorage кэш: 10K × 600B = **6MB > 5MB лимит** → кэш не сохраняется → каждый reload = 14 сек
- React state: 10K объектов в памяти, `.map(interactionToChat)` на каждый render → **UI лаг 200-500ms**
- DOM: 10K `.chat-item` элементов → **скролл тормозит**, layout recalc >100ms

**При 100K interactions (крупный селлер):**
- Full-load невозможен (3+ мин, таймауты, OOM)
- Нужна принципиально другая архитектура: **НЕ грузить всё, а показывать окно**

#### Правильная архитектура для масштаба

**Принцип: inbox — это view, а не dump всей БД.**

Ни один support desk в мире не загружает все тикеты на клиент. Загружается **текущий вид** (view):

```
Текущий подход (не масштабируется):
  Client: "Дай мне ВСЁ" → Server: 1417 items → Client группирует в секции

Правильный подход (масштабируется на миллионы):
  Client: "Дай мне urgent top 20, waiting top 20, recent top 50"
  Server: 90 items → Client показывает
  Client: [скролл вниз] → "Дай мне page 2 из Все сообщения"
  Server: 50 items → Client дозагружает
```

**Конкретная реализация — `GET /interactions/inbox`:**

```json
// Один запрос вместо 29 страниц
GET /api/interactions/inbox

Response:
{
  "sections": {
    "urgent": {
      "total": 7,
      "items": [/* top 20 urgent, sorted by sla_deadline */]
    },
    "waiting": {
      "total": 13,
      "items": [/* top 20 waiting, sorted by occurred_at */]
    },
    "all": {
      "total": 1397,
      "items": [/* top 50 recent, sorted by updated_at DESC */]
    }
  },
  "sync_ts": "2026-02-16T06:09:21Z"
}
```

**Почему это масштабируется:**
- 1 запрос вместо 29 (или 200, или 10K)
- Backend делает `SELECT ... WHERE ... ORDER BY ... LIMIT 20` — быстро на любом объёме с индексами
- Клиент получает ~90 items вместо 1417 (или 100K) → кэш <100KB
- Дозагрузка при скролле (lazy load per section)
- При 100K interactions запрос занимает столько же времени, сколько при 1K

**SQL backend (примерный):**
```sql
-- urgent: top 20 by deadline
SELECT * FROM interactions
WHERE seller_id = 3 AND status != 'closed'
  AND (extra_data->>'sla_priority' IN ('urgent','critical')
       OR priority IN ('urgent','critical'))
ORDER BY sla_due_at ASC NULLS LAST
LIMIT 20;

-- waiting: top 20 by age
SELECT * FROM interactions
WHERE seller_id = 3 AND status != 'closed'
  AND needs_response = true
  AND priority NOT IN ('urgent','critical')
ORDER BY occurred_at ASC
LIMIT 20;

-- recent: top 50
SELECT * FROM interactions
WHERE seller_id = 3
ORDER BY updated_at DESC
LIMIT 50;
```

#### Переход: когда какой подход

| Объём | Подход | Время до контента |
|-------|--------|-------------------|
| <2K items | Текущий (full-load + cache) | ~2 сек |
| 2K-10K | `/inbox` endpoint (3 SQL запроса) | <500ms |
| 10K-100K | `/inbox` + delta sync + virtual scroll | <300ms |
| 100K+ | `/inbox` + SSE push + CQRS read model | <200ms |

---

## Мировая практика (Support Desk)

### Как устроена загрузка в Support Desk системах

| Продукт | Архитектура | Первая загрузка | Real-time |
|---------|-------------|-----------------|-----------|
| **Zendesk** | REST + WebSocket | Первые 100 тикетов, lazy scroll | WebSocket push для новых тикетов |
| **Intercom** | GraphQL + WebSocket | Inbox summary (counts) → lazy items | WebSocket для messages + presence |
| **Freshdesk** | REST + Polling | Paginated list, 30 items/page | Long polling (30s), переход на WS |
| **Help Scout** | REST + SSE | Mailbox view, 50 items | Server-Sent Events для обновлений |
| **Front** | REST + WebSocket | Inbox с виртуальным скроллом | WS для real-time sync |
| **HubSpot** | GraphQL + SSE | Dashboard summary → drill-down | SSE для ticket updates |
| **Crisp** | WebSocket-first | Полный список через WS | WS bidirectional |

### Ключевые паттерны

#### 1. "Show counts, load details" (Intercom, HubSpot)

Первым делом загружается **summary**: количество в каждой секции + последние 3-5 items в каждой. Полный список подгружается при скролле.

```
Inbox Summary (1 request, <100ms):
  В работе: 7 items    [показать первые 3]
  Ожидают:  13 items   [показать первые 3]
  Все:      1397 items [показать первые 10]
```

**Для AgentIQ:** создать endpoint `GET /interactions/summary` → counts + top items per section.

#### 2. "Optimistic UI + background sync" (Zendesk, Front)

UI показывает кэш мгновенно ("optimistic"), в фоне синхронизирует. Если данные изменились — плавно обновляет (animation, не replace).

```
t=0     Показать кэш (stale but fast)
t=200ms Получить delta (только изменения с last_sync)
t=300ms Обновить изменившиеся items (анимация ↔ секций)
```

**Для AgentIQ:** delta sync endpoint `GET /interactions?updated_since=<ts>`.

#### 3. "Priority-first fetch" (Freshdesk, Help Scout)

Сначала грузятся urgent/unresolved items (они важнее для оператора), потом остальные.

```
Request 1: GET /interactions?priority=urgent,high  → 20 items, 50ms
Request 2: GET /interactions?status=waiting         → 13 items, 30ms
Request 3: GET /interactions?page=1                 → остальные
```

**Для AgentIQ:** 2 параллельных запроса при mount: urgent items + page 1.

#### 4. "Server-Sent Events / WebSocket" (Intercom, Crisp, Front)

Polling заменяется на push. Сервер уведомляет клиент о новых сообщениях, смене статуса, новом тикете.

```
SSE stream: /api/interactions/stream
  data: {"type":"new_message","interaction_id":42,"preview":"Добрый день..."}
  data: {"type":"status_change","interaction_id":15,"new_status":"urgent"}
```

**Для AgentIQ (уровень 2):** SSE проще WebSocket, не требует отдельной инфраструктуры. FastAPI поддерживает SSE нативно через `StreamingResponse`.

#### 5. Virtual scrolling (Front, Zendesk)

Список из 10K+ тикетов рендерится через виртуальный скролл — в DOM всего 20-30 элементов, остальные подгружаются при скролле.

**Для AgentIQ (уровень 3):** `react-window` или `@tanstack/virtual`. Актуально при 5000+ interactions.

---

## План улучшений

### Уровень 0: Текущее состояние (MVP)

- [x] Inline full-load: все pages загружаются до первого рендера
- [x] localStorage cache с slim format
- [x] `isSame` check для минимизации re-renders
- [x] 10-секундный polling
- **Подходит для:** 1 seller, ~1500 interactions

### Уровень 1: Priority-first + Delta sync (Post-MVP)

- [ ] `GET /interactions/summary` — counts + top 5 per section (один запрос <100ms)
- [ ] `GET /interactions?priority=urgent,high` — urgent items первыми
- [ ] `GET /interactions?updated_since=<ts>` — delta sync (только изменения)
- [ ] Stale-while-revalidate кэш (показывать даже протухший + обновлять в фоне)
- [ ] Адаптивный polling: 10s active → 30s idle → 120s background
- **Подходит для:** 1-10 sellers, ~5000 interactions

### Уровень 2: SSE + Server-side sections (Scale)

- [ ] Server-Sent Events для real-time push (новые сообщения, смена статуса)
- [ ] Server-side section grouping (backend возвращает items с section assignment)
- [ ] IndexedDB для кэша (снять ограничение 5MB localStorage)
- [ ] Optimistic UI: кэш мгновенно, delta в фоне, плавная анимация изменений
- **Подходит для:** 10-100 sellers, ~50K interactions

### Уровень 3: Virtual scroll + CQRS (Enterprise)

- [ ] Virtual scrolling (react-window) для списков 10K+
- [ ] CQRS: отдельная read-модель для inbox (materialized views)
- [ ] WebSocket для bidirectional real-time
- [ ] Background sync workers (Kafka/RabbitMQ)
- **Подходит для:** 100+ sellers, 500K+ interactions

---

## Файлы

| Файл | Что делает |
|------|-----------|
| `frontend/src/App.tsx:633-737` | `fetchInteractions()` — основная логика загрузки |
| `frontend/src/App.tsx:247-300` | `slimForCache()` + `saveInteractionsToCache()` |
| `frontend/src/App.tsx:380-392` | useState initializer — cache restore |
| `frontend/src/App.tsx:739-808` | `fetchAllRemainingPages()` — batch background pagination |
| `frontend/src/hooks/usePolling.ts` | Polling hook (10s interval) |
| `backend/app/routers/interactions.py` | API endpoint `/interactions` |
| `backend/app/tasks/sync.py` | Celery sync tasks (30s cycle) |
