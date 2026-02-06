# AgentIQ — AI анализ отзывов для WB продавцов

> **Domain:** agentiq.ru
> **MVP Status:** ✅ Working locally
> **Focus:** Поиск скрытых проблем в отзывах + анализ качества ответов продавца

**→ [Что это простыми словами](PRODUCT.md)**

---

## 🚀 Быстрый старт (локальный запуск)

```bash
cd mvp

# 1. Установка зависимостей
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Установка Redis
brew install redis
brew services start redis

# 3. Настройка .env
cp .env.example .env
# Отредактируй .env: SECRET_KEY, WBCON_EMAIL, WBCON_PASS, DEEPSEEK_API_KEY

# 4. Инициализация БД
python3 init_db.py

# 5. Запуск (2 терминала)
# Terminal 1: FastAPI + Celery Worker
./start.sh

# Terminal 2: (опционально) ngrok для Telegram auth
ngrok http 8000
```

Открой: http://localhost:8000

Подробнее: [mvp/QUICKSTART.md](mvp/QUICKSTART.md)

---

## 📁 Структура проекта

```
agentiq/
├── PRODUCT.md                    # ⭐ Описание продукта (2-3 абзаца)
├── README.md                     # Этот файл
│
├── mvp/                          # ⭐ Рабочий MVP (FastAPI + Celery)
│   ├── backend/                  # Python backend
│   │   ├── main.py              # API endpoints + auth
│   │   ├── tasks.py             # Celery worker tasks
│   │   ├── database.py          # SQLAlchemy models
│   │   └── telegram_bot.py      # Telegram notifications
│   ├── templates/                # Jinja2 HTML templates
│   │   ├── index.html           # Landing
│   │   ├── dashboard.html       # Дашборд с задачами
│   │   ├── report.html          # ⭐ Карточка отчёта
│   │   └── communication-loss-282955222.html  # Mockup анализа ответов
│   ├── static/                   # CSS/JS/images
│   ├── requirements.txt          # Python dependencies
│   ├── .env.example             # Config template
│   ├── start.sh                 # Startup script (backend + worker)
│   └── README.md                # MVP documentation
│
├── scripts/                      # ⭐ Скрипты анализа
│   ├── wbcon-task-to-card-v2.py # Главный скрипт анализа отзывов
│   ├── llm_analyzer.py          # DeepSeek LLM integration
│   ├── wbcon-reviews-fetch.sh   # Bash скрипт для WBCON API
│   ├── wbcon-questions-fetch.sh # Fetch customer questions
│   └── wbcon-images-fetch.sh    # Fetch product images
│
├── docs/                         # Документация
│   ├── CARD_FORMAT.md           # Формат JSON карточки
│   ├── RULES.md                 # Правила анализа
│   ├── architecture.md          # Архитектура системы
│   ├── reasoning-rules.md       # Логика reasoning
│   └── review-card-logic.md     # Алгоритм карточки
│
├── archive/                      # Архив (старые версии)
│   ├── demos/                   # HTML/JSON demo cards
│   ├── root-demos/              # Старые demo файлы из корня
│   ├── research/                # API research, landing drafts
│   ├── custdev/                 # CustDev interviews
│   ├── old-scripts/             # Deprecated scripts
│   └── test-data/               # Test JSON files
│
├── card-data.json               # Sample analysis output
├── openapi.json                 # API schema
├── otveto-analysis-card-WB-03-02-2026.pdf  # Design reference
└── next-actions.md              # Development roadmap
```

---

## 🎯 Что делает система

### 1. Анализ проблемных вариантов товара
- Определяет какой цвет/размер/режим проседает по рейтингу
- Извлекает причины жалоб (тусклый, батарея, размер не тот)
- Сравнивает варианты (красный: 4.0★ vs белый: 4.8★)

### 2. Анализ качества ответов продавца ⭐ NEW
- Классифицирует ответы: хорошие, нормальные, вредящие
- Находит токсичные паттерны (обвиняет покупателя, игнорирует жалобу)
- Генерирует рекомендации «как стоило ответить»
- Оценивает влияние на конверсию (~2-5% потери из-за плохих ответов)

### 3. Готовый план действий
- Конкретные шаги с приоритетами (критично / важно)
- Черновики ответов для копирования
- Рекомендации по обновлению карточки товара

**Демо:** [mvp/templates/communication-loss-282955222.html](mvp/templates/communication-loss-282955222.html)

---

## 🔑 Ключевые файлы

