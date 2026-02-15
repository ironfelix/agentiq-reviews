# Sentry Error Tracking Integration

## Overview

AgentIQ Chat Center integrates with [Sentry](https://sentry.io) for production error tracking and monitoring. Sentry is **optional** and the application works without it if no DSN is configured.

## Features

- **FastAPI Integration**: Automatic error tracking for all API endpoints
- **Celery Integration**: Error tracking for background tasks (sync, AI analysis, etc.)
- **Performance Monitoring**: Trace sampling for performance insights
- **Optional**: Application runs normally when Sentry is disabled (empty DSN)
- **Test Endpoint**: `/api/health/sentry-test` for testing error capture (debug mode only)

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Sentry Error Tracking (optional)
SENTRY_DSN=""  # Leave empty to disable, or set to your Sentry DSN
SENTRY_ENVIRONMENT="production"  # production, staging, development
SENTRY_TRACES_SAMPLE_RATE=0.1  # 0.0 to 1.0 (10% of transactions sampled)
```

### Getting Your Sentry DSN

1. Create a free account at [sentry.io](https://sentry.io)
2. Create a new project (select "FastAPI" or "Python")
3. Copy the DSN from project settings
4. Add it to your `.env` file:

```bash
SENTRY_DSN="https://examplePublicKey@o0.ingest.sentry.io/0"
```

## Usage

### Basic Setup

The integration initializes automatically on app startup. No code changes needed.

**Without Sentry** (DSN empty):
```bash
# .env
SENTRY_DSN=""
```
- Application runs normally
- No errors sent to Sentry
- No performance overhead

**With Sentry** (DSN configured):
```bash
# .env
SENTRY_DSN="https://..."
SENTRY_ENVIRONMENT="production"
```
- All unhandled errors automatically captured
- Background task errors tracked
- Performance traces sampled (10% by default)

### Environments

Set `SENTRY_ENVIRONMENT` to match your deployment:

| Environment | Description | Use Case |
|-------------|-------------|----------|
| `production` | Live production server | VPS at agentiq.ru |
| `staging` | Pre-production testing | Staging/QA server |
| `development` | Local development | Localhost |

### Trace Sampling

`SENTRY_TRACES_SAMPLE_RATE` controls performance monitoring:

| Rate | Description | Use Case |
|------|-------------|----------|
| `0.0` | No traces | Errors only, no performance data |
| `0.1` | 10% sampled | Recommended for production |
| `0.5` | 50% sampled | Staging/high-volume testing |
| `1.0` | All traces | Development only (expensive) |

## Testing

### Manual Test (Debug Mode)

The `/api/health/sentry-test` endpoint triggers a test error:

```bash
# Enable debug mode
DEBUG=true

# Trigger test error
curl http://localhost:8001/api/health/sentry-test
```

**Response when Sentry is enabled:**
```json
{
  "detail": "Test error triggered: Sentry test error - this is intentional for testing error tracking"
}
```

Check your Sentry dashboard for the captured error.

**Response when Sentry is disabled:**
```json
{
  "status": "sentry_disabled",
  "message": "Sentry is not configured (SENTRY_DSN is empty)"
}
```

**Note:** This endpoint returns 404 when `DEBUG=false` (production safety).

### Automated Tests

Run the test suite:

```bash
cd apps/chat-center/backend
source venv/bin/activate
pytest tests/test_sentry_integration.py -v
```

**Tests verify:**
- ✅ Sentry not initialized when DSN is empty
- ✅ Sentry initialized correctly when DSN is provided
- ✅ FastAPI integration enabled
- ✅ Celery integration enabled
- ✅ Test endpoint blocked in production
- ✅ Test endpoint works in debug mode

## Architecture

### FastAPI Integration

Located in: `apps/chat-center/backend/app/main.py`

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

**What it captures:**
- Unhandled exceptions in endpoints
- HTTP request metadata (method, path, status)
- User context (if authenticated)
- Request/response payloads (sanitized)

### Celery Integration

Located in: `apps/chat-center/backend/app/tasks/sync.py`

```python
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
- Task retry attempts
- Task metadata (task name, args, retries)
- Performance traces for long-running tasks

## Production Deployment

### VPS Setup

1. **Install dependencies**:
   ```bash
   cd /opt/agentiq/apps/chat-center/backend
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   # /opt/agentiq/apps/chat-center/backend/.env
   SENTRY_DSN="https://YOUR_DSN@sentry.io/YOUR_PROJECT"
   SENTRY_ENVIRONMENT="production"
   SENTRY_TRACES_SAMPLE_RATE=0.1
   ```

3. **Restart services**:
   ```bash
   sudo systemctl restart agentiq-chat       # FastAPI
   sudo systemctl restart agentiq-celery     # Celery worker
   sudo systemctl restart agentiq-celery-beat # Celery scheduler
   ```

4. **Verify initialization**:
   ```bash
   sudo journalctl -u agentiq-chat -f | grep -i sentry
   # Should show: "Sentry initialized for environment: production"

   sudo journalctl -u agentiq-celery -f | grep -i sentry
   # Should show: "Sentry initialized for Celery tasks (env: production)"
   ```

### Monitoring

Check your Sentry dashboard at `https://sentry.io/organizations/YOUR_ORG/issues/`

**Common errors to watch:**
- `sync_seller_chats` failures (WB API auth errors)
- `analyze_chat_with_ai` failures (DeepSeek API timeouts)
- Database connection errors
- Rate limit errors

## Privacy & Security

### Data Sanitization

Sentry automatically sanitizes sensitive data:

- **Passwords**: Removed from request bodies
- **API tokens**: Masked in headers
- **Personal data**: User emails/names redacted

### Custom Scrubbing

To add custom data scrubbing, edit `main.py`:

```python
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    before_send=scrub_sensitive_data,  # Custom function
)

def scrub_sensitive_data(event, hint):
    # Remove sensitive keys
    if 'request' in event:
        if 'headers' in event['request']:
            event['request']['headers'].pop('Authorization', None)
    return event
```

## Troubleshooting

### Sentry Not Capturing Errors

**Check initialization:**
```bash
sudo journalctl -u agentiq-chat -n 50 | grep -i sentry
```

**Expected output:**
```
Sentry initialized for environment: production
```

**If missing:**
1. Verify `SENTRY_DSN` is set in `.env`
2. Restart service: `sudo systemctl restart agentiq-chat`
3. Check for import errors: `python -m app.main`

### Test Endpoint Returns 404

**Reason:** `DEBUG=false` in production (security feature)

**Solution:**
```bash
# Enable debug mode temporarily
DEBUG=true python -m uvicorn app.main:app --port 8001

# Test endpoint
curl http://localhost:8001/api/health/sentry-test
```

### Celery Tasks Not Captured

**Check worker logs:**
```bash
sudo journalctl -u agentiq-celery -n 100 | grep -i sentry
```

**Expected output:**
```
Sentry initialized for Celery tasks (env: production)
```

**If missing:**
1. Verify `SENTRY_DSN` in `.env`
2. Restart worker: `sudo systemctl restart agentiq-celery`

## Cost Optimization

Sentry has volume-based pricing. To reduce costs:

1. **Lower trace sample rate**:
   ```bash
   SENTRY_TRACES_SAMPLE_RATE=0.05  # 5% instead of 10%
   ```

2. **Filter noisy errors**:
   ```python
   sentry_sdk.init(
       before_send=lambda event, hint: None if is_noisy_error(event) else event
   )
   ```

3. **Use error grouping**: Sentry groups similar errors automatically

4. **Set up alerts**: Get notified for critical errors only

## Resources

- [Sentry Python SDK Docs](https://docs.sentry.io/platforms/python/)
- [FastAPI Integration](https://docs.sentry.io/platforms/python/integrations/fastapi/)
- [Celery Integration](https://docs.sentry.io/platforms/python/integrations/celery/)
- [Performance Monitoring](https://docs.sentry.io/product/performance/)

## Changelog

### MVP-003 (2024-02-15)
- Initial Sentry integration
- FastAPI error tracking
- Celery background task tracking
- Test endpoint for error capture
- Optional configuration (disabled by default)
