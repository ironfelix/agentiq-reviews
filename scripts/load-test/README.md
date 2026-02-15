# AgentIQ Load Testing

Load testing suite for the Chat Center backend API using [Locust](https://locust.io/).

## Overview

This load test simulates realistic user behavior against the AgentIQ API:

- **List operations (60%)**: Browsing interactions/chats
- **Detail operations (20%)**: Viewing individual items
- **Analytics (15%)**: Quality metrics, ops alerts
- **Write operations (5%)**: AI drafts, syncing data

## Installation

```bash
# Install locust
pip install locust

# Or add to requirements.txt
echo "locust==2.20.0" >> requirements.txt
pip install -r requirements.txt
```

## Setup

### 1. Create Test User

You need an authenticated user for load testing. Create one via:

```bash
# Option A: Register via API
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "loadtest@agentiq.ru",
    "password": "loadtest123",
    "name": "Load Test User",
    "marketplace": "wildberries"
  }'

# Option B: Use existing demo user
# (if you already have a test account)
```

### 2. Set Environment Variables

```bash
export LOAD_TEST_EMAIL="loadtest@agentiq.ru"
export LOAD_TEST_PASSWORD="loadtest123"
```

Or create a `.env.loadtest` file:

```bash
# .env.loadtest
LOAD_TEST_EMAIL=loadtest@agentiq.ru
LOAD_TEST_PASSWORD=loadtest123
```

Then load it:

```bash
source .env.loadtest  # or: export $(cat .env.loadtest | xargs)
```

## Running Tests

### Interactive Mode (Web UI)

Best for exploratory testing and real-time monitoring:

```bash
cd scripts/load-test
locust -f locustfile.py --host=http://localhost:8001
```

Then open http://localhost:8089 in your browser and configure:

- **Number of users**: 100
- **Spawn rate**: 10 users/second
- **Host**: http://localhost:8001

### Headless Mode (CI/CD)

For automated testing without Web UI:

```bash
# Local backend
locust -f locustfile.py \
  --host=http://localhost:8001 \
  --users=100 \
  --spawn-rate=10 \
  --run-time=5m \
  --headless

# Staging server
locust -f locustfile.py \
  --host=https://agentiq.ru/api \
  --users=50 \
  --spawn-rate=5 \
  --run-time=3m \
  --headless
```

### Quick Script (Recommended)

Use the provided shell script for automated tests:

```bash
./run-load-test.sh

# Or with custom settings
./run-load-test.sh --users=50 --duration=3m
```

## Performance Targets

### Excellent
- **p95 latency**: < 500ms
- **Error rate**: < 1%
- **RPS**: > 50 requests/second (single-core backend)

### Acceptable
- **p95 latency**: < 1000ms
- **Error rate**: < 5%
- **RPS**: > 20 requests/second

### Critical (requires optimization)
- **p95 latency**: >= 1000ms
- **Error rate**: >= 5%

## Interpreting Results

### Sample Output

```
AgentIQ Load Test Finished
============================================================
Total Requests: 12,543
Total Failures: 23
Median Response Time: 245ms
95th Percentile: 678ms
99th Percentile: 1,234ms
Average Response Time: 312.45ms
Requests/sec: 41.81
Error Rate: 0.18%
============================================================
PERFORMANCE VALIDATION
============================================================
✓ p95 (678ms) < 1000ms - ACCEPTABLE
✓ Error rate (0.18%) < 1% - EXCELLENT
============================================================
FINAL RESULT: PASS
============================================================
```

### Common Issues

#### High p95 Latency (> 1000ms)

**Symptoms**: Slow response times, timeouts

**Possible causes**:
- Database queries without indexes
- N+1 queries (missing eager loading)
- Slow external API calls (WB, Ozon)
- Insufficient database connection pool

**Solutions**:
- Add database indexes: `CREATE INDEX idx_interactions_seller_occurred ON interactions(seller_id, occurred_at DESC);`
- Enable SQLAlchemy query logging: `echo=True` in engine config
- Cache expensive operations (quality metrics, product info)
- Increase connection pool: `pool_size=20, max_overflow=40`

#### High Error Rate (> 5%)

**Symptoms**: 500 errors, timeouts, authentication failures

**Possible causes**:
- JWT token expiration during test
- Database connection exhaustion
- Rate limiting on external APIs
- Memory leaks / resource exhaustion

**Solutions**:
- Increase JWT token expiration: `ACCESS_TOKEN_EXPIRE_MINUTES = 120`
- Monitor database connections: `SELECT count(*) FROM pg_stat_activity;`
- Add retry logic for external API calls
- Profile memory usage: `tracemalloc`, `memory_profiler`

#### Low RPS (< 20 req/sec)

**Symptoms**: Backend can't handle concurrent load

**Possible causes**:
- Blocking I/O operations (synchronous external calls)
- CPU-bound tasks in API handlers (AI analysis)
- Single-threaded bottlenecks

**Solutions**:
- Use async/await for all I/O operations
- Offload heavy tasks to Celery background workers
- Enable Uvicorn workers: `uvicorn app.main:app --workers=4`
- Use connection pooling for external APIs

## Advanced Usage

### Test Specific Endpoints

Edit `locustfile.py` and comment out tasks you don't want to test:

```python
# @task(20)  # Disable this task
# def list_interactions_all(self):
#     pass

@task(50)  # Increase weight for this task
def get_quality_metrics(self):
    pass
```

### Custom User Behavior

Create a custom user class for specific scenarios:

```python
class HeavyAnalyticsUser(HttpUser):
    """User that only requests analytics endpoints."""
    wait_time = between(5, 10)

    @task
    def quality_metrics(self):
        # ...
```

Run with:

```bash
locust -f locustfile.py --user-classes HeavyAnalyticsUser
```

### Distributed Load Testing

For testing with > 1000 concurrent users, use multiple workers:

```bash
# Master node
locust -f locustfile.py --master

# Worker nodes (run on separate machines or terminals)
locust -f locustfile.py --worker --master-host=127.0.0.1
locust -f locustfile.py --worker --master-host=127.0.0.1
locust -f locustfile.py --worker --master-host=127.0.0.1
```

### Monitoring During Tests

```bash
# Monitor backend logs
tail -f /var/log/agentiq/backend.log

# Monitor database queries (PostgreSQL)
psql agentiq_chat -c "SELECT pid, query_start, state, query FROM pg_stat_activity WHERE state != 'idle';"

# Monitor system resources
htop  # CPU, memory
iotop # Disk I/O
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Load Test

on:
  push:
    branches: [main, develop]

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install locust
      - name: Run load test
        env:
          LOAD_TEST_EMAIL: ${{ secrets.LOAD_TEST_EMAIL }}
          LOAD_TEST_PASSWORD: ${{ secrets.LOAD_TEST_PASSWORD }}
        run: |
          cd scripts/load-test
          ./run-load-test.sh --users=50 --duration=2m
```

## Best Practices

1. **Start small**: Begin with 10 users, then scale up
2. **Warm up period**: Let the system stabilize before measuring
3. **Realistic data**: Use production-like data volume in test DB
4. **Monitor resources**: Watch CPU, memory, database connections
5. **Isolate environment**: Don't run load tests against production
6. **Reproduce issues**: Re-run failed tests to confirm bottlenecks
7. **Document baselines**: Track performance over time (p95, RPS)

## Troubleshooting

### `ModuleNotFoundError: No module named 'locust'`

Install locust:

```bash
pip install locust
```

### `Login failed: LOAD_TEST_EMAIL and LOAD_TEST_PASSWORD must be set`

Set environment variables:

```bash
export LOAD_TEST_EMAIL="your-email@example.com"
export LOAD_TEST_PASSWORD="your-password"
```

### `Connection refused` errors

Ensure backend is running:

```bash
cd apps/chat-center/backend
uvicorn app.main:app --host=0.0.0.0 --port=8001
```

### Test exits immediately with 0 requests

Check that the test user has data to interact with (interactions, chats). If empty, load test will skip detail views and analytics.

Seed demo data:

```bash
# Via API
curl -X POST http://localhost:8001/api/auth/seed-demo \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Resources

- [Locust Documentation](https://docs.locust.io/)
- [Performance Testing Best Practices](https://martinfowler.com/articles/practical-test-pyramid.html#PerformanceTests)
- [AgentIQ Backend API Docs](../../apps/chat-center/backend/README.md)
