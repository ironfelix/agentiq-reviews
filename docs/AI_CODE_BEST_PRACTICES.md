# AI Code Development — Best Practices

Как максимально приблизить AI-разработку к качеству команды разработчиков.

**Цель:** минимизировать техдолг, улучшить maintainability, упростить рефакторинг.

---

## Проблемы AI-разработки

### 1. Техдолг накапливается быстро
- AI пишет код «на лету» без глубокого понимания архитектуры
- Copy-paste между похожими компонентами
- Дублирование логики
- Inconsistent naming conventions

### 2. Отсутствие peer review
- Нет второго мнения на архитектурные решения
- Security issues могут пройти незамеченными
- Best practices не всегда соблюдаются

### 3. Testing coverage низкий
- AI не пишет тесты proactively (если не попросишь)
- Manual testing = slow feedback loop
- Regression bugs

### 4. Documentation отстаёт
- AI генерит код быстрее чем обновляет docs
- Specs устаревают
- Onboarding новых devs сложен

---

## Best Practices (проверенные на AgentIQ)

### 1. Spec-Driven Development (КРИТИЧНО!)

**До написания кода:**
1. Напиши спеку в `docs/specs/` (используй `TEMPLATE_FEATURE_SPEC.md`)
2. Опиши: API contract, data models, edge cases, security considerations
3. Дай AI спеку → он пишет код по спеке
4. После кода → обнови спеку с реальным implementation

**Пример:**
```markdown
# Spec: Leads API

## API Contract
POST /api/leads
Request: { nm: string, contact: string, company?: string }
Response: { id: number, created_at: datetime }

## Validation Rules
- nm: digits only, 5-15 chars
- contact: min 2 chars, any format accepted
- Auto-add @ if looks like telegram username

## Security
- Rate limit: 10 req/min per IP
- No auth required (public endpoint)
- SQL injection: use parameterized queries

## Edge Cases
- Duplicate (same nm+contact): return 409
- Invalid contact format: return 422 with details
```

**Результат:** AI пишет код который соответствует спеке, меньше переделок.

---

### 2. Code Review Checklist (после каждого PR)

**Используй этот чеклист ВСЕГДА:**

#### Security
- [ ] SQL injection защита (parameterized queries)
- [ ] XSS protection (sanitize user input)
- [ ] Auth/authz проверки (JWT validation)
- [ ] Secrets не в коде (env variables)
- [ ] CORS настроен правильно
- [ ] Rate limiting на public endpoints

#### Architecture
- [ ] Separation of concerns (models / services / API layers)
- [ ] DRY principle (no copy-paste)
- [ ] Single responsibility (каждая функция делает одно)
- [ ] Consistent naming (users vs user_list vs getUsers)
- [ ] Error handling везде (try/catch, logging)

#### Performance
- [ ] DB queries оптимизированы (indexes, N+1 avoided)
- [ ] Caching где нужно (Redis для frequent queries)
- [ ] Pagination для больших списков
- [ ] Async/await правильно (no blocking operations)

#### Testing
- [ ] Unit tests для бизнес-логики
- [ ] Integration tests для API endpoints
- [ ] Edge cases покрыты (empty input, invalid data)
- [ ] Error paths тоже тестируются

#### Documentation
- [ ] Docstrings для functions
- [ ] API docs обновлены (FastAPI auto-gen + manual)
- [ ] Спеки актуальны
- [ ] CHANGELOG.md обновлён

---

### 3. Refactoring Sprints (каждые 2 недели)

**Проблема:** код пишется быстро, но становится messy.

**Решение:** выделяй 20% времени на рефакторинг.

**Рефакторинг чеклист:**
1. **Extract duplicated code** → utils/helpers
2. **Rename inconsistent variables** (user vs users vs user_list)
3. **Split large files** (>500 lines → split)
4. **Add type hints** (Python: всегда используй typing)
5. **Remove dead code** (unused imports, functions)
6. **Update docs** (README, specs)

**Как делать с AI:**
```
"Найди дублирующийся код в api/ и вынеси в общие helpers.
Переименуй inconsistent variables для единого стиля.
Обнови docstrings для всех functions."
```

