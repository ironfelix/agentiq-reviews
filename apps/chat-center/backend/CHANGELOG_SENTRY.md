# Sentry Integration - Change Log (MVP-003)

## Summary

Added optional Sentry error tracking integration to AgentIQ Chat Center backend.

**Key principle:** Sentry is **OPTIONAL**. Application works normally when `SENTRY_DSN` is empty (default).

## Changes

### 1. Dependencies (`requirements.txt`)

**Added:**
```
sentry-sdk[fastapi]==2.22.0
```

Includes FastAPI and Celery integrations.

### 2. Configuration (`app/config.py`)

**Added settings:**
```python
# Sentry Error Tracking (optional)
SENTRY_DSN: str = ""  # Empty string = disabled
SENTRY_ENVIRONMENT: str = "production"
SENTRY_TRACES_SAMPLE_RATE: float = 0.1
```

**Environment variables:**
- `SENTRY_DSN`: Your Sentry project DSN (leave empty to disable)
- `SENTRY_ENVIRONMENT`: production, staging, or development
- `SENTRY_TRACES_SAMPLE_RATE`: 0.0 to 1.0 (percentage of traces to sample)

### 3. FastAPI Integration (`app/main.py`)

**Added initialization block:**
```python
if settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        release="1.0.0",
        integrations=[FastApiIntegration()],
    )
```

**Added test endpoint:**
```python
@app.get("/api/health/sentry-test")
async def sentry_test():
    """Trigger test error for Sentry (debug mode only)"""
```

**Behavior:**
- Only initializes if `SENTRY_DSN` is not empty
- Test endpoint returns 404 in production (`DEBUG=false`)
- All unhandled exceptions automatically captured

### 4. Celery Integration (`app/tasks/sync.py`)

**Added initialization block:**
```python
from app.config import get_settings

_settings = get_settings()
if _settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=_settings.SENTRY_DSN,
        environment=_settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=_settings.SENTRY_TRACES_SAMPLE_RATE,
        release="1.0.0",
        integrations=[CeleryIntegration()],
    )
```

**What it captures:**
- Task failures (sync errors, AI analysis errors)
- Task retries
- Task metadata (name, args, retries)

### 5. Tests (`tests/test_sentry_integration.py`)

**Added comprehensive test suite:**

```python
def test_sentry_not_initialized_without_dsn()
def test_sentry_initialized_with_dsn()
def test_sentry_test_endpoint_disabled_in_production()
def test_sentry_test_endpoint_no_dsn()
def test_sentry_test_endpoint_triggers_error()
def test_celery_sentry_initialization()
def test_celery_sentry_not_initialized_without_dsn()
```

**Run tests:**
```bash
pytest tests/test_sentry_integration.py -v
```

### 6. Documentation

**Created:**
- `docs/backend/SENTRY_INTEGRATION.md` - Full technical documentation
- `SENTRY_SETUP.md` - Quick setup guide for developers

## Backwards Compatibility

✅ **100% backwards compatible**

- Default `SENTRY_DSN = ""` → Sentry disabled
- No changes required to existing `.env` files
- Application works exactly as before when Sentry is not configured
- No performance overhead when disabled

## Usage

### Disable Sentry (Default)

```bash
# .env
SENTRY_DSN=""  # Empty or omitted
```

Application runs normally, no errors sent to Sentry.

### Enable Sentry

```bash
# .env
SENTRY_DSN="https://your-dsn@sentry.io/project-id"
SENTRY_ENVIRONMENT="production"
SENTRY_TRACES_SAMPLE_RATE=0.1
```

All errors automatically captured and sent to Sentry dashboard.

## Testing

### Local Testing

```bash
# 1. Install dependencies
cd apps/chat-center/backend
source venv/bin/activate
pip install -r requirements.txt

# 2. Run tests
pytest tests/test_sentry_integration.py -v

# 3. Test endpoint (debug mode)
DEBUG=true uvicorn app.main:app --reload
curl http://localhost:8001/api/health/sentry-test
```

### Production Deployment

```bash
# 1. SSH to VPS
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164

# 2. Install dependencies
cd /opt/agentiq/apps/chat-center/backend
source venv/bin/activate
pip install -r requirements.txt

# 3. Configure .env (optional)
nano .env
# Add: SENTRY_DSN="..." or leave empty

# 4. Restart services
sudo systemctl restart agentiq-chat
sudo systemctl restart agentiq-celery
sudo systemctl restart agentiq-celery-beat

# 5. Verify
sudo journalctl -u agentiq-chat -n 50 | grep -i sentry
```

## Error Categories Captured

### FastAPI Endpoints
- HTTP 500 errors
- Database connection failures
- Authentication failures
- Validation errors
- Rate limit errors

### Celery Tasks
- `sync_seller_chats` failures (WB API auth, network errors)
- `sync_seller_interactions` failures (WBCON API errors)
- `analyze_chat_with_ai` failures (DeepSeek API timeouts)
- `send_message_to_marketplace` failures (moderation, network)

## Security

- **Automatic scrubbing**: Passwords, tokens, API keys masked
- **Test endpoint**: Only accessible in DEBUG mode
- **Environment filtering**: Separate production/staging/dev errors
- **Privacy**: No PII sent to Sentry by default

## Performance Impact

**When disabled (`SENTRY_DSN=""`):**
- Zero overhead (import skipped)

**When enabled:**
- Minimal overhead (~1-2ms per request)
- Trace sampling reduces cost (10% by default)
- Async error reporting (non-blocking)

## Cost Optimization

Sentry free tier includes:
- 5,000 errors/month
- 10,000 transactions/month

To stay within limits:
1. Lower `SENTRY_TRACES_SAMPLE_RATE` (0.05 = 5%)
2. Filter noisy errors (custom `before_send`)
3. Use error grouping (automatic in Sentry)

## Next Steps

1. ✅ Merge this PR
2. 🔄 Deploy to staging (test with real errors)
3. 📊 Monitor Sentry dashboard for 1 week
4. 🚀 Deploy to production
5. 📈 Set up alerts for critical errors

## References

- Full docs: `docs/backend/SENTRY_INTEGRATION.md`
- Setup guide: `SENTRY_SETUP.md`
- Tests: `tests/test_sentry_integration.py`
- Sentry Python SDK: https://docs.sentry.io/platforms/python/
