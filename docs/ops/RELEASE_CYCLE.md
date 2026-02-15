# Release Cycle & Development Workflow

**Last updated:** 2026-02-15
**Status:** Active

## Overview

AgentIQ релизный цикл для MVP stage — баланс между скоростью разработки и контролем качества. Включает AI-powered code review, автоматизированное тестирование и безопасный деплой.

---

## 🌍 Окружения

### 1. Local Development

**Машина разработчика** (MacBook)

```
Backend:  http://localhost:8001
Frontend: http://localhost:5173
Database: PostgreSQL local или Docker
```

**Характеристики:**
- Hot reload (Vite + uvicorn --reload)
- Моки внешних API (WB/Ozon) или sandbox
- Быстрая итерация без влияния на prod
- Полный доступ к логам и дебагу

**Setup:**
```bash
# Backend
cd apps/chat-center/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8001

# Frontend
cd apps/chat-center/frontend
npm run dev
```

---

### 2. Staging

**VPS:** 79.137.175.164
**URL:** https://staging.agentiq.ru
**Database:** agentiq_chat_staging

```
Backend:  localhost:8002 -> staging.agentiq.ru/api
Frontend: /var/www/staging/
Celery:   agentiq-staging-celery (systemd)
```

**Характеристики:**
- Копия production инфраструктуры
- Реальные интеграции WB/Ozon API
- Тестирование перед релизом
- Демо для клиентов/инвесторов

**Auto-deploy:** каждый push в `main` → автоматический деплой на staging

**Setup staging:** см. секцию "Настройка Staging"

---

### 3. Production

**VPS:** 79.137.175.164
**URL:** https://agentiq.ru
**Database:** agentiq_chat

```
Backend:  localhost:8001 -> agentiq.ru/api
Frontend: /var/www/agentiq/
Celery:   agentiq-celery (systemd)
```

**Характеристики:**
- Реальные пользователи
- Мониторинг 24/7 (Sentry, UptimeRobot)
- Бэкапы БД (daily)
- Manual deploy только после QA на staging

**Deploy:** Manual trigger через GitHub Actions

---

## 🔄 Release Workflow

### Standard Flow

```
┌──────────────┐
│ 1. Feature   │  git checkout -b feature/ai-draft
│    Branch    │  code + local test
└──────┬───────┘
       │
┌──────▼───────┐
│ 2. AI Code   │  Push → AI review (Claude/o1)
│    Review    │  Fix issues
└──────┬───────┘
       │
┌──────▼───────┐
│ 3. Merge to  │  PR approved → merge to main
│    main      │
└──────┬───────┘
       │
┌──────▼───────┐
│ 4. Auto      │  GitHub Actions → deploy to staging
│    Staging   │  Smoke tests run
└──────┬───────┘
       │
┌──────▼───────┐
│ 5. Manual QA │  5-10 min checklist
│    on Staging│  Test new features + regression
└──────┬───────┘
       │
┌──────▼───────┐
│ 6. Deploy    │  Manual trigger (GitHub Actions)
│    Production│  Backup DB → deploy → smoke test
└──────────────┘
```

---

## 🤖 AI Code Review Strategy

### Cross-Model Validation

**Принцип:** Разные AI модели ревьюят код друг друга

```
Claude 4.5/4.6 пишет → o1-preview + gpt-4o ревьюят
OpenAI (o1/gpt-4o) пишет → Claude 4.6 Opus ревьюит
Human пишет → Claude 4.6 + o1 (оба, dual review)
```

### Model Selection

| Code Type | Primary Reviewer | Why |
|-----------|-----------------|-----|
| Architecture changes | Claude 4.6 Opus | Глубокое понимание контекста |
| Bug fixes | o1-preview | Reasoning, находит edge cases |
| Features | Claude 4.5 Sonnet | Баланс скорости/качества |
| Refactoring | Claude 4.6 Opus | Видит общую картину |
| Security changes | Claude 4.5 + o1 | Оба хороши в security |
| Tests | gpt-4o | Знает best practices |
| Docs | gpt-4o-mini | Быстро и дёшево |

### Commit Convention (для детекта автора)

