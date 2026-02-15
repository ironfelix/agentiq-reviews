# Sentry Integration - Quick Setup Guide

## Local Development

### 1. Install Dependencies

```bash
cd apps/chat-center/backend
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure (Optional)

Add to `.env` (or leave empty to disable):

```bash
# Sentry Error Tracking (optional - leave empty to disable)
SENTRY_DSN=""
SENTRY_ENVIRONMENT="development"
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### 3. Get Sentry DSN (Optional)

If you want to enable error tracking:

1. Sign up at [sentry.io](https://sentry.io) (free tier available)
2. Create new project → select "Python/FastAPI"
3. Copy DSN from project settings
4. Add to `.env`:
   ```bash
   SENTRY_DSN="https://your-dsn@sentry.io/project-id"
   ```

### 4. Test Locally

```bash
# Start backend
uvicorn app.main:app --reload --port 8001

# Check logs
# Should see: "Sentry initialized" (if DSN set) OR "Sentry disabled" (if empty)

# Test endpoint (debug mode only)
DEBUG=true uvicorn app.main:app --reload --port 8001
curl http://localhost:8001/api/health/sentry-test
```

## Production Deployment (VPS)

### 1. Install Dependencies

```bash
ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164

cd /opt/agentiq/apps/chat-center/backend
source venv/bin/activate
pip install sentry-sdk[fastapi]==2.22.0
```

### 2. Configure Environment

```bash
# Edit .env
nano /opt/agentiq/apps/chat-center/backend/.env

# Add Sentry config (or leave empty to disable):
SENTRY_DSN=""  # Set to your DSN or leave empty
SENTRY_ENVIRONMENT="production"
SENTRY_TRACES_SAMPLE_RATE=0.1
```

### 3. Restart Services

```bash
# Restart FastAPI
sudo systemctl restart agentiq-chat

# Restart Celery workers
sudo systemctl restart agentiq-celery
sudo systemctl restart agentiq-celery-beat
```

### 4. Verify

```bash
# Check FastAPI logs
sudo journalctl -u agentiq-chat -n 50 | grep -i sentry
# Expected: "Sentry initialized for environment: production" OR "Sentry disabled"

# Check Celery logs
sudo journalctl -u agentiq-celery -n 50 | grep -i sentry
# Expected: "Sentry initialized for Celery tasks" OR (nothing if disabled)
```

## Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `SENTRY_DSN` | `""` (disabled) | Your Sentry project DSN. Leave empty to disable Sentry entirely. |
| `SENTRY_ENVIRONMENT` | `"production"` | Environment name (production, staging, development) |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.1` | Percentage of transactions to trace (0.0-1.0). 0.1 = 10% |

## Test Endpoint

**Only available in DEBUG mode** (security feature):

```bash
# Local testing
DEBUG=true uvicorn app.main:app --reload
curl http://localhost:8001/api/health/sentry-test

# Returns 500 with test error (check Sentry dashboard)
```

**Production:** Returns 404 (endpoint disabled for safety)

## Running Tests

```bash
cd apps/chat-center/backend
source venv/bin/activate
pytest tests/test_sentry_integration.py -v
```

## Key Features

- ✅ **Optional**: Works without Sentry if DSN is empty
- ✅ **FastAPI**: Automatic error tracking for all endpoints
- ✅ **Celery**: Background task error tracking
- ✅ **Performance**: Trace sampling for monitoring
- ✅ **Safe**: Test endpoint blocked in production
- ✅ **Zero config**: Sensible defaults

## Full Documentation

See [docs/backend/SENTRY_INTEGRATION.md](/docs/backend/SENTRY_INTEGRATION.md) for:
- Detailed architecture
- Privacy & security
- Troubleshooting
- Cost optimization
- Custom configuration

## Support

- Sentry Docs: https://docs.sentry.io/platforms/python/
- FastAPI Integration: https://docs.sentry.io/platforms/python/integrations/fastapi/
- Celery Integration: https://docs.sentry.io/platforms/python/integrations/celery/
