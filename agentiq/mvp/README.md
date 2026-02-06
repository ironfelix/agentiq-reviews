# AgentIQ MVP - Setup Guide

Минимальная рабочая версия платформы для анализа отзывов WB с Telegram авторизацией.

---

## 🚀 Быстрый запуск (с публичным URL)

```bash
# Запустить всё одной командой:
./start-with-tunnel.sh
```

Этот скрипт:
- ✅ Запускает FastAPI + Celery
- ✅ Создаёт публичный HTTPS URL через localhost.run
- ✅ Готов для тестирования Telegram авторизации

📖 **Подробная инструкция:** [QUICKSTART_TUNNEL.md](QUICKSTART_TUNNEL.md)
📋 **Для остановки:** `./stop.sh`

---

## Архитектура

```
FastAPI (backend) + SQLite (DB) + Celery (фоновые задачи) + Telegram (auth + notifications)
```

**Компоненты:**
- **FastAPI**: веб-сервер, API, раздача HTML
- **SQLite**: хранение пользователей, задач, отчётов
- **Celery + Redis**: очередь для фоновых задач (анализ отзывов)
- **Telegram Bot**: авторизация (Login Widget) + пуши

---

## Требования

- **Python 3.9+**
- **Redis** (для Celery)
- **Telegram Bot** (токен от @BotFather)

---

## Установка

### 1. Установить зависимости

```bash
cd mvp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Установить Redis

**macOS:**
```bash
brew install redis
brew services start redis
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Проверка:**
```bash
redis-cli ping
# Должно вернуть: PONG
```

### 3. Создать Telegram бота

1. Открыть [@BotFather](https://t.me/BotFather) в Telegram
2. Отправить `/newbot`
3. Указать имя: `AgentIQ Bot`
4. Указать username: `agentiq_yourname_bot` (должен быть уникальный)
5. Получить токен (вида `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. Отправить `/setdomain` → выбрать бота → указать домен: `agentiq.ru` (или `localhost:8000` для теста)

**Важно:** Для Telegram Login Widget нужен домен. Для локальных тестов используй [ngrok](https://ngrok.com/) или [localhost.run](https://localhost.run/).

---

## Настройка

### 1. Создать `.env` файл

```bash
cp .env.example .env
```

### 2. Заполнить `.env`

```bash
# FastAPI
SECRET_KEY=your-secret-random-key-here-generate-it
ENVIRONMENT=development

# Database
DATABASE_URL=sqlite+aiosqlite:///./agentiq.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_USERNAME=agentiq_yourname_bot

# WBCON API (уже заполнено)
WBCON_EMAIL=vanili7@gmail.com
WBCON_PASS=5ltDb74W
WBCON_FB_BASE=https://01-fb.wbcon.su

# Frontend URL (важно для Telegram Login Widget!)
FRONTEND_URL=http://localhost:8000  # или https://your-ngrok-url.ngrok.io
```

**Генерация SECRET_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Запуск

Нужно запустить **3 процесса** в разных терминалах:

### Terminal 1: FastAPI сервер

```bash
cd mvp
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

Откроется на [http://localhost:8000](http://localhost:8000)

### Terminal 2: Celery Worker

```bash
cd mvp
source venv/bin/activate
celery -A backend.tasks.celery_app worker --loglevel=info
```

### Terminal 3: Redis (если не запущен как сервис)

```bash
redis-server
```

---

## Использование

### 1. Открыть сайт

[http://localhost:8000](http://localhost:8000)

### 2. Войти через Telegram

Кликнуть на кнопку «Telegram Login Widget» → Telegram откроет диалог → подтвердить

### 3. Создать анализ

В dashboard:
1. Ввести артикул WB (например: `117220345`)
2. Кликнуть «Анализировать»
3. Задача создана → получишь пуш в Telegram (~2-5 мин)

### 4. Посмотреть отчёт

Кликнуть на карточку задачи → откроется полный отчёт с:
- Рейтингами
- Причинами негатива
- Трендами
- Рекомендациями
- Черновиком ответа

---

## Тестирование с ngrok (для Telegram Login Widget)

Если хочешь протестировать Telegram авторизацию локально, используй ngrok:

### 1. Установить ngrok

```bash
brew install ngrok  # macOS
# или скачать с https://ngrok.com/download
```

### 2. Запустить туннель

```bash
ngrok http 8000
```

Получишь URL вида: `https://abc123.ngrok.io`

### 3. Обновить `.env`

```bash
FRONTEND_URL=https://abc123.ngrok.io
```

### 4. Обновить домен бота

Отправить в @BotFather:
```
/setdomain
→ выбрать бота
→ ввести: abc123.ngrok.io
```

### 5. Перезапустить FastAPI

```bash
# Ctrl+C в Terminal 1, затем
uvicorn backend.main:app --reload --port 8000
```

Теперь открой `https://abc123.ngrok.io` и авторизуйся через Telegram!

---

## Структура проекта

```
mvp/
├── backend/
│   ├── main.py              # FastAPI app (endpoints, routes)
│   ├── database.py          # SQLAlchemy models (User, Task, Report)
│   ├── auth.py              # Telegram auth verification
│   ├── tasks.py             # Celery workers (фоновые задачи)
│   └── telegram_bot.py      # Telegram notifications
├── templates/
│   ├── index.html           # Landing + Telegram Login Widget
│   ├── dashboard.html       # Dashboard (список задач)
│   └── report.html          # Детальный отчёт
├── static/
│   └── report-card.css      # Стили для отчёта
├── requirements.txt         # Python dependencies
├── .env.example             # Пример конфигурации
└── README.md                # Эта инструкция
```

---

## Демо-артикулы для тестов

Эти артикулы доступны в DEMO-режиме WBCON API:

- **117220345** — фонарик (есть проблемы по вариантам)
- **178614734** — товар 2
- **255299570** — товар 3

---

## FAQ

### Q: Telegram Login Widget не работает

**A:** Проверь:
1. Домен в @BotFather совпадает с `FRONTEND_URL` в `.env`
2. Для локального теста используй ngrok
3. Перезапусти FastAPI после изменения `.env`

### Q: Celery worker не обрабатывает задачи

**A:** Проверь:
1. Redis запущен: `redis-cli ping`
2. Celery worker запущен в отдельном терминале
3. В логах Celery есть строка `[tasks] ready`

### Q: Ошибка "WBCON API failed"

**A:** Проверь:
1. Артикул входит в список демо-артикулов (см. выше)
2. `WBCON_EMAIL` и `WBCON_PASS` в `.env` корректны
3. `WBCON_FB_BASE` правильный (с протоколом `https://`)

### Q: Задача зависла в "processing"

**A:**
1. Проверь логи Celery worker (Terminal 2)
2. WBCON API может быть медленным (до 5 минут для больших товаров)
3. Если зависло — перезапусти Celery worker

---

## Что дальше?

После успешного запуска MVP:

1. **Деплой на продакшн** (Vercel + Railway / Render)
2. **Добавить категории** (одежда, электроника, pet food)
3. **Улучшить UI** (анимации, графики, фильтры)
4. **Webhook вместо polling** (WBCON API callback)
5. **Multi-tenant** (поддержка нескольких пользователей)

---

## Контакты

Вопросы? Пиши в Telegram: @your_username