```bash
# Claude пишет код
git commit -m "Add AI draft quality validation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# o1-preview пишет код
git commit -m "Implement retry logic

Co-Authored-By: OpenAI o1-preview <o1@openai.com>"

# gpt-4o пишет код
git commit -m "Fix WB pagination bug

Co-Authored-By: OpenAI gpt-4o <gpt4o@openai.com>"

# Human пишет код (dual review)
git commit -m "Update user settings UI

Co-Authored-By: Ivan Ilin <ivan@agentiq.ru>"
```

**GitHub Action парсит `Co-Authored-By:`** и выбирает соответствующего ревьюера.

### Review Checklist

AI проверяет:

**Security ✅**
- SQL injection (raw queries)
- XSS vulnerabilities
- Secrets в коде (API keys)
- Authentication bypass
- CLAUDE.md не закоммичен

**Architecture ✅**
- DRY violations
- Слишком сложные функции (>50 lines)
- Separation of concerns
- Async/await использование

**Performance ✅**
- N+1 queries
- Отсутствие индексов
- Неэффективные циклы
- Memory leaks

**AgentIQ-specific ✅**
- Guardrails rules не хардкодятся (должны быть в GUARDRAILS.md)
- Banned phrases не обещаются
- Quality score формула правильная (процентная)
- WB API пагинация обрабатывает дубликаты
- 152-ФЗ compliance

**Testing ✅**
- Критичный код покрыт тестами
- Edge cases проверены
- Моки внешних API

---

## 🧪 Testing Strategy

### Test Pyramid

```
        /\
       /E2E\      10%  - Playwright (критичные сценарии)
      /──────\
     /Integration\ 20%  - API + DB integration tests
    /────────────\
   /  Unit Tests  \ 70%  - pytest (быстрые, много)
  /────────────────\
```

### 1. Unit Tests (обязательно)

**Backend:**
```bash
cd apps/chat-center/backend
pytest tests/test_guardrails.py
pytest tests/test_ai_analyzer.py
pytest tests/test_wb_connector.py
```

**Coverage target:** 70%+ для критичных модулей

**Пример:**
```python
# tests/test_guardrails.py
def test_banned_phrase_detection():
    text = "Мы вернём вам деньги"
    result = check_guardrails(text)
    assert result["has_violations"] == True
    assert "возврат" in result["violations"]
```

### 2. Smoke Tests (критичные пути)

**После каждого деплоя:**
```python
# tests/smoke/test_critical_paths.py
def test_user_can_login():
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "testpass"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_chat_sync_works():
    response = client.post("/api/sync/trigger", headers=auth_headers)
    assert response.json()["status"] == "success"

def test_ai_suggestion_generated():
    response = client.get("/api/chats/123/suggestion", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["suggestion"]) > 0
```

**Запуск автоматически** после деплоя на staging/prod

### 3. Integration Tests

**API + Database:**
```python
def test_full_chat_flow(db_session):
    # Create seller
    seller = create_seller(db_session, email="test@wb.ru")

    # Sync chats
    sync_result = sync_wb_chats(seller.id)
    assert sync_result["chats_synced"] > 0

    # Get AI suggestion
    chat = db_session.query(Chat).first()
    suggestion = generate_ai_suggestion(chat.id)
    assert suggestion is not None

    # Send message
    send_message(chat.id, suggestion["text"])
    assert chat.chat_status == "responded"
```

### 4. E2E Tests (опционально, когда появятся ресурсы)

**Playwright:**
```typescript
// e2e/critical-paths.spec.ts
test('user can respond to urgent chat', async ({ page }) => {
  await page.goto('https://staging.agentiq.ru/app');

  // Login
  await page.fill('[data-testid="email"]', 'test@example.com');
  await page.fill('[data-testid="password"]', 'testpass');
  await page.click('[data-testid="login-btn"]');

  // Wait for chats to load
  await page.waitForSelector('.chat-item');

  // Click urgent chat
  await page.click('.chat-item.urgent');

  // Check AI suggestion appears
  await expect(page.locator('.ai-suggestion')).toBeVisible();

  // Send message
  await page.fill('[data-testid="message-input"]', 'Здравствуйте!');
  await page.click('[data-testid="send-btn"]');

  // Verify sent
  await expect(page.locator('.message.seller')).toBeVisible();
});
```

---

## 🚀 CI/CD Pipeline

### GitHub Actions Workflows

