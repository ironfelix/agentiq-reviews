# AgentIQ MVP — Deployment Checklist

## Pre-Deployment Checklist

### Local Testing ✓

- [ ] Виртуальное окружение создано и активировано
- [ ] Все зависимости установлены (`pip install -r requirements.txt`)
- [ ] Redis запущен и доступен (`redis-cli ping`)
- [ ] База данных инициализирована (`python3 init_db.py`)
- [ ] `.env` файл создан и заполнен
- [ ] Telegram бот создан в @BotFather
- [ ] FastAPI сервер запускается без ошибок
- [ ] Celery worker запускается без ошибок
- [ ] Авторизация через Telegram работает (ngrok)
- [ ] Создание задачи работает
- [ ] Celery обрабатывает задачи
- [ ] Telegram уведомления приходят
- [ ] Отчёт отображается корректно

---

## Production Deployment

### 1. Infrastructure Setup

#### Database Migration: SQLite → PostgreSQL

**Почему:** SQLite не подходит для production с concurrent writes.

```bash
# 1. Установить PostgreSQL на сервере или использовать managed service
# Railway, Render, Supabase, AWS RDS

# 2. Обновить DATABASE_URL в .env
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# 3. Обновить backend/database.py (уже поддерживает PostgreSQL)

# 4. Обновить backend/tasks.py для sync connection
DATABASE_URL_SYNC=postgresql://user:pass@host:5432/dbname
```

**Checklist:**
- [ ] PostgreSQL instance создан
- [ ] Connection string получен
- [ ] `.env` обновлён
- [ ] `init_db.py` запущен на новой БД
- [ ] Проверка подключения OK

---

#### Redis Setup

**Options:**
1. **Managed Redis** (рекомендуется)
   - Railway Redis addon
   - Render Redis
   - Redis Labs (free tier)
   - AWS ElastiCache

2. **Self-hosted Redis**
   - На том же сервере что и backend
   - Docker container

**Checklist:**
- [ ] Redis instance создан
- [ ] Connection URL получен
- [ ] `.env` обновлён: `REDIS_URL=redis://...`
- [ ] Проверка: `redis-cli -u $REDIS_URL ping`

---

### 2. Backend Deployment

#### Option A: Railway (рекомендуется)

**Setup:**
```bash
# 1. Создать аккаунт на railway.app
# 2. Создать новый проект
# 3. Deploy from GitHub repo

# 4. Добавить environment variables:
# Railway Dashboard → Variables → Add:
SECRET_KEY=...
DATABASE_URL=...
REDIS_URL=...
TELEGRAM_BOT_TOKEN=...
TELEGRAM_BOT_USERNAME=...
WBCON_EMAIL=...
WBCON_PASS=...
WBCON_FB_BASE=...
FRONTEND_URL=https://agentiq.ru
ENVIRONMENT=production
```

**Procfile:**
```
web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
worker: celery -A backend.tasks.celery_app worker --loglevel=info
```

**Checklist:**
- [ ] Railway project создан
- [ ] GitHub repo подключен
- [ ] Environment variables добавлены
- [ ] Deploy успешен
- [ ] Web service работает
- [ ] Worker service работает
- [ ] Logs чистые (нет ошибок)

---

#### Option B: Render

**Setup:**
```bash
# 1. render.com → New → Web Service
# 2. Connect GitHub repo
# 3. Build Command: pip install -r requirements.txt
# 4. Start Command: uvicorn backend.main:app --host 0.0.0.0 --port $PORT

# 5. Создать отдельный Worker service:
# Build Command: pip install -r requirements.txt
# Start Command: celery -A backend.tasks.celery_app worker --loglevel=info
```

**Checklist:**
- [ ] Web Service создан
- [ ] Background Worker создан
- [ ] Environment variables добавлены
- [ ] Deploy успешен
- [ ] Health check OK: `https://your-app.onrender.com/health`

---

### 3. Frontend / Static Files

#### Option A: Vercel (рекомендуется для static)

**Setup:**
```bash
# 1. vercel.com → Import Project
# 2. Connect GitHub repo
# 3. Root Directory: apps/reviews/templates (если хочешь static hosting)

# Или просто используй FastAPI для serving templates (проще)
```

**Checklist:**
- [ ] Frontend deployment выбран
- [ ] Domain настроен
- [ ] HTTPS работает
- [ ] Templates корректно отдаются

---

### 4. Domain & SSL

#### DNS Setup

