# Development & Deployment Process

Last updated: 2026-02-15
Status: ACTIVE

## Overview

This document describes the development workflow, testing strategy, and deployment process for AgentIQ.

## Development Workflow

### Before writing code
1. Read relevant docs (see CLAUDE.md for required reading)
2. Understand the existing code structure
3. Plan the approach for non-trivial changes

### While writing code
1. Follow the design system (docs/design-system/)
2. Write backend tests for new services/endpoints
3. Check TypeScript types: `cd frontend && npx tsc --noEmit`
4. Run backend tests: `cd backend && source venv/bin/activate && pytest -v`

### Before deploying
Run the pre-deploy check:
```bash
./scripts/pre-deploy-check.sh
```

This runs:
- TypeScript type checking (catches type errors)
- Frontend build (catches build errors)
- Backend pytest suite (catches logic errors)

## Testing Strategy

### Test Pyramid

| Layer | Tool | What it catches | When to run |
|-------|------|-----------------|-------------|
| **Unit tests** (465) | pytest | Backend logic, API contracts, services | Every change |
| **E2E tests** (37) | Playwright | Frontend rendering, mobile layout, UX flows, performance | Before deploy |
| **Smoke test** (16 checks) | bash/curl | Prod health, SSL, endpoints, response times | After every deploy |

### Running tests

```bash
# Backend unit tests
cd apps/chat-center/backend
source venv/bin/activate
pytest -v                      # All tests
pytest -v -k "test_auth"       # By name
pytest --cov=app               # With coverage

# Frontend E2E tests
cd apps/chat-center/frontend
npm run test:e2e               # All (desktop + mobile)
npm run test:e2e:mobile        # Mobile only
npm run test:e2e:prod          # Against production
npm run test:e2e:headed        # With visible browser

# Prod smoke test
./scripts/ops/smoke-test.sh https://agentiq.ru
```

### What each test layer catches

**Unit tests** catch:
- API endpoint contracts (auth, validation, response format)
- Business logic (SLA prioritization, auto-responses, guardrails)
- Service integrations (WB connector, AI analyzer, product cache)
- Data models and schemas

**E2E tests** catch:
- Mobile layout issues (horizontal scroll, touch targets)
- UI state management (dot colors, badge counts, filter persistence)
- Navigation flows (mobile panel switching, back buttons)
- Performance regressions (load times, API call counts)
- Visual rendering (elements visible/hidden correctly)

**Smoke test** catches:
- Deployment failures (services not starting)
- SSL certificate expiry
- Endpoint availability
- Response time degradation
- Auth guard regressions

### What tests DON'T catch (and what to do)
- **AI prompt quality** -> Manual review of AI responses quarterly
- **Real data edge cases** -> Monitor Sentry for production errors
- **Cross-browser issues** -> Add Firefox/Safari to Playwright projects
- **Load/stress** -> Run load tests before scaling events

## Deployment

### Standard deploy (with checks + rollback)
```bash
./scripts/deploy.sh
```

This runs:
1. Pre-deploy checks (TypeScript + tests)
2. Frontend build
3. Backend packaging
4. **Backup current prod** (for rollback)
5. Deploy backend + frontend
6. Install new dependencies
7. Restart services
8. **Smoke test**
9. If smoke test fails -> **automatic rollback**

### Quick deploy (skip checks)
```bash
./scripts/deploy.sh --skip-checks
```

### Deploy without running tests
```bash
./scripts/deploy.sh --skip-tests
```

### Manual rollback
If you need to rollback manually:
```bash
SSH="ssh -i ~/Downloads/ubuntu-STD3-2-4-20GB-snQXiBJ3_Ilyin.pem ubuntu@79.137.175.164"
# Find the backup
$SSH "ls -la /tmp/agentiq-backup-*.tar.gz"
# Restore
$SSH "cd /opt/agentiq && sudo tar xzf /tmp/agentiq-backup-YYYYMMDD-HHMMSS.tar.gz --overwrite"
$SSH "sudo systemctl restart agentiq-api agentiq-celery agentiq-celery-beat"
```

## Monitoring

### Health checks
- **API**: https://agentiq.ru/api/health
- **Celery**: https://agentiq.ru/api/interactions/health/celery
- **SSL**: checked by cron daily at 06:00

### Error tracking
- **Sentry**: captures runtime exceptions (Python backend)
- Review errors weekly, fix P0 within 24h

### Cron jobs on VPS
| Job | Schedule | Script |
|-----|----------|--------|
| DB backup | Daily 03:00 | `/opt/agentiq/scripts/ops/db-backup.sh` |
| SSL check | Daily 06:00 | `/opt/agentiq/scripts/ops/ssl-check.sh` |
| Celery health | Every 5 min | `/opt/agentiq/scripts/ops/celery-check.sh` |
| certbot renew | 2x/day | `/usr/bin/certbot renew` |

## Future Improvements (Roadmap)

### Phase 1: Post-pilot (March 2026)
- [ ] GitHub Actions CI/CD (auto-run tests on push)
- [ ] Staging environment (staging.agentiq.ru)

### Phase 2: Growth (Q2 2026)
- [ ] Visual regression tests (Percy/Playwright screenshots)
- [ ] Load testing automation (k6 or locust)
- [ ] Uptime monitoring with Telegram alerts
- [ ] Database migration automation (Alembic in CI)

### Phase 3: Scale (Q3 2026)
- [ ] Docker containerization
- [ ] Blue-green deployments
- [ ] Feature flags
- [ ] Performance monitoring (Grafana + Prometheus)