**1. AI Code Review** (`.github/workflows/ai-code-review.yml`)
- Trigger: каждый PR
- Детектит автора кода (Claude/OpenAI/Human)
- Запускает соответствующего AI reviewer
- Комментирует в PR

**2. Deploy to Staging** (`.github/workflows/deploy-staging.yml`)
- Trigger: push to `main`
- Runs: tests → deploy → smoke tests
- Auto-rollback если smoke tests fail

**3. Deploy to Production** (`.github/workflows/deploy-prod.yml`)
- Trigger: manual (workflow_dispatch)
- Runs: backup DB → deploy → smoke tests → notify
- Требует approval

---

## 📋 Pre-Release Checklist (Go/No-Go)

Перед **каждым деплоем в Production** проверить:

### Code Quality ✅
```
☐ All tests passed (pytest + smoke)
☐ AI code review approved (no critical issues)
☐ No merge conflicts
☐ CLAUDE.md not committed
```

### Staging Validation ✅
```
☐ QA checklist completed on staging
☐ New features tested manually
☐ Regression testing done (critical paths)
☐ Performance acceptable (no slowdowns)
☐ Sentry: 0 critical errors in last hour
```

### Production Readiness ✅
```
☐ Database backup created
☐ Rollback plan ready (git SHA to revert)
☐ Monitoring active (Sentry, UptimeRobot)
☐ Team available (если что-то пойдёт не так)
☐ No other deploys in progress
```

### Communication ✅
```
☐ Changelog prepared (что релизим)
☐ Breaking changes documented
☐ Users notified (если нужно)
```

**Decision:**
- ✅ **GO** — proceed with production deploy
- ❌ **NO-GO** — fix issues, retry tomorrow

---

## 🔧 Настройка Staging Environment

### 1. Поддомен DNS

**У регистратора домена:**
```
A-record:
staging.agentiq.ru -> 79.137.175.164
```

### 2. nginx config

**`/etc/nginx/sites-enabled/staging-agentiq`:**
```nginx
server {
    server_name staging.agentiq.ru;

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8002/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend
    location / {
        root /var/www/staging;
        try_files $uri $uri/ /index.html;
    }

    # SSL (certbot)
    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/staging.agentiq.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.agentiq.ru/privkey.pem;
}

# HTTP -> HTTPS redirect
server {
    listen 80;
    server_name staging.agentiq.ru;
    return 301 https://$server_name$request_uri;
}
```

**Enable:**
```bash
sudo ln -s /etc/nginx/sites-available/staging-agentiq /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. SSL Certificate

```bash
sudo certbot --nginx -d staging.agentiq.ru
```

### 4. Database Setup

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE agentiq_chat_staging;
CREATE USER agentiq_staging WITH PASSWORD 'secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE agentiq_chat_staging TO agentiq_staging;
\q
```

**Copy production data (optional):**
```bash
# Backup prod
pg_dump agentiq_chat > prod_backup.sql

# Restore to staging
psql -U agentiq_staging -d agentiq_chat_staging < prod_backup.sql
```

### 5. Backend Service

**`/etc/systemd/system/agentiq-staging.service`:**
```ini
[Unit]
Description=AgentIQ Chat Backend (Staging)
After=network.target postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/agentiq-staging
Environment="DATABASE_URL=postgresql://agentiq_staging:secure_password_here@localhost/agentiq_chat_staging"
Environment="ENV=staging"
Environment="SENTRY_ENVIRONMENT=staging"
Environment="WB_API_TOKEN=your_wb_token"
Environment="OZON_API_KEY=your_ozon_key"
ExecStart=/opt/agentiq-staging/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable agentiq-staging
sudo systemctl start agentiq-staging
sudo systemctl status agentiq-staging
```

### 6. Celery Service (Staging)

**`/etc/systemd/system/agentiq-staging-celery.service`:**
```ini
[Unit]
Description=AgentIQ Celery Worker (Staging)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/agentiq-staging/backend
Environment="DATABASE_URL=postgresql://agentiq_staging:password@localhost/agentiq_chat_staging"
Environment="ENV=staging"
ExecStart=/opt/agentiq-staging/venv/bin/celery -A app.celery_app worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
```

### 7. Deploy Script