---

### 4. Architectural Reviews (до больших фич)

**Когда:** перед началом новой большой фичи (биллинг, webhooks, analytics).

**Как:**
1. Напиши design doc (1-2 страницы):
   - Problem statement
   - Proposed solution
   - Alternatives considered
   - Tradeoffs (pros/cons)
   - Migration plan (если breaking changes)
2. Покажи AI → попроси critique
3. Обсуди с GPT-4 / o1 (architectural review)
4. Итерируй до consensus

**Пример design doc:**
```markdown
# Design: Billing System

## Problem
Need subscription management (trial, paid, cancelled).

## Proposed Solution
- Use Stripe for payments
- Table: subscriptions (user_id, stripe_subscription_id, status, plan)
- Webhook: /api/webhooks/stripe (handle subscription.updated)
- Middleware: check subscription status before API calls

## Alternatives
1. Build custom billing → too complex, reinventing wheel
2. Paddle → less flexible than Stripe
3. Manual invoicing → doesn't scale

## Tradeoffs
Pros: battle-tested, PCI compliance, webhooks
Cons: Stripe fees (2.9% + $0.30), vendor lock-in

## Migration Plan
1. Add subscriptions table
2. Add Stripe integration
3. Add middleware (soft launch: log only)
4. Enable enforcement after 1 week testing
```

---

### 5. Testing Strategy (Pyramid)

```
        /\
       /E2E\         ← 10% (critical flows only)
      /------\
     /  API   \      ← 30% (all endpoints)
    /----------\
   /   Unit     \    ← 60% (business logic)
  /--------------\
```

**Unit tests (60%):**
- Все services, helpers, utils
- Fast (milliseconds)
- No DB, no external APIs

**API tests (30%):**
- All endpoints (happy path + errors)
- Use test DB (in-memory or separate)
- Mock external APIs (WB, DeepSeek)

**E2E tests (10%):**
- Critical user flows only:
  - Login → connect WB → view chats → send reply
  - Register → trial → upgrade to paid
- Slow (seconds), run before deploy only

**Как попросить AI:**
```
"Напиши unit tests для services/ai_analyzer.py.
Покрой все edge cases: empty input, invalid data, API timeout.
Используй pytest fixtures для mock data."
```

---

### 6. Continuous Integration (GitHub Actions)

**Автоматизируй всё:**

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Lint
        run: ruff check app/
      - name: Type check
        run: mypy app/
```

**CI должен проверять:**
- ✅ Tests pass (pytest)
- ✅ Linting (ruff / pylint)
- ✅ Type checking (mypy)
- ✅ Security scan (bandit / safety)
- ✅ Coverage >80% (pytest-cov)

**Результат:** нельзя merge код если CI failed.

---

### 7. Code Quality Tools (автоматизация)

**Backend (Python):**
- **Linter:** `ruff` (faster than flake8)
- **Formatter:** `black` (consistent style)
- **Type checker:** `mypy` (catch type errors)
- **Security:** `bandit` (find security issues)

**Frontend (TypeScript):**
- **Linter:** `eslint` (with typescript-eslint)
- **Formatter:** `prettier`
- **Type checker:** `tsc --noEmit`

**Git hooks (pre-commit):**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff
        args: [--fix]
  - repo: https://github.com/psf/black
    hooks:
      - id: black
```

**Результат:** код автоформатится и линтится до commit, меньше "style debates".

---

### 8. Documentation as Code

**Все docs рядом с кодом:**

```
agentiq/
├── apps/chat-center/backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── leads.py
│   │   │   └── leads_spec.md        ← спека рядом с кодом
│   │   ├── services/
│   │   │   ├── ai_analyzer.py
│   │   │   └── ai_analyzer_spec.md
│   └── README.md                    ← quickstart
├── docs/
│   ├── specs/                       ← глобальные спеки
│   ├── architecture/                ← архитектура
│   └── api/                         ← API docs
```

**Auto-generate где можно:**
- OpenAPI spec (FastAPI → auto-generated)
- DB schema (SQLAlchemy → ERD diagram tools)
- Type definitions (TypeScript → typedoc)