### Backend (Python/FastAPI)
- **[mvp/backend/main.py](mvp/backend/main.py)** — API endpoints, auth, routes
- **[mvp/backend/tasks.py](mvp/backend/tasks.py)** — Celery tasks для фоновой обработки
- **[mvp/backend/database.py](mvp/backend/database.py)** — SQLAlchemy models (User, Task, Report)

### Анализ отзывов
- **[scripts/wbcon-task-to-card-v2.py](scripts/wbcon-task-to-card-v2.py)** — Главный скрипт анализа
  - Определение категории товара
  - Поиск проблемных вариантов
  - Подсчёт причин жалоб
  - **Анализ качества ответов** (LLM-powered)
  - Генерация рекомендаций
- **[scripts/llm_analyzer.py](scripts/llm_analyzer.py)** — DeepSeek LLM integration
  - Классификация причин негатива
  - Deep analysis (root cause + strategy)
  - **Communication quality analysis** ⭐
  - Guardrails для ответов продавца

### HTML Template
- **[mvp/templates/report.html](mvp/templates/report.html)** — Jinja2 template для карточки отчёта
  - Проблемные варианты + сравнение
  - Причины жалоб с цитатами
  - **Секция "Коммуникация"** (качество ответов, худшие примеры, план действий)

### Документация
- **[PRODUCT.md](PRODUCT.md)** — Описание продукта простыми словами
- **[docs/CARD_FORMAT.md](docs/CARD_FORMAT.md)** — Формат JSON карточки
- **[mvp/QUICKSTART.md](mvp/QUICKSTART.md)** — Подробная инструкция по запуску
- **[docs/architecture.md](docs/architecture.md)** — Архитектура системы

---

## 🛠 Технологии

**Backend:**
- FastAPI — web framework
- SQLAlchemy + aiosqlite — database (SQLite)
- Celery + Redis — background tasks
- Jinja2 — HTML templates
- python-telegram-bot — Telegram notifications

**LLM Integration:**
- DeepSeek API (OpenAI-compatible) — ~$0.01/100 reviews
- Prompts with guardrails (no false promises, no AI mentions)

**Frontend:**
- Vanilla JS + CSS
- Montserrat font (Google Fonts)
- Dark theme (#0a1018 background)

**Integrations:**
- WBCON API — парсинг отзывов WB
- WB Public Card API — описание товара
- Telegram Login Widget — авторизация

---

## 📊 Текущий статус

### ✅ Готово
- Backend API (FastAPI) с auth bypass для локального теста
- Celery worker для фоновой обработки
- Интеграция с WBCON API (создание задач, polling, pagination)
- Скрипт анализа отзывов (rule-based + LLM)
- **LLM-анализ качества ответов продавца** ⭐
- База данных (SQLite) с моделями User, Task, Report
- Dashboard с таблицей задач и статусами
- HTML template `report.html` с секцией Communication

### 🚧 В процессе
- ❌ Telegram авторизация (сейчас bypass для локального теста)
- ❌ Deploy на продакшн (нужен ngrok/cloudflare для webhook)

### 📝 TODO
- [ ] Добавить обработку ошибок и retry для WBCON API
- [ ] Настроить Telegram Bot для авторизации
- [ ] Deploy на VPS (ngrok/cloudflared для webhook)
- [ ] Логирование и мониторинг (Sentry?)
- [ ] Метрики и A/B тесты

---

## 🐛 Известные проблемы

1. **WBCON pagination broken** — offset returns duplicates, only 100 of 407 fetched
2. **Telegram notifications** — async/await in sync context, fixed via `asyncio.run()`
3. **Auth bypass** — для локального теста создаётся фейковый user (telegram_id=999999999)
4. **python-dotenv not in system python** — pass env vars via CLI: `DEEPSEEK_API_KEY=... USE_LLM=1 python3 ...`

---

## 📞 Контакты

Вопросы и предложения: [GitHub Issues](https://github.com/ironfelix/agentiq-reviews/issues)

---

## 📚 Дополнительные материалы

- **Описание продукта** — [PRODUCT.md](PRODUCT.md)
- **CustDev интервью** — [archive/custdev/](archive/custdev/)
- **Демо-карточки** — [archive/demos/](archive/demos/), [archive/root-demos/](archive/root-demos/)
- **API исследование** — [archive/research/](archive/research/)
- **Референс дизайна** — [otveto-analysis-card-WB-03-02-2026.pdf](otveto-analysis-card-WB-03-02-2026.pdf)