**Для agentiq.ru:**

```bash
# A Record (если используешь VPS)
A    @         123.45.67.89
A    www       123.45.67.89

# CNAME (если используешь Railway/Render/Vercel)
CNAME @         your-app.railway.app
CNAME www       your-app.railway.app
```

**Checklist:**
- [ ] DNS records добавлены
- [ ] Propagation complete (24-48h max)
- [ ] `ping agentiq.ru` работает
- [ ] HTTPS настроен (автоматически на Railway/Vercel)
- [ ] HTTP → HTTPS redirect работает

---

### 5. Telegram Bot Configuration

**Update @BotFather:**

```
/setdomain
→ выбрать бота
→ ввести: agentiq.ru

/setdescription
→ AI-платформа для анализа отзывов Wildberries. Автоматический анализ причин негатива, тренды, рекомендации, черновики ответов.

/setabouttext
→ Автоматизация работы с отзывами WB: анализ, классификация, генерация ответов.

/setuserpic
→ загрузить логотип AgentIQ
```

**Checklist:**
- [ ] Domain обновлён
- [ ] Description обновлён
- [ ] Profile pic загружен
- [ ] `/start` команда работает (опционально)
- [ ] Notifications отправляются

---

### 6. Environment Variables (Production)

**CRITICAL — проверь все:**

```bash
# Security
SECRET_KEY=<strong-random-key>  # НЕ использовать dev key!
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql+asyncpg://...  # PostgreSQL, не SQLite!

# Redis
REDIS_URL=redis://...  # Managed Redis

# Telegram
TELEGRAM_BOT_TOKEN=<production-bot-token>
TELEGRAM_BOT_USERNAME=<production-bot-username>

# WBCON
WBCON_EMAIL=<your-email>
WBCON_PASS=<your-password>
WBCON_FB_BASE=https://01-fb.wbcon.su

# Frontend
FRONTEND_URL=https://agentiq.ru  # HTTPS обязательно!
```

**Checklist:**
- [ ] SECRET_KEY уникальный (не dev key!)
- [ ] ENVIRONMENT=production
- [ ] DATABASE_URL → PostgreSQL
- [ ] REDIS_URL правильный
- [ ] FRONTEND_URL → production domain (HTTPS)
- [ ] Все credentials secure (не в git!)

---

### 7. Security Hardening

**FastAPI:**
```python
# backend/main.py

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# CORS (production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://agentiq.ru"],  # Только твой домен
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["agentiq.ru", "www.agentiq.ru"]
)
```

**Secrets:**
```bash
# НИКОГДА не коммитить:
- .env
- agentiq.db
- *.log

# Добавить в .gitignore:
echo ".env" >> .gitignore
echo "*.db" >> .gitignore
echo "*.log" >> .gitignore
echo "logs/" >> .gitignore
```

**Checklist:**
- [ ] CORS настроен (только нужные origins)
- [ ] TrustedHost middleware добавлен
- [ ] Secrets не в git
- [ ] `.gitignore` обновлён
- [ ] Rate limiting добавлен (опционально)

---

### 8. Monitoring & Logging

#### Error Tracking

**Option 1: Sentry (рекомендуется)**
```bash
pip install sentry-sdk[fastapi]

# backend/main.py
import sentry_sdk
sentry_sdk.init(
    dsn="https://...@sentry.io/...",
    environment="production"
)
```

**Option 2: Rollbar**
```bash
pip install rollbar
```

**Checklist:**
- [ ] Error tracking setup
- [ ] Test error sent
- [ ] Notifications configured

---

#### Logging

**Structured logging:**
```python
# backend/main.py
import logging
import json

logger = logging.getLogger("agentiq")
logger.setLevel(logging.INFO)

# JSON formatter for production
formatter = logging.Formatter(
    '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
```

**Checklist:**
- [ ] Logging configured
- [ ] Log level: INFO в production
- [ ] Logs accessible (Railway/Render dashboard)

---

### 9. Performance Optimization

**Database indexes:**
```sql
-- Добавить если используешь PostgreSQL
CREATE INDEX idx_tasks_user_id ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_reports_task_id ON reports(task_id);
CREATE INDEX idx_reports_article_id ON reports(article_id);
```

**Celery tuning:**
```python
# backend/tasks.py
celery_app = Celery(
    "agentiq",
    broker=REDIS_URL,
    backend=REDIS_URL,
    broker_connection_retry_on_startup=True,  # Важно!
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 минут max
)
```

