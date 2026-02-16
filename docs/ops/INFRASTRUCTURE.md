# AgentIQ — Infrastructure Overview

Текущая архитектура развёртывания (февраль 2026).

---

## Сервер

**VPS (Virtual Private Server)**
- Provider: *(судя по имени хоста — Standard VPS)*
- **IP:** `79.137.175.164`
- **OS:** Ubuntu Linux (24.04 LTS)
- **Specs:** 2 vCPU, 4GB RAM, 20GB SSD
- **SSH:** `ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164`

**Домен:**
- `agentiq.ru` (production)
- SSL: Let's Encrypt (автообновление через certbot)

---

## Application Stack

### Backend (FastAPI)
```
Service: agentiq-chat
Port: 8001 (localhost only, за nginx)
Workers: 2 (uvicorn multiprocessing)
Location: /opt/agentiq/app/apps/chat-center/backend/
Venv: /opt/agentiq/venv/
User: ubuntu
```

**Start/Stop:**
```bash
sudo systemctl start agentiq-chat
sudo systemctl stop agentiq-chat
sudo systemctl restart agentiq-chat
sudo systemctl status agentiq-chat
```

**Logs:**
```bash
sudo journalctl -u agentiq-chat -f
```

**Environment variables:**
- File: `/opt/agentiq/app/apps/chat-center/backend/.env`
- Keys: DATABASE_URL, REDIS_URL, SECRET_KEY, ENCRYPTION_KEY, DEEPSEEK_API_KEY

### Frontend (React SPA)
```
Build: Vite
Location: /var/www/agentiq/
Entry: /var/www/agentiq/app/index.html (SPA)
Landing: /var/www/agentiq/landing.html (static)
Assets: /var/www/agentiq/assets/
User: www-data
```

### Nginx (Reverse Proxy)
```
Config: /etc/nginx/sites-enabled/agentiq
Port: 80 → 443 redirect
SSL: 443
```

**Routes:**
- `GET /` → `/var/www/agentiq/landing.html` (landing page)
- `GET /app/*` → `/var/www/agentiq/app/index.html` (React SPA with client-side routing)
- `GET|POST /api/*` → `http://127.0.0.1:8001/api/` (FastAPI proxy)
- `/api/metrics` → НЕ проксируется публично (Prometheus scrape только localhost)

**Reload config:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

---

## Database

**PostgreSQL**
- Version: 14+
- Database: `agentiq_chat`
- User: `agentiq`
- Password: `agentiq123` (⚠️ TODO: rotate to stronger password)
- Host: `localhost:5432`
- Connection: asyncpg via SQLAlchemy 2.0 async

**Access:**
```bash
sudo -u postgres psql -d agentiq_chat
```

**Tables:**
- `sellers` — продавцы (users)
- `chats` — чаты с покупателями (WB/Ozon)
- `messages` — сообщения в чатах
- `interactions` — unified entity (чаты + вопросы + отзывы)
- `interaction_events` — history events
- `sla_rules` — SLA правила
- `runtime_setting` — runtime config
- `customer_profile` — профили покупателей
- `product_cache` — кэш карточек товаров (WB CDN)
- `leads` — заявки с лендинга

**Backups:**
- TODO: automated daily backups

---

## Cache & Queue

### Redis
```
Port: 6379
DB: 0
Use cases:
  - Response cache (AI-generated drafts)
  - Rate limiting (API throttling)
  - Session storage (future)
```

**Access:**
```bash
redis-cli
```

### Celery (Background Tasks)
```
Service worker: agentiq-celery
Service beat: agentiq-celery-beat
Workers: 2 processes
Broker: Redis (redis://localhost:6379/0)
```

**Periodic tasks (beat schedule):**
- `sync_all_sellers` — каждые 30 сек (синхронизация чатов с WB/Ozon)
- `check_sla_escalation` — каждые 5 мин (проверка SLA нарушений)
- `analyze_pending_chats` — каждые 2 мин (AI анализ новых чатов)
- `auto_close_inactive_chats` — каждые 24 часа (закрытие чатов без активности 10+ дней)

**Start/Stop:**
```bash
sudo systemctl restart agentiq-celery
sudo systemctl restart agentiq-celery-beat
sudo systemctl status agentiq-celery
sudo systemctl status agentiq-celery-beat
```

**Logs:**
```bash
sudo journalctl -u agentiq-celery -f
sudo journalctl -u agentiq-celery-beat -f
```

---

## External Services

### WB Connector API (Feedbacks & Questions)
- **Feedbacks:** `https://19-fb.wbcon.su/` (JWT auth, exp: 2026-03-10)
- **Questions:** `https://qs.wbcon.su/` (JWT auth)
- Rate limits: ~100 req/min per token
- Used for: sync отзывов и вопросов покупателей

### WB Chat API
- Official WB API for chat management
- Auth: API key в seller credentials
- Features: read messages, send replies, mark as read
- Gaps: нет webhooks (только polling), нет связи с отзывами, нет order_id в чате

### WB CDN (Public)
- **Card data:** `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json`
- **Price history:** `.../price-history.json`
- No auth required
- Cache TTL: 24h (в `product_cache` таблице)

### DeepSeek API (LLM)
- API: `https://api.deepseek.com/v1/`
- Model: `deepseek-chat`
- Use cases:
  - AI анализ чатов (intent detection, sentiment, priority)
  - Draft generation (AI-suggested replies)
  - Communication quality analysis