**Обновляй при каждом PR:**
- [ ] Спека обновлена
- [ ] API docs обновлены
- [ ] CHANGELOG.md += новая запись

---

### 9. Monitoring & Observability

**Не только для production, но и для development:**

**Metrics (Prometheus):**
- Request count (by endpoint, status)
- Response time (p50, p95, p99)
- Error rate (5xx)
- DB query time

**Logs (structured):**
```python
import structlog
logger = structlog.get_logger()

logger.info("lead_created", lead_id=lead.id, nm=lead.nm)
```

**Alerts (production):**
- Error rate >5% → email/Slack
- Response time p95 >2s → warning
- DB connections >80% → critical

**Результат:** видишь проблемы до того как пользователи пожалуются.

---

### 10. Security First (не откладывай на потом)

**Security checklist для каждой фичи:**

#### Authentication & Authorization
- [ ] JWT tokens secure (strong secret, expiration)
- [ ] Password hashing (bcrypt, not MD5)
- [ ] RBAC если нужно (roles, permissions)
- [ ] Session management (logout invalidates token)

#### Input Validation
- [ ] SQL injection защита (ORM parameterized queries)
- [ ] XSS protection (sanitize HTML)
- [ ] CSRF protection (если stateful)
- [ ] File upload validation (size, type, content)

#### Secrets Management
- [ ] API keys в env vars, НЕ в коде
- [ ] Encryption keys rotated (quarterly)
- [ ] DB passwords strong (generated, not "password123")
- [ ] .env в .gitignore

#### Rate Limiting
- [ ] Public endpoints limited (10-100 req/min)
- [ ] Login attempts limited (5 failures → lockout)
- [ ] API keys per-user limits

**Tools:**
- `bandit` (static analysis)
- `safety` (dependency vulnerabilities)
- OWASP ZAP (penetration testing)

---

### 11. Deployment Automation

**Problem:** manual deployment = errors, downtime.

**Solution:** CI/CD pipeline.

**Pipeline stages:**
1. **Test** (GitHub Actions)
   - Run tests
   - Lint & type check
   - Security scan
2. **Build** (if pass)
   - Docker image build
   - Tag with git SHA
3. **Deploy to Staging** (auto)
   - Deploy to staging server
   - Run smoke tests
   - Notify on Slack
4. **Deploy to Production** (manual approval)
   - Human clicks "Deploy to prod"
   - Blue-green deployment (zero downtime)
   - Rollback if errors

**Результат:** deploy за 5 минут, не 2 часа ручной работы.

---

### 12. Tech Debt Tracking

**Не накапливай, трекай:**

**TODO comments в коде:**
```python
# TODO: Add retry logic for WB API timeouts (Tech Debt #42)
# FIXME: This is O(n²), need to optimize (Tech Debt #43)
# HACK: Temporary workaround, remove after WB fixes API (Tech Debt #44)
```

**Tech Debt issues (GitHub):**
- Label: `tech-debt`
- Priority: P0 (critical) → P3 (nice-to-have)
- Link to code (file:line)

**Sprint planning:**
- 20% времени на tech debt (каждый спринт)
- P0/P1 debt блокирует новые фичи

**Результат:** tech debt не копится до "rewrite from scratch".

---

## Процесс разработки с AI (итоговый workflow)

### Phase 1: Planning (ВСЕГДА перед кодом)
1. **Напиши спеку** (`docs/specs/FEATURE_NAME.md`)
   - API contract, data models, edge cases, security
2. **Design review** (с AI или GPT-4)
   - Alternatives, tradeoffs, migration plan
3. **Approve** → можно писать код

### Phase 2: Development
1. **Дай AI спеку** → он пишет код
2. **Code review** (используй checklist выше)
3. **Напиши тесты** (или попроси AI написать)
4. **Run tests locally** → fix до green
5. **Update docs** (спека, CHANGELOG)

### Phase 3: Pre-commit
1. **Run linters** (ruff, black, mypy)
2. **Run tests** (`pytest --cov`)
3. **Git commit** (conventional commits: `feat:`, `fix:`, `refactor:`)

