# AgentIQ — AI анализ отзывов для WB продавцов

> **Domain:** agentiq.ru
> **MVP Status:** ✅ Working locally
> **Focus:** Поиск скрытых проблем в отзывах + анализ качества ответов продавца

**→ [Что это простыми словами](docs/product/PRODUCT.md)**

---

## 🚀 Быстрый старт (локальный запуск)

```bash
cd apps/reviews

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

Подробнее: [docs/reviews/QUICKSTART.md](docs/reviews/QUICKSTART.md)
Документация: [docs/INDEX.md](docs/INDEX.md)

---

## 📁 Структура проекта

```
agentiq/
├── apps/
│   ├── reviews/                 # ⭐ Анализ отзывов (FastAPI + Celery)
│   └── chat-center/             # ⭐ Chat Center MVP+
├── docs/
│   ├── INDEX.md                 # Навигация по докам
│   ├── architecture/            # Архитектура
│   ├── product/                 # Описание продукта
│   ├── reviews/                 # Документация по анализу отзывов
│   ├── chat-center/             # Документация по чатам
│   ├── research/                # Custdev/рынок/конкуренты
│   ├── ops/                     # Деплой/безопасность/правила
│   └── prototypes/              # Публичные прототипы (GitHub Pages)
├── scripts/                     # Скрипты анализа/интеграций
├── data/                        # Дамп-данные, отчёты, логи
├── assets/                      # Изображения/PDF
├── infra/                       # Docker/Nginx/compose
├── archive/                     # Архив (старые версии)
├── next-actions.md              # Development roadmap
└── README.md                    # Этот файл
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

**Демо:** [data/reports/reviews/communication-loss-282955222.html](data/reports/reviews/communication-loss-282955222.html)

---

## 🔑 Ключевые файлы

### Backend (Python/FastAPI)
- **[apps/reviews/backend/main.py](apps/reviews/backend/main.py)** — API endpoints, auth, routes
- **[apps/reviews/backend/tasks.py](apps/reviews/backend/tasks.py)** — Celery tasks для фоновой обработки
- **[apps/reviews/backend/database.py](apps/reviews/backend/database.py)** — SQLAlchemy models (User, Task, Report)

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
- **[apps/reviews/templates/report.html](apps/reviews/templates/report.html)** — Jinja2 template для карточки отчёта
  - Проблемные варианты + сравнение
  - Причины жалоб с цитатами
  - **Секция "Коммуникация"** (качество ответов, худшие примеры, план действий)

### Документация
- **[docs/product/PRODUCT.md](docs/product/PRODUCT.md)** — Описание продукта простыми словами
- **[docs/reviews/CARD_FORMAT.md](docs/reviews/CARD_FORMAT.md)** — Формат JSON карточки
- **[docs/reviews/QUICKSTART.md](docs/reviews/QUICKSTART.md)** — Подробная инструкция по запуску
- **[docs/architecture/architecture.md](docs/architecture/architecture.md)** — Архитектура системы

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

- **Описание продукта** — [docs/product/PRODUCT.md](docs/product/PRODUCT.md)
- **CustDev интервью** — [docs/research/custdev/](docs/research/custdev/)
- **Демо-отчёты** — [data/reports/](data/reports/)
- **API/рынок исследование** — [docs/research/](docs/research/), [archive/research/](archive/research/)
- **Референс дизайна** — [assets/pdf/otveto-analysis-card-WB-03-02-2026.pdf](assets/pdf/otveto-analysis-card-WB-03-02-2026.pdf)
