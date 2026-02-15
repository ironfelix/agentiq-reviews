# MVP-005: Celery Health Monitoring - Implementation Summary

**Status:** ✅ Complete
**Date:** 2026-02-15
**Developer:** Claude Sonnet 4.5

## Objective

Implement comprehensive Celery health monitoring to ensure background task processing reliability in production. Critical for AgentIQ since Celery handles chat sync, AI analysis, and SLA escalation.

## Deliverables

### 1. Health Service (`app/services/celery_health.py`)

**Function:** `get_celery_health(timeout: int = 5) -> dict`

**Features:**
- ✅ Pings Celery worker via `inspect.ping()`
- ✅ Gathers metrics: active_tasks, queue_length, scheduled_tasks
- ✅ Extracts heartbeat timestamp from worker stats
- ✅ 5-second timeout (non-blocking if worker is down)
- ✅ Fallback handling for timeout/exceptions
- ✅ Status classification: "healthy" | "degraded" | "down"

**Status Logic:**
- `down` - Worker not responding (ping fails or timeout)
- `degraded` - Worker alive but queue_length >= 100
- `healthy` - Worker alive + queue_length < 100

**Return Format:**
```python
{
    "worker_alive": bool,
    "active_tasks": int | None,
    "scheduled_tasks": int | None,
    "queue_length": int | None,
    "last_heartbeat": datetime | None,
    "status": "healthy" | "degraded" | "down"
}
```

### 2. API Endpoint (`GET /api/interactions/health/celery`)

**Location:** `app/api/interactions.py`

**Features:**
- ✅ Public endpoint (no auth required for ops monitoring)
- ✅ Returns JSON with worker status and metrics
- ✅ 5-second timeout enforced
- ✅ Added to interactions router (keeps health endpoints grouped)

**Usage:**
```bash
curl http://localhost:8001/api/interactions/health/celery
```

### 3. Ops Alerts Integration

**Location:** `app/services/interaction_metrics.py` - `get_ops_alerts()`

**Features:**
- ✅ Calls `get_celery_health()` within ops-alerts endpoint
- ✅ Generates alert if `status == "down"` (severity: critical)
- ✅ Generates alert if `status == "degraded"` (severity: medium)
- ✅ Includes `celery_health` payload in response
- ✅ Preserves existing sync_health alerts (no conflicts)

**Alert Codes:**
- `celery_worker_down` - Critical alert when worker is not responding
- `celery_queue_high` - Medium alert when queue >= 100 tasks

**Integration Point:**
```python
# In get_ops_alerts()
celery_health = get_celery_health(timeout=5)
if celery_health["status"] == "down":
    alerts.append({"code": "celery_worker_down", "severity": "critical", ...})
elif celery_health["status"] == "degraded":
    alerts.append({"code": "celery_queue_high", "severity": "medium", ...})
```

### 4. Cron Monitoring Script (`scripts/ops/celery-check.sh`)

**Features:**
- ✅ Bash script for periodic health checks
- ✅ Email alerts on failure (via sendmail)
- ✅ Color-coded output (GREEN/YELLOW/RED)
- ✅ JSON parsing with jq
- ✅ Configurable API URL and email recipient
- ✅ Exit codes: 0=healthy, 1=HTTP error, 2=down, 3=degraded, 4=unknown
- ✅ Detailed troubleshooting steps in alert emails

**Usage:**
```bash
./celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru
```

**Cron Setup (every 5 minutes):**
```cron
*/5 * * * * /opt/agentiq/scripts/ops/celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru >> /var/log/agentiq-celery-check.log 2>&1
```

**Email Alert Format:**
```
Subject: [AgentIQ CRITICAL] Celery Worker DOWN

Timestamp: 2026-02-15 10:30:00
Status: down
Worker Alive: false

Celery worker is not responding. Background tasks are not being processed.

Impact:
- Chat sync disabled
- AI analysis disabled
- SLA escalation disabled
- Auto-close tasks disabled

Action Required:
1. Check worker service: systemctl status agentiq-celery
2. Check logs: journalctl -u agentiq-celery -n 100
3. Restart if needed: systemctl restart agentiq-celery
4. Check Redis: systemctl status redis
```

### 5. Test Suite (`tests/test_celery_health.py`)