### Phase 4: CI/CD
1. **Push to GitHub** → CI runs (tests, lint, security)
2. **If pass** → auto-deploy to staging
3. **Manual testing** на staging
4. **If OK** → deploy to production (manual approval)

### Phase 5: Monitoring
1. **Check metrics** (errors, latency)
2. **Check logs** (any exceptions?)
3. **User feedback** → backlog

---

## Metrics для оценки качества кода

### Code Quality Score (0-100)
```
Score =
  Test Coverage (0-40 pts) +
  Linter Pass (0-20 pts) +
  Type Coverage (0-20 pts) +
  Documentation (0-10 pts) +
  Security Score (0-10 pts)
```

**Target:** >80 для production code.

### Tech Debt Ratio
```
Tech Debt Ratio =
  (Time to fix all P0/P1 tech debt) /
  (Time to build current features)
```

**Target:** <20% (здоровый проект)
**Alert:** >50% (опасная зона, нужен рефакторинг)

---

## Tools Recommendations

### Backend (Python)
- **Framework:** FastAPI (async, type hints, auto docs)
- **ORM:** SQLAlchemy 2.0 (async, type-safe)
- **Testing:** pytest + pytest-cov + pytest-asyncio
- **Linting:** ruff (all-in-one: flake8 + isort + pyupgrade)
- **Formatting:** black
- **Type checking:** mypy --strict
- **Security:** bandit + safety

### Frontend (TypeScript)
- **Framework:** React 18 + TypeScript
- **Build:** Vite (fast, modern)
- **Linting:** eslint + typescript-eslint
- **Formatting:** prettier
- **Testing:** vitest (like jest but faster)
- **Type checking:** tsc --noEmit

### Infrastructure
- **CI/CD:** GitHub Actions (simple, free for OSS)
- **Monitoring:** Prometheus + Grafana (self-hosted)
- **Logging:** structlog (structured logs)
- **Errors:** Sentry (error tracking)

---

## Real Example: AgentIQ Refactoring Plan

### Current State (Feb 2026)
- ⚠️ Test coverage: ~20% (low)
- ⚠️ Type hints: ~60% (medium)
- ⚠️ Documentation: ~70% (good but outdated)
- ⚠️ Tech debt: ~15 P0/P1 issues

### Refactoring Sprints (Next 4 weeks)

**Week 1: Testing**
- [ ] Add pytest setup
- [ ] Write unit tests for services/ (target: 80% coverage)
- [ ] Write API tests for all endpoints
- [ ] Add CI/CD (GitHub Actions)

**Week 2: Code Quality**
- [ ] Setup ruff + black + mypy
- [ ] Fix all linter errors
- [ ] Add type hints to all functions
- [ ] Remove dead code (unused imports, functions)

**Week 3: Architecture**
- [ ] Extract duplicated code → utils/
- [ ] Split large files (>500 lines)
- [ ] Consistent naming (rename inconsistent vars)
- [ ] Add docstrings everywhere

**Week 4: Documentation**
- [ ] Update all specs (match current implementation)
- [ ] Write missing API docs
- [ ] Update architecture diagrams
- [ ] Write deployment runbook

**Result:** production-ready code, easy to scale with team.

---

## Conclusion

**AI-разработка может быть качественной если:**
1. ✅ Используешь Spec-Driven Development (спеки перед кодом)
2. ✅ Делаешь code review по чеклисту (каждый PR)
3. ✅ Пишешь тесты (unit + API + E2E)
4. ✅ Автоматизируешь (CI/CD, linters, formatters)
5. ✅ Выделяешь 20% времени на рефакторинг
6. ✅ Трекаешь tech debt (не накапливаешь)
7. ✅ Документируешь всё (specs, API, architecture)

**Разница между AI-кодом и team-кодом сокращается до минимума.**

**Следующий шаг:** выбери 2-3 practice из списка и внедри на этой неделе.

---

**Создано:** 2026-02-16
**Основано на:** AgentIQ MVP experience (7 дней AI-разработки)
**Автор:** Claude Sonnet 4.5 + Ivan (founder feedback)
