# Celery Health Monitoring (MVP-005)

**Status:** Implemented
**Last updated:** 2026-02-15

## Overview

Celery health monitoring provides real-time visibility into background task processing health. Critical for production reliability since Celery handles:
- Chat sync (every 30s)
- Interaction sync (every 5min)
- AI analysis (every 2min)
- SLA escalation (every 5min)
- Auto-close inactive chats (daily)

## Architecture

### Components

1. **Health Service** (`app/services/celery_health.py`)
   - Pings Celery worker via `inspect.ping()`
   - Gathers metrics: active tasks, queue length, heartbeat
   - Returns status: `healthy` | `degraded` | `down`
   - Timeout: 5 seconds (non-blocking)

2. **API Endpoint** (`GET /api/interactions/health/celery`)
   - Public endpoint (no auth required for ops monitoring)
   - Returns JSON with worker status and metrics

3. **Ops Alerts Integration** (`app/services/interaction_metrics.py`)
   - Integrates Celery health into `/api/interactions/metrics/ops-alerts`
   - Generates alerts when worker is down or queue is high

4. **Cron Monitoring Script** (`scripts/ops/celery-check.sh`)
   - Bash script for periodic health checks
   - Email alerts on failure
   - Designed for cron integration

## API Reference

### GET /api/interactions/health/celery

Check Celery worker and scheduler health.

**Request:**
```bash
curl http://localhost:8001/api/interactions/health/celery
```

**Response (healthy):**
```json
{
  "worker_alive": true,
  "active_tasks": 3,
  "scheduled_tasks": 0,
  "queue_length": 5,
  "last_heartbeat": "2026-02-15T10:30:00Z",
  "status": "healthy"
}
```

**Response (degraded - high queue):**
```json
{
  "worker_alive": true,
  "active_tasks": 15,
  "scheduled_tasks": 2,
  "queue_length": 120,
  "last_heartbeat": "2026-02-15T10:30:00Z",
  "status": "degraded"
}
```

**Response (down):**
```json
{
  "worker_alive": false,
  "active_tasks": null,
  "scheduled_tasks": null,
  "queue_length": null,
  "last_heartbeat": null,
  "status": "down"
}
```

### Status Logic

| Condition | Status | Alert Severity |
|-----------|--------|----------------|
| `worker_alive=false` | `down` | Critical |
| `worker_alive=true` + `queue_length >= 100` | `degraded` | Medium |
| `worker_alive=true` + `queue_length < 100` | `healthy` | None |

## Ops Alerts Integration

Celery health is automatically included in `/api/interactions/metrics/ops-alerts`:

**Response structure:**
```json
{
  "generated_at": "2026-02-15T10:30:00Z",
  "celery_health": {
    "worker_alive": true,
    "status": "healthy",
    "active_tasks": 3,
    "queue_length": 5
  },
  "alerts": [
    {
      "code": "celery_worker_down",
      "severity": "critical",
      "title": "Celery worker не отвечает",
      "message": "Фоновые задачи не выполняются (sync, AI analysis, SLA escalation)"
    }
  ]
}
```

**Alert Codes:**

| Code | Severity | Condition |
|------|----------|-----------|
| `celery_worker_down` | `critical` | Worker not responding (no ping) |
| `celery_queue_high` | `medium` | Queue length >= 100 tasks |

## Cron Monitoring Setup

### Installation

1. Copy script to server:
```bash
scp scripts/ops/celery-check.sh ubuntu@79.137.175.164:/opt/agentiq/scripts/ops/
ssh ubuntu@79.137.175.164
chmod +x /opt/agentiq/scripts/ops/celery-check.sh
```

2. Setup cron (check every 5 minutes):
```bash
crontab -e

# Add line:
*/5 * * * * /opt/agentiq/scripts/ops/celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru >> /var/log/agentiq-celery-check.log 2>&1
```

### Script Usage

```bash
./celery-check.sh [API_URL] [EMAIL]

# Examples:
./celery-check.sh http://localhost:8001/api/interactions/health/celery
./celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru
```

**Exit Codes:**
- `0` - Healthy
- `1` - HTTP error (endpoint unreachable)
- `2` - Critical (worker down)
- `3` - Warning (high queue)
- `4` - Unknown status

### Email Alerts

When worker is down, email is sent with:
- Timestamp
- Current status
- Impact description (sync/AI/SLA disabled)
- Troubleshooting steps

**Prerequisites:**
- `sendmail` configured on server
- `jq` installed (JSON parsing)

## Troubleshooting

### Worker Down (status: "down")

**Symptoms:**
- `worker_alive: false`
- Background tasks not processing
- Chats not syncing

**Diagnosis:**
```bash
# 1. Check worker service
sudo systemctl status agentiq-celery

# 2. Check logs
sudo journalctl -u agentiq-celery -n 100

# 3. Check Redis (broker)
sudo systemctl status redis
redis-cli ping  # Should return PONG

# 4. Check beat scheduler
sudo systemctl status agentiq-celery-beat
```