**Coverage:**
- ✅ `test_healthy_state()` - Normal queue, worker alive
- ✅ `test_degraded_state_high_queue()` - Queue >= 100 tasks
- ✅ `test_down_state_no_ping()` - Worker not responding
- ✅ `test_down_state_timeout()` - Timeout exception
- ✅ `test_down_state_exception()` - Unexpected exception
- ✅ `test_multiple_workers()` - Aggregate metrics across workers
- ✅ `test_empty_worker_responses()` - Edge case handling
- ✅ `test_health_endpoint_returns_status()` - API integration
- ✅ `test_health_endpoint_healthy()` - API healthy response
- ✅ `test_health_endpoint_down()` - API down response
- ✅ `test_ops_alerts_includes_celery_down()` - Alert integration
- ✅ `test_ops_alerts_includes_celery_degraded()` - Degraded alert
- ✅ `test_ops_alerts_no_celery_alert_when_healthy()` - No alert when healthy
- ✅ `test_ops_alerts_includes_celery_health_payload()` - Payload structure

**Test Execution:**
```bash
cd apps/chat-center/backend
source venv/bin/activate
pytest tests/test_celery_health.py -v
```

### 6. Documentation (`docs/ops/CELERY_MONITORING.md`)

**Sections:**
- ✅ Overview (why Celery monitoring is critical)
- ✅ Architecture (components diagram)
- ✅ API Reference (request/response examples)
- ✅ Status Logic (table with conditions)
- ✅ Ops Alerts Integration (alert codes, severity)
- ✅ Cron Monitoring Setup (installation, usage, email config)
- ✅ Troubleshooting (worker down, high queue, timeout)
- ✅ Testing (unit tests, manual testing)
- ✅ Production Deployment (systemd services, nginx config)
- ✅ Metrics & Observability (Prometheus integration roadmap)
- ✅ References (Celery docs, related files)
- ✅ Changelog

## Files Created

1. `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/celery_health.py` (108 lines)
2. `/Users/ivanilin/Documents/ivanilin/agentiq/scripts/ops/celery-check.sh` (183 lines)
3. `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/tests/test_celery_health.py` (334 lines)
4. `/Users/ivanilin/Documents/ivanilin/agentiq/docs/ops/CELERY_MONITORING.md` (486 lines)

## Files Modified

1. `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/api/interactions.py`
   - Added import: `from app.services.celery_health import get_celery_health`
   - Added endpoint: `@router.get("/health/celery")`

2. `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/interaction_metrics.py`
   - Modified `get_ops_alerts()` to include Celery health check
   - Added alerts for `celery_worker_down` and `celery_queue_high`
   - Added `celery_health` to response payload

## Design Decisions

### 1. Timeout Strategy
**Decision:** 5-second timeout on all inspect operations.
**Rationale:** Prevents blocking if Celery is down. API must remain responsive even if worker is unresponsive.

### 2. Status Thresholds
**Decision:** `queue_length >= 100` triggers "degraded".
**Rationale:** Based on typical load (30s sync + 5min interaction sync). 100+ tasks indicates backlog building up.

### 3. No Auth on Health Endpoint
**Decision:** `/api/interactions/health/celery` is public (no auth required).
**Rationale:** Ops monitoring tools (cron, Prometheus) shouldn't need seller auth. Health is system-level, not seller-specific.

### 4. Integration into Ops Alerts
**Decision:** Include Celery health in existing `/api/interactions/metrics/ops-alerts` endpoint.
**Rationale:** Single source of truth for operational alerts. Frontend already polls this endpoint.

### 5. Separate Health Endpoint
**Decision:** Provide dedicated `/health/celery` endpoint in addition to ops-alerts.
**Rationale:** Allows cron/Prometheus to check Celery health independently without seller context.

## Testing Strategy

### Unit Tests
- Mock `celery_app.control.inspect()` to simulate different worker states
- Test all status transitions: healthy → degraded → down
- Test timeout/exception handling
- Test multi-worker aggregation

### Integration Tests
- Test API endpoint returns correct HTTP 200 + JSON format
- Test ops-alerts includes Celery alerts when appropriate
- Test ops-alerts payload structure (celery_health field)

### Manual Testing (Production Readiness)
```bash
# 1. Test healthy state
curl http://localhost:8001/api/interactions/health/celery | jq .

# 2. Test down state (stop worker)
sudo systemctl stop agentiq-celery
curl http://localhost:8001/api/interactions/health/celery | jq .

# 3. Test degraded state (queue many tasks)
for i in {1..150}; do curl -X POST http://localhost:8001/api/interactions/sync/reviews?max_items=100; done
curl http://localhost:8001/api/interactions/health/celery | jq .

# 4. Test cron script
./scripts/ops/celery-check.sh http://localhost:8001/api/interactions/health/celery

# 5. Test ops-alerts integration
curl -H "Authorization: Bearer $TOKEN" http://localhost:8001/api/interactions/metrics/ops-alerts | jq '.alerts[] | select(.code | contains("celery"))'
```