**Checklist:**
- [ ] Database indexes добавлены
- [ ] Celery tuning применён
- [ ] Connection pooling настроен
- [ ] Task timeouts установлены

---

### 10. Testing Production

**Smoke tests:**

```bash
# 1. Health check
curl https://agentiq.ru/health

# 2. Landing page
curl https://agentiq.ru/

# 3. API (with auth)
curl https://agentiq.ru/api/tasks/list \
  -H "Cookie: session_token=..."

# 4. Create task
curl -X POST https://agentiq.ru/api/tasks/create \
  -H "Content-Type: application/json" \
  -H "Cookie: session_token=..." \
  -d '{"article_id": 117220345}'
```

**End-to-end test:**
1. [ ] Открыть agentiq.ru
2. [ ] Авторизоваться через Telegram
3. [ ] Создать задачу (демо-артикул)
4. [ ] Дождаться уведомления в TG
5. [ ] Открыть отчёт по ссылке
6. [ ] Проверить все элементы отчёта

---

### 11. Backups

**Database:**
```bash
# Auto-backup (если PostgreSQL)
# Railway: automatic backups included
# Render: enable в настройках

# Manual backup:
pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql

# Restore:
psql $DATABASE_URL < backup_20240101.sql
```

**Checklist:**
- [ ] Auto-backups enabled
- [ ] Backup frequency: daily
- [ ] Restore process tested
- [ ] Backup storage: secure

---

### 12. Documentation

**Update для production:**

```markdown
# Production URLs
- Website: https://agentiq.ru
- API: https://agentiq.ru/api
- Health: https://agentiq.ru/health
- Logs: Railway/Render dashboard

# Credentials (SECURE!)
- DATABASE_URL: [in 1Password]
- REDIS_URL: [in 1Password]
- TELEGRAM_BOT_TOKEN: [in 1Password]
- SECRET_KEY: [in 1Password]

# Support
- Sentry: https://sentry.io/organizations/.../issues/
- Logs: https://railway.app/project/.../logs
```

**Checklist:**
- [ ] Production URLs documented
- [ ] Credentials в password manager
- [ ] Runbook создан (как перезапустить)
- [ ] Incident response plan

---

### 13. Go-Live Checklist

**Final checks:**

- [ ] Все environment variables правильные
- [ ] Database migrations applied
- [ ] Redis подключен
- [ ] Celery worker запущен
- [ ] HTTPS работает
- [ ] Telegram bot domain настроен
- [ ] Error tracking работает
- [ ] Backups настроены
- [ ] Monitoring работает
- [ ] End-to-end test passed
- [ ] Team уведомлён
- [ ] Rollback plan готов

---

### 14. Post-Launch Monitoring

**First 24 hours:**

- [ ] Check error logs каждый час
- [ ] Monitor Celery queue length
- [ ] Check response times
- [ ] Verify all tasks completing
- [ ] Check Telegram notifications arriving
- [ ] Monitor database size
- [ ] Monitor Redis memory

**First week:**

- [ ] Daily error review
- [ ] Performance metrics
- [ ] User feedback collection
- [ ] Bug triage
- [ ] Database optimization

---

## Rollback Plan

**If something goes wrong:**

1. **FastAPI issues:**
   ```bash
   # Railway: rollback to previous deploy
   railway rollback

   # Manual: git revert
   git revert HEAD
   git push
   ```

2. **Database issues:**
   ```bash
   # Restore from backup
   psql $DATABASE_URL < backup_latest.sql
   ```

3. **Celery issues:**
   ```bash
   # Restart worker
   railway restart <worker-service-id>

   # Purge queue (если застряло)
   celery -A backend.tasks.celery_app purge
   ```

---

## Success Criteria

MVP считается успешно задеплоенным если:

- ✅ Авторизация через Telegram работает
- ✅ Создание задач работает
- ✅ Celery обрабатывает задачи
- ✅ Уведомления приходят
- ✅ Отчёты отображаются
- ✅ Нет критических ошибок в логах
- ✅ Response time < 2s
- ✅ Uptime > 99% (после первой недели)

---

## Contacts & Support

**If stuck:**
1. Check logs (Railway/Render dashboard)
2. Check Sentry errors
3. Test manually with curl
4. Rollback if critical

**Emergency contacts:**
- Developer: @your_telegram
- Infrastructure: Railway/Render support
- Database: PostgreSQL support