- Cost: ~$0.14 per 1M input tokens, ~$0.28 per 1M output tokens
- API key: `DEEPSEEK_API_KEY` in `.env`

### Yandex.Metrika (Analytics)
- Counter ID: `106846293`
- Tracking: clickmap, link tracking, accurate bounce rate
- Location: landing page `<head>`

---

## Monitoring & Observability

### Prometheus Metrics
- Endpoint: `http://127.0.0.1:8001/api/metrics`
- Metrics:
  - `http_requests_total{method, path, status_code}`
  - `http_request_duration_seconds{method, path}`
- Scrape: TODO (Prometheus server not configured yet)

### Sentry (Error Tracking)
- Status: Disabled (no DSN configured)
- TODO: enable for production error tracking

### Logs
- **Backend:** `sudo journalctl -u agentiq-chat -f`
- **Celery:** `sudo journalctl -u agentiq-celery -f`
- **Nginx:** `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **PostgreSQL:** `/var/log/postgresql/`

---

## Deployment Process

### Frontend Deploy
```bash
# 1. Build locally
cd apps/chat-center/frontend
npm run build

# 2. Upload to server
rsync -avz --delete -e "ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem" \
  dist/ ubuntu@79.137.175.164:/tmp/agentiq-deploy/

# 3. Move to production
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164 "
  sudo cp /tmp/agentiq-deploy/index.html /var/www/agentiq/landing.html
  sudo cp /tmp/agentiq-deploy/app/index.html /var/www/agentiq/app/index.html
  sudo rm -rf /var/www/agentiq/assets/*
  sudo cp -r /tmp/agentiq-deploy/assets/* /var/www/agentiq/assets/
  sudo chown -R www-data:www-data /var/www/agentiq/
"
```

### Backend Deploy
```bash
# 1. Upload code
rsync -avz --delete -e "ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem" \
  --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
  apps/chat-center/backend/app/ \
  ubuntu@79.137.175.164:/tmp/backend-update/

# 2. Copy to production
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164 "
  sudo cp -r /tmp/backend-update/* /opt/agentiq/app/apps/chat-center/backend/app/
  sudo chown -R ubuntu:ubuntu /opt/agentiq/app/apps/chat-center/backend/app/
  sudo systemctl restart agentiq-chat
  sudo systemctl restart agentiq-celery
"
```

### Database Migrations
```bash
# Manual migrations (TODO: setup Alembic)
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164
sudo -u postgres psql -d agentiq_chat

# Run SQL migrations
ALTER TABLE ...;
GRANT ALL PRIVILEGES ON TABLE ... TO agentiq;
```

---

## Security

### Current State
- ✅ SSL/TLS (Let's Encrypt)
- ✅ Firewall: only 22, 80, 443 open
- ✅ SSH: key-based auth only
- ✅ API: JWT auth for protected endpoints
- ✅ Credentials encryption: AES-256 via `ENCRYPTION_KEY`
- ⚠️ `SECRET_KEY` = weak default ("change-me-in-production")
- ⚠️ DB password = weak ("agentiq123")
- ⚠️ No automated backups
- ⚠️ No secrets rotation policy

### TODO
- [ ] Rotate SECRET_KEY to strong random value
- [ ] Rotate DB password
- [ ] Setup automated daily backups
- [ ] Enable Sentry for production
- [ ] Setup Prometheus scraping
- [ ] Rate limiting on public endpoints (/api/leads)
- [ ] Secrets rotation policy (JWT tokens, API keys)

See: `docs/security/SECURITY_AUDIT.md` for full security review.

---

## Scaling Path (Future)

**Current limits:**
- 1 server (single point of failure)
- 2 workers (can handle ~100-200 concurrent requests)
- No load balancer
- No CDN for static assets

**When to scale:**
- >100 active sellers
- >10k chats/day
- >1000 concurrent users

**Scaling options:**
1. **Vertical:** upgrade VPS (4 CPU, 8GB RAM)
2. **Horizontal:**
   - Add 2nd app server behind load balancer
   - Separate DB server
   - Redis cluster
   - CDN for static assets (Cloudflare)
3. **Managed services:**
   - Managed PostgreSQL (AWS RDS, Yandex Managed PostgreSQL)
   - Managed Redis (AWS ElastiCache)
   - Container orchestration (Docker + k8s / Yandex Cloud Functions)

---

## Cost Estimate (Current)

| Service | Monthly Cost |
|---------|--------------|
| VPS (2 CPU, 4GB, 20GB) | ~$10-15 |
| Domain (agentiq.ru) | ~$10/year = $1/mo |
| SSL (Let's Encrypt) | Free |
| DeepSeek API | ~$5-10 (depends on usage) |
| WB Connector API | Free (community token) |
| **Total** | **~$16-26/mo** |

**Future costs:**
- Sentry: $26/mo (team plan)
- Prometheus + Grafana: self-hosted (free) or managed (~$20/mo)
- Backups storage: ~$5/mo for 50GB

---

## References

- Production URL: https://agentiq.ru/
- API docs: https://agentiq.ru/api/docs
- Health check: https://agentiq.ru/api/health
- Metrics (internal): http://127.0.0.1:8001/api/metrics
- Deployment guide: `docs/ops/DEPLOYMENT.md`
- Security audit: `docs/security/SECURITY_AUDIT.md`
- Release cycle: `docs/ops/RELEASE_CYCLE.md`