**Fix:**
```bash
# Restart worker
sudo systemctl restart agentiq-celery

# Restart beat
sudo systemctl restart agentiq-celery-beat

# Verify health
curl http://localhost:8001/api/interactions/health/celery
```

### High Queue (status: "degraded")

**Symptoms:**
- `queue_length >= 100`
- Tasks taking longer to process
- Delayed sync/AI analysis

**Diagnosis:**
```bash
# 1. Check active tasks
celery -A app.tasks.sync inspect active

# 2. Check reserved (queued) tasks
celery -A app.tasks.sync inspect reserved

# 3. Check worker capacity
celery -A app.tasks.sync inspect stats
```

**Possible Causes:**
1. **High load** - Many sellers syncing simultaneously
2. **Slow external API** - WB/Ozon rate limiting
3. **Insufficient workers** - Need to scale

**Fix:**
```bash
# Option 1: Scale workers (edit systemd service)
sudo nano /etc/systemd/system/agentiq-celery.service
# Change: --concurrency=4 (instead of 2)

sudo systemctl daemon-reload
sudo systemctl restart agentiq-celery

# Option 2: Clear stuck tasks (if queue is stale)
# WARNING: Only if you're sure tasks are stuck
celery -A app.tasks.sync purge
```

### Timeout Issues

If health check times out (5s), possible causes:
1. Redis connection issue
2. Worker unresponsive (deadlock/infinite loop)
3. Network latency

Check Redis connection:
```bash
redis-cli -h localhost -p 6379 ping
```

## Testing

### Unit Tests

Located in `tests/test_celery_health.py`:

```bash
cd apps/chat-center/backend
source venv/bin/activate
pytest tests/test_celery_health.py -v
```

**Test Coverage:**
- ✅ Healthy state (normal queue)
- ✅ Degraded state (queue >= 100)
- ✅ Down state (no ping response)
- ✅ Down state (timeout)
- ✅ Multiple workers aggregation
- ✅ API endpoint integration
- ✅ Ops alerts integration

### Manual Testing

**Test healthy state:**
```bash
# Start Celery (if not running)
celery -A app.tasks.sync worker --loglevel=info

# Check health
curl http://localhost:8001/api/interactions/health/celery | jq .
```

**Test down state:**
```bash
# Stop Celery
sudo systemctl stop agentiq-celery

# Check health (should return "down")
curl http://localhost:8001/api/interactions/health/celery | jq .
```

**Test degraded state:**
```bash
# Queue many tasks to simulate high load
for i in {1..150}; do
  curl -X POST http://localhost:8001/api/interactions/sync/reviews?max_items=100
done

# Check health (should return "degraded")
curl http://localhost:8001/api/interactions/health/celery | jq .
```

## Metrics & Observability

### Prometheus Integration (Future)

Health endpoint can be scraped by Prometheus:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'agentiq-celery'
    scrape_interval: 30s
    metrics_path: '/api/interactions/health/celery'
    static_configs:
      - targets: ['localhost:8001']
```

Convert to Prometheus format:
```python
# Add to /api/metrics endpoint
celery_worker_up = Gauge('celery_worker_up', 'Celery worker is alive')
celery_active_tasks = Gauge('celery_active_tasks', 'Active tasks')
celery_queue_length = Gauge('celery_queue_length', 'Queue length')
```

## Production Deployment

### systemd Services

**Worker service** (`/etc/systemd/system/agentiq-celery.service`):
```ini
[Unit]
Description=AgentIQ Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/agentiq/apps/chat-center/backend
Environment="PATH=/opt/agentiq/apps/chat-center/backend/venv/bin"
ExecStart=/opt/agentiq/apps/chat-center/backend/venv/bin/celery -A app.tasks.sync worker --loglevel=info --concurrency=2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Beat service** (`/etc/systemd/system/agentiq-celery-beat.service`):
```ini
[Unit]
Description=AgentIQ Celery Beat Scheduler
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/agentiq/apps/chat-center/backend
Environment="PATH=/opt/agentiq/apps/chat-center/backend/venv/bin"
ExecStart=/opt/agentiq/apps/chat-center/backend/venv/bin/celery -A app.tasks.sync beat --loglevel=info
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration

No changes needed (health endpoint already proxied via `/api`).

## References

- **Celery Monitoring Guide:** https://docs.celeryproject.org/en/stable/userguide/monitoring.html
- **Inspect API:** https://docs.celeryproject.org/en/stable/userguide/workers.html#inspecting-workers
- **Task Reference:** `apps/chat-center/backend/app/tasks/sync.py`
- **Systemd Services:** `/etc/systemd/system/agentiq-celery*.service`

## Changelog

### 2026-02-15 - MVP-005 Initial Implementation
- ✅ Created `app/services/celery_health.py` with 5-second timeout
- ✅ Added `GET /api/interactions/health/celery` endpoint
- ✅ Integrated into `/api/interactions/metrics/ops-alerts`
- ✅ Created `scripts/ops/celery-check.sh` for cron monitoring
- ✅ Added comprehensive test coverage (`tests/test_celery_health.py`)
- ✅ Documented setup, troubleshooting, and production deployment
