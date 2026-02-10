# AgentIQ MVP — Быстрый запуск через localhost.run

> **Цель:** Получить публичный URL для тестирования Telegram авторизации без полноценного deploy

---

## Что такое localhost.run?

**localhost.run** — это бесплатный SSH туннель, который создаёт публичный HTTPS URL для вашего локального сервера.

**Преимущества:**
- ✅ Бесплатно
- ✅ Не требует регистрации
- ✅ HTTPS из коробки
- ✅ Работает через SSH (без установки дополнительного софта)
- ✅ Идеально для MVP тестирования

**Недостатки:**
- ❌ URL меняется при каждом перезапуске
- ❌ Не для production (только для тестов)
- ❌ Может быть нестабильным

---

## Быстрый старт

### Шаг 1: Запустить локальный сервер

```bash
cd /Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/apps/reviews

# Активировать виртуальное окружение
source venv/bin/activate

# Запустить Redis
brew services start redis

# Запустить FastAPI (Terminal 1)
uvicorn backend.main:app --reload --port 8000

# Запустить Celery Worker (Terminal 2)
celery -A backend.tasks.celery_app worker --loglevel=info
```

Проверь: http://localhost:8000 должен открыться

---

### Шаг 2: Создать туннель через localhost.run

**Открой новый терминал (Terminal 3):**

```bash
ssh -R 80:localhost:8000 localhost.run
```

Ты увидишь что-то вроде:

```
Connect to http://abc123xyz.lhrtunnel.link or https://abc123xyz.lhrtunnel.link
```

**Твой публичный URL:** `https://abc123xyz.lhrtunnel.link` ✅

---

### Шаг 3: Обновить настройки Telegram бота

1. Открой @BotFather в Telegram
2. Отправь команду:
   ```
   /setdomain
   ```
3. Выбери своего бота
4. Введи домен **БЕЗ https://**:
   ```
   abc123xyz.lhrtunnel.link
   ```

---

### Шаг 4: Обновить .env файл

```bash
# Отредактируй apps/reviews/.env
nano apps/reviews/.env
```

Измени `FRONTEND_URL`:

```bash
FRONTEND_URL=https://abc123xyz.lhrtunnel.link
```

**Перезапусти FastAPI** (Ctrl+C в Terminal 1, затем снова `uvicorn ...`)

---

### Шаг 5: Протестировать авторизацию

1. Открой в браузере: `https://abc123xyz.lhrtunnel.link`
2. Нажми "Login with Telegram"
3. Авторизуйся через Telegram
4. Создай задачу с артикулом WB
5. Проверь что пришло уведомление в Telegram

---

## Troubleshooting

### Проблема: SSH туннель отключается

**Решение:** Добавь `ServerAliveInterval` для keep-alive

```bash
ssh -o ServerAliveInterval=60 -R 80:localhost:8000 localhost.run
```

---

### Проблема: URL изменился, Telegram Login не работает

**Что случилось:** localhost.run выдаёт новый URL при каждом подключении

**Решение:**

1. Получи новый URL из SSH output
2. Обнови `/setdomain` в @BotFather
3. Обнови `FRONTEND_URL` в `.env`
4. Перезапусти FastAPI

---

### Проблема: Telegram уведомления не приходят

**Проверь:**

1. `TELEGRAM_BOT_TOKEN` правильный в `.env`
2. Celery worker запущен и нет ошибок
3. Отправь тестовое сообщение боту: `/start`

**Debug:**

```bash
# Проверь Celery логи (Terminal 2)
# Должны быть строки типа:
[2024-02-05 23:00:00,123: INFO/MainProcess] Task backend.tasks.analyze_article_task[...] received
[2024-02-05 23:00:05,456: INFO/ForkPoolWorker-1] Task backend.tasks.analyze_article_task[...] succeeded
```

---

### Проблема: CORS ошибка в браузере

**Решение:** Обнови `backend/main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для тестов, в продакшн ограничить!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Перезапусти FastAPI.

---

## Альтернативы localhost.run

Если localhost.run не работает, попробуй:

### 1. ngrok (требует регистрацию, но стабильнее)

```bash
# Установка
brew install ngrok

# Регистрация
ngrok config add-authtoken YOUR_TOKEN

# Запуск
ngrok http 8000
```

### 2. cloudflared (от Cloudflare)

```bash
# Установка
brew install cloudflared

# Запуск
cloudflared tunnel --url http://localhost:8000
```

### 3. serveo.net (аналог localhost.run)

```bash
ssh -R 80:localhost:8000 serveo.net
```

---

## Когда переходить на production?

**Используй localhost.run/ngrok для:**
- ✅ Первичное тестирование Telegram auth
- ✅ Демо для 1-2 человек
- ✅ CustDev интервью (показать работающий прототип)

**Переходи на production hosting когда:**
- ❌ Нужен постоянный URL
- ❌ Больше 5-10 пользователей
- ❌ Нужны SLA и стабильность
- ❌ Планируешь запускать платный продукт

Следуй [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md) для полного deploy.

---

## Полный workflow

```bash
# Terminal 1: FastAPI
cd apps/reviews
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Celery Worker
cd apps/reviews
source venv/bin/activate
celery -A backend.tasks.celery_app worker --loglevel=info

# Terminal 3: localhost.run tunnel
ssh -o ServerAliveInterval=60 -R 80:localhost:8000 localhost.run

# → Копируешь URL из output Terminal 3
# → Обновляешь /setdomain в @BotFather
# → Обновляешь FRONTEND_URL в .env
# → Перезапускаешь Terminal 1 (FastAPI)
# → Открываешь URL в браузере
# → Profit! 🎉
```

---

## Полезные команды

```bash
# Проверить что Redis работает
redis-cli ping  # должен вернуть PONG

# Проверить что локальный сервер работает
curl http://localhost:8000/health

# Проверить что публичный URL работает
curl https://YOUR-URL.lhrtunnel.link/health

# Посмотреть логи FastAPI
# (смотри Terminal 1)

# Посмотреть логи Celery
# (смотри Terminal 2)

# Посмотреть задачи в Redis
redis-cli
> KEYS *
> GET celery-task-meta-<task-id>
```

---

## Следующие шаги

После того как протестируешь через localhost.run:

1. [ ] Провести 2-3 CustDev интервью с демо
2. [ ] Собрать фидбек по UX/UI
3. [ ] Решить: продолжать или pivot?
4. [ ] Если продолжать → deploy на Railway/Render
5. [ ] Настроить custom domain agentiq.ru
6. [ ] Добавить onboarding flow
7. [ ] Добавить billing (если платный)

---

**Status:** ✅ Ready to use
**Last Updated:** 2026-02-05