**`/opt/agentiq-staging/deploy.sh`:**
```bash
#!/bin/bash
set -e

echo "🚀 Deploying to staging..."

cd /opt/agentiq-staging

# Pull latest
git pull origin main

# Backend
cd backend
source ../venv/bin/activate
pip install -r requirements.txt

# Run migrations (если используешь Alembic)
# alembic upgrade head

# Restart services
sudo systemctl restart agentiq-staging
sudo systemctl restart agentiq-staging-celery

# Frontend
cd ../frontend
npm install
npm run build
sudo rm -rf /var/www/staging/*
sudo cp -r dist/* /var/www/staging/
sudo chown -R www-data:www-data /var/www/staging

echo "✅ Staging deployed successfully"

# Smoke test
sleep 5
curl -f https://staging.agentiq.ru/api/health || (echo "❌ Health check failed" && exit 1)

echo "✅ Health check passed"
```

---

## 📊 Monitoring & Observability

### 1. Sentry

**Environments:**
- `production` — agentiq.ru
- `staging` — staging.agentiq.ru
- `development` — localhost

**Alerts:**
- Critical errors → Telegram/Email immediately
- Warning errors → Daily digest

### 2. Health Checks

**Endpoint:** `/api/health`

```python
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "environment": os.getenv("ENV"),
        "database": check_database_connection(),
        "celery": check_celery_worker(),
        "timestamp": datetime.utcnow().isoformat()
    }
```

**UptimeRobot** monitors:
- https://agentiq.ru/api/health (every 5 min)
- https://staging.agentiq.ru/api/health (every 10 min)

### 3. Logs

**Production:**
```bash
# Backend
sudo journalctl -u agentiq-chat -f --since "10 min ago"

# Celery
sudo journalctl -u agentiq-celery -f

# nginx
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

**Staging:**
```bash
sudo journalctl -u agentiq-staging -f
```

---

## 🔙 Rollback Plan

### Quick Rollback (если что-то сломалось)

**1. Identify last working commit:**
```bash
git log --oneline -5
```

**2. Revert to previous version:**
```bash
# On VPS
cd /opt/agentiq
git checkout <previous_commit_sha>
sudo systemctl restart agentiq-chat
```

**3. Restore database (если были миграции):**
```bash
psql agentiq_chat < backup_YYYYMMDD_HHMMSS.sql
```

**4. Verify:**
```bash
curl https://agentiq.ru/api/health
```

### Automated Rollback

**GitHub Action** может автоматически откатить если smoke tests fail после деплоя.

---

## 💰 Cost Tracking

### AI Code Review
- ~50 PRs/месяц × $0.10 = **$5/мес**

### VPS (staging + production)
- Текущий VPS: **~$10/мес**
- Или отдельный staging VPS: **+$5-10/мес**

### Monitoring
- Sentry free tier: **$0**
- UptimeRobot free tier: **$0**

**Total:** **$5-15/мес** для полного setup

---

## 📈 Roadmap

### Фаза 1: MVP (сейчас)
- ✅ Local development
- ✅ Production environment
- ✅ Manual deploys
- ✅ Pytest unit tests
- ✅ Sentry monitoring

### Фаза 2: Automation (1-2 недели)
- 🔄 Staging environment
- 🔄 AI Code Review (GitHub Actions)
- 🔄 Auto-deploy to staging
- 🔄 Manual QA checklist
- 🔄 Smoke tests

### Фаза 3: Advanced (1-2 месяца)
- ⏳ E2E tests (Playwright)
- ⏳ Load testing (k6)
- ⏳ Feature flags
- ⏳ Gradual rollouts (canary deploys)

### Фаза 4: Scale (3+ месяца)
- ⏳ Kubernetes (если масштаб потребует)
- ⏳ Multiple regions
- ⏳ Advanced monitoring (Grafana, Prometheus)

---

## 🔗 Related Docs

- **Architecture:** `docs/architecture/architecture.md`
- **Guardrails:** `docs/GUARDRAILS.md`
- **Testing:** `apps/chat-center/backend/tests/README.md`
- **Deployment:** `apps/chat-center/DEPLOYMENT.md`
- **Celery Monitoring:** `docs/ops/CELERY_MONITORING.md`

---

## Changelog

**2026-02-15:**
- Initial release cycle documentation
- AI code review strategy (Claude 4.6 + o1-preview)
- Staging environment setup
- CI/CD pipelines (GitHub Actions)
