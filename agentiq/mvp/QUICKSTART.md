# AgentIQ MVP — Quick Start (5 минут)

## Быстрый старт для тестирования

### 1. Установка зависимостей (2 мин)

```bash
cd mvp

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установить зависимости
pip install -r requirements.txt
```

### 2. Установить Redis (1 мин)

**macOS:**
```bash
brew install redis
brew services start redis
```

**Linux:**
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

**Проверка:**
```bash
redis-cli ping  # Должно вернуть: PONG
```

### 3. Настройка (1 мин)

```bash
# Скопировать пример конфигурации
cp .env.example .env
```

**Отредактировать `.env`:**

```bash
# Telegram Bot (получить от @BotFather)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_USERNAME=your_bot_username

# SECRET_KEY (сгенерировать)
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Вставить результат в .env:
SECRET_KEY=your_generated_secret_key_here

# Остальное можно оставить как есть для локального теста
```

### 4. Инициализация БД (30 сек)

```bash
python3 init_db.py
```

Должно вывести:
```
Initializing database...
✅ Database initialized successfully!
Tables created: users, tasks, reports, notifications
```

### 5. Запуск (1 мин)

Открыть **3 терминала**:

**Terminal 1 (FastAPI):**
```bash
cd mvp
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2 (Celery):**
```bash
cd mvp
source venv/bin/activate
celery -A backend.tasks.celery_app worker --loglevel=info
```

**Terminal 3 (Redis)** — если не запущен как сервис:
```bash
redis-server
```

### 6. Открыть браузер

[http://localhost:8000](http://localhost:8000)

---

## ⚠️ Важно для Telegram авторизации

Telegram Login Widget работает только с **настоящим доменом**. Для локального теста используй **ngrok**:

### Вариант A: ngrok (рекомендуется для теста)

```bash
# 1. Установить ngrok
brew install ngrok

# 2. Запустить туннель
ngrok http 8000

# 3. Скопировать URL (например: https://abc123.ngrok.io)

# 4. Обновить .env
FRONTEND_URL=https://abc123.ngrok.io

# 5. Настроить домен бота в @BotFather
/setdomain
→ выбрать бота
→ ввести: abc123.ngrok.io (без https://)

# 6. Перезапустить FastAPI (Ctrl+C в Terminal 1, затем снова запустить)
```

Теперь открой `https://abc123.ngrok.io` и авторизуйся!

### Вариант B: Без auth (для быстрого теста)

Если хочешь просто протестировать функционал без Telegram авторизации, можно временно закомментировать `Depends(get_current_user)` в [backend/main.py](backend/main.py:93) для endpoints dashboard и tasks.

---

## Тестирование

### 1. Авторизация
- Открыть главную → кликнуть «Login via Telegram»
- Подтвердить в Telegram
- Должно редиректнуть на `/dashboard`

### 2. Создание задачи
- Ввести демо-артикул: `117220345`
- Кликнуть «Анализировать»
- Увидеть карточку с прогрессом (обновляется каждые 5 сек)

### 3. Получение уведомления
- Через 2-5 минут придёт push в Telegram
- Кликнуть ссылку → открывается отчёт

### 4. Просмотр отчёта
- Видеть красивую карточку с:
  - Рейтингом
  - Сигналами
  - Причинами
  - Рекомендациями
  - Черновиком ответа

---

## Демо-артикулы

Для WBCON API (демо-режим) доступны только эти артикулы:

- **117220345** — фонарик
- **178614734** — товар 2
- **255299570** — товар 3

---

## Troubleshooting

### "Module not found: backend"

```bash
# Убедись что находишься в директории mvp/
cd mvp

# И venv активирован
source venv/bin/activate
```

### "Redis connection failed"

```bash
# Проверь что Redis запущен
redis-cli ping

# Если нет — запусти
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

### "TELEGRAM_BOT_TOKEN not set"

```bash
# Проверь .env файл
cat .env | grep TELEGRAM

# Должно быть:
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_BOT_USERNAME=your_bot_username

# Если нет — отредактируй .env
```

### "Task зависла в processing"

```bash
# 1. Проверь логи Celery (Terminal 2)
# 2. Проверь что артикул валидный (см. демо-артикулы выше)
# 3. Перезапусти Celery worker
```

---

## Следующие шаги

После успешного локального теста:

1. **Деплой на продакшн** → см. [README.md](README.md) раздел "Деплой"
2. **Добавить категории** → см. [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) раздел "Phase 2"
3. **Улучшить UI** → графики, фильтры, экспорт
4. **Монетизация** → тарифы, Stripe integration

---

## Полная документация

- [README.md](README.md) — детальные инструкции по setup
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) — полное описание архитектуры и кода
- [architecture.md](../architecture.md) — vision и roadmap

---

## Контакты

Вопросы? Telegram: @your_username
