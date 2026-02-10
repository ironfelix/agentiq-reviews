# AgentIQ — Project Summary

> AI-платформа анализа отзывов и качества ответов продавцов на Wildberries.

## Quickstart (локально)

```bash
cd apps/reviews
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить токены
python init_db.py       # создать БД

# Terminal 1 — Redis
redis-server

# Terminal 2 — Celery worker
source venv/bin/activate
celery -A backend.tasks.celery_app worker --loglevel=info

# Terminal 3 — FastAPI
source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Открыть http://localhost:8000
```

Для публичного URL (Telegram auth): `apps/reviews/start-with-tunnel.sh`

---

## Архитектура

```
Browser → (Nginx SSL) → FastAPI :8000 → SQLite (agentiq.db)
                             ↓
                       Celery task → Redis :6379 → Worker
                                                     ↓
                                           WBCON API (19-fb.wbcon.su)
                                           WB CDN (карточка, цены)
                                           DeepSeek LLM
                                                     ↓
                                           wbcon-task-to-card-v2.py → JSON
                                                     ↓
                                           Jinja2 → HTML (2 шаблона)
                                           Playwright → PDF
```

## Два отчёта

| Тип | URL | Шаблон | Что показывает |
|-----|-----|--------|----------------|
| **Анализ товара** | `/dashboard/report/{id}` | `report.html` | Сигналы, причины негатива, варианты, тренды |
| **Анализ коммуникации** | `/dashboard/report/{id}/communication` | `comm-report.html` | Качество ответов, потери ₽, рекомендации |

---

## Структура файлов

### Backend (`apps/reviews/backend/`)

| Файл | Что делает |
|------|-----------|
| `main.py` | FastAPI app. Роуты, auth middleware, Jinja2 рендеринг, API endpoints |
| `tasks.py` | Celery worker. WBCON API v2 (create task → poll → fetch), запуск скрипта анализа |
| `database.py` | SQLAlchemy модели: User, Task, Report, Notification, InviteCode |
| `auth.py` | Telegram auth (HMAC verify) + JWT сессии (HS256, 30 дней, auto-refresh) |
| `pdf_export.py` | Playwright HTML→PDF (раскрывает `<details>`, сохраняет тёмную тему) |
| `telegram_bot.py` | Отправка уведомлений в Telegram |

### Скрипты (`scripts/`)

| Файл | Что делает |
|------|-----------|
| `wbcon-task-to-card-v2.py` | Главный скрипт анализа (~1100 строк). Классификация, варианты, тренды, money_loss, communication |
| `llm_analyzer.py` | DeepSeek LLM интеграция. Classify, actions, reply, communication analysis, guardrails |
| `wbcon-reviews-fetch.sh` | Bash-скрипт загрузки отзывов через WBCON v2 API |
| `wbcon-questions-fetch.sh` | Загрузка вопросов (старый API qs.wbcon.su) |
| `wbcon-images-fetch.sh` | Загрузка изображений (старый API) |

### Шаблоны (`apps/reviews/templates/`)

| Файл | Что рендерит |
|------|-------------|
| `index.html` | Лендинг с Telegram Login Widget |
| `invite.html` | Страница ввода инвайт-кода (первый вход) |
| `dashboard.html` | Dashboard: ввод артикула, список задач, progress, 2 кнопки отчётов |
| `report.html` | Отчёт анализа товара (сигналы, причины, варианты) |
| `comm-report.html` | Отчёт коммуникации (оценка /10, потери, скорость, ТОП ошибок) |

### Инфраструктура

| Файл | Что делает |
|------|-----------|
| `infra/docker-compose.yml` | Redis + Web (FastAPI) + Worker (Celery) |
| `apps/reviews/Dockerfile` | Python 3.11 + Playwright Chromium |
| `apps/reviews/Dockerfile.worker` | Celery worker контейнер |
| `apps/reviews/start.sh` | Локальный запуск (venv + FastAPI + Celery + Redis) |
| `apps/reviews/start-with-tunnel.sh` | + SSH tunnel для публичного URL |
| `apps/reviews/stop.sh` | Остановка всех процессов |

---

## Внешние API

### WBCON v2 (отзывы)
- **Base:** `https://19-fb.wbcon.su`
- **Auth:** header `token: <JWT>` (expires 2026-03-10)
- **Flow:** `POST /create_task_fb` → `GET /task_status` → `GET /get_results_fb`
- **Pagination:** `offset=0,100,200...`, dedup по `fb_id` (есть баг с дубликатами)
- **Docs:** `https://19-fb.wbcon.su/docs`

### WB CDN (карточка товара, цены)
- **Card:** `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json`
- **Prices:** `…/price-history.json` (kopecks ÷ 100 = rubles)
- **Basket N** from `nmId // 100000` via range table (see `_wb_basket_num()`)

### DeepSeek LLM
- **Model:** `deepseek-chat` via OpenAI SDK
- **Uses:** classification, communication analysis, recommendations
- **Guardrails:** banned phrases + post-processing (see `docs/reviews/RESPONSE_GUARDRAILS.md`)

---

## ENV переменные

```bash
SECRET_KEY=...              # FastAPI secret
DATABASE_URL=sqlite+aiosqlite:///./agentiq.db
REDIS_URL=redis://localhost:6379/0
TELEGRAM_BOT_TOKEN=...      # @BotFather
TELEGRAM_BOT_USERNAME=...
WBCON_TOKEN=...             # JWT, expires 2026-03-10
DEEPSEEK_API_KEY=...        # platform.deepseek.com
USE_LLM=1                  # 0 = skip LLM calls
FRONTEND_URL=...            # for Telegram callback redirect
```

---

## User Flow

1. **Вход:** Landing → Telegram Login → (первый раз) инвайт-код → Dashboard
2. **Анализ:** Ввод артикула → Celery task → WBCON → Script → LLM → Save to DB
3. **Просмотр:** Dashboard → "Анализ товара" / "Анализ коммуникации"
4. **Шеринг:** "Поделиться" → публичная ссылка без авторизации
5. **PDF:** Кнопка "PDF" → Playwright → скачивание

---

## Документация (docs/)

| Файл | Содержание |
|------|-----------|
| `docs/reviews/RESPONSE_GUARDRAILS.md` | **Важно!** Правила генерации ответов: banned phrases, формат "от лица продавца" |
| `docs/reviews/WBCON_API_V2.md` | API reference WBCON v2 (token auth, endpoints, pagination) |
| `docs/reviews/COMMUNICATION_LOSS_CALCULATION.md` | Методика расчёта потерь от плохих ответов |
| `docs/architecture/architecture-mvp2.md` | Архитектура MVP2: компоненты, flow, деплой |
| `docs/ops/DEPLOYMENT.md` | VPS deploy guide: Docker + Nginx + SSL |
| `docs/reviews/API.md` | HTTP API endpoints |
| `docs/reviews/reasoning-rules.md` | Правила reasoning: окна, пороги, классификация |
| `docs/reviews/review-card-logic.md` | Логика генерации JSON карточки товара |

### Архив
`archive/` — старые версии скриптов, демо-карточки, исследования (не используются).

---

## DB Schema

```
users        — Telegram пользователи (telegram_id, username, invite_code_id)
tasks        — Задачи анализа (article_id, wbcon_task_id:String, status, progress)
reports      — Результаты (article_id, data:JSON, share_token, rating, feedback_count)
notifications— История TG-уведомлений
invite_codes — Инвайт-коды бета-доступа (code, max_uses, used_count)
```