## Production Deployment Checklist

- [ ] Deploy new code to VPS
  ```bash
  rsync -avz -e "ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem" \
    apps/chat-center/backend/ ubuntu@79.137.175.164:/opt/agentiq/apps/chat-center/backend/
  ```

- [ ] Restart backend service
  ```bash
  ssh ubuntu@79.137.175.164 "sudo systemctl restart agentiq-chat"
  ```

- [ ] Verify health endpoint works
  ```bash
  curl https://agentiq.ru/api/interactions/health/celery | jq .
  ```

- [ ] Copy cron script to server
  ```bash
  scp scripts/ops/celery-check.sh ubuntu@79.137.175.164:/opt/agentiq/scripts/ops/
  ssh ubuntu@79.137.175.164 "chmod +x /opt/agentiq/scripts/ops/celery-check.sh"
  ```

- [ ] Setup cron job
  ```bash
  ssh ubuntu@79.137.175.164
  crontab -e
  # Add: */5 * * * * /opt/agentiq/scripts/ops/celery-check.sh https://agentiq.ru/api/interactions/health/celery ops@agentiq.ru >> /var/log/agentiq-celery-check.log 2>&1
  ```

- [ ] Test cron script manually
  ```bash
  /opt/agentiq/scripts/ops/celery-check.sh https://agentiq.ru/api/interactions/health/celery
  ```

- [ ] Configure sendmail (if not already done)
  ```bash
  sudo apt-get install sendmail
  sudo sendmailconfig
  ```

- [ ] Test email alerts (stop worker, wait for cron)
  ```bash
  sudo systemctl stop agentiq-celery
  # Wait 5 minutes for cron to trigger
  # Check email: ops@agentiq.ru
  sudo systemctl start agentiq-celery
  ```

## Known Limitations

1. **No per-task metrics** - Current implementation aggregates across all tasks. Cannot monitor individual task types (sync vs AI analysis).
   - **Future:** Add per-task-type metrics using Celery events.

2. **No historical data** - Health check is point-in-time. No trend analysis.
   - **Future:** Integrate with Prometheus for time-series data.

3. **No Beat health check** - Only monitors worker, not beat scheduler.
   - **Future:** Add separate `inspect.registered()` check for beat tasks.

4. **Email dependency** - Cron script requires sendmail.
   - **Future:** Support webhooks (Slack/Telegram) or PagerDuty integration.

5. **No auto-remediation** - Script only alerts, doesn't auto-restart worker.
   - **Future:** Add `--auto-restart` flag to script.

## Future Enhancements

1. **Prometheus Integration**
   - Export metrics in Prometheus format
   - Add Grafana dashboard for Celery health

2. **Flower Integration**
   - Deploy Flower for real-time task monitoring
   - Link from health endpoint to Flower UI

3. **Auto-Restart Logic**
   - Extend cron script to auto-restart worker if down > 10min
   - Add rate limiting to prevent restart loops

4. **Beat Health Check**
   - Add separate endpoint for beat scheduler health
   - Verify periodic tasks are being scheduled

5. **Task Type Metrics**
   - Break down queue_length by task type
   - Identify which tasks are causing backlog

6. **SLA Tracking**
   - Track task execution time vs expected SLA
   - Alert on slow tasks (>2min for sync, >10s for AI)

## References

- **Celery Inspect Docs:** https://docs.celeryproject.org/en/stable/userguide/workers.html#inspecting-workers
- **Task Configuration:** `apps/chat-center/backend/app/tasks/__init__.py`
- **Sync Tasks:** `apps/chat-center/backend/app/tasks/sync.py`
- **Systemd Services:** `/etc/systemd/system/agentiq-celery*.service`
- **Ops Alerts:** `apps/chat-center/backend/app/services/interaction_metrics.py`

## Sign-off

**Implementation:** ✅ Complete
**Testing:** ✅ Unit tests written (14 test cases)
**Documentation:** ✅ Complete (`docs/ops/CELERY_MONITORING.md`)
**Production Ready:** ⚠️ Requires deployment and cron setup

**Next Steps:**
1. Deploy to VPS
2. Setup cron job
3. Test email alerts
4. Monitor for 24 hours
5. Document any issues in `/docs/ops/CELERY_MONITORING.md`
