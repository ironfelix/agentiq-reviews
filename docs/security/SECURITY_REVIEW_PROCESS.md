# AgentIQ — Security Review Process

> **Last updated:** 2026-02-15
> **Status:** Active
> **Owner:** Engineering team

Этот документ описывает процесс security review, который должен выполняться при каждом релизе и на регулярной основе. Основан на OWASP ASVS (Application Security Verification Standard) и мировых практиках (Google, Stripe, GitLab).

---

## 1. Security Review в цикле разработки

### Когда проводить

| Триггер | Тип ревью | Кто делает |
|---------|-----------|------------|
| Каждый PR в `main` | Automated checks (CI) | CI pipeline |
| Изменения в auth/crypto/permissions | Manual code review | Lead + security checklist |
| Новый API endpoint | Threat model (5 min) | Developer |
| Изменения в `.env`, config, deploy scripts | Secrets check | Reviewer |
| Перед релизом (deploy на prod) | Pre-deploy checklist | Lead |
| Ежеквартально | Full security audit | External / automated |
| После инцидента | Post-mortem + targeted audit | Team |

---

## 2. CI Pipeline: Automated Security Checks

### 2.1. Static Analysis (SAST)

Запускать на каждый PR:

```bash
# Python backend — bandit (security linter)
pip install bandit
bandit -r apps/chat-center/backend/app/ -f json -o bandit-report.json
# Fail on HIGH/CRITICAL
bandit -r apps/chat-center/backend/app/ -ll  # --severity-level LOW=ignore

# Python dependencies — pip-audit
pip install pip-audit
pip-audit -r apps/chat-center/backend/requirements.txt

# JavaScript frontend — npm audit
cd apps/chat-center/frontend
npm audit --production
```

### 2.2. Secrets Detection

```bash
# gitleaks — detect secrets in code and git history
# Install: brew install gitleaks
gitleaks detect --source . --report-format json --report-path gitleaks-report.json

# trufflehog — deep history scan
# Install: brew install trufflehog
trufflehog filesystem --directory . --only-verified
```

### 2.3. Dependency Check

```bash
# Python
pip-audit -r requirements.txt --fix --dry-run

# JavaScript
npm audit fix --dry-run
```

### 2.4. GitHub Actions (рекомендуемый workflow)

```yaml
# .github/workflows/security.yml
name: Security Checks
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run bandit (Python SAST)
        run: |
          pip install bandit
          bandit -r apps/chat-center/backend/app/ -ll -f json -o bandit.json
        continue-on-error: true

      - name: Run pip-audit
        run: |
          pip install pip-audit
          pip-audit -r apps/chat-center/backend/requirements.txt

      - name: Run npm audit
        run: |
          cd apps/chat-center/frontend
          npm audit --production --audit-level=high

      - name: Run gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## 3. Pre-Deploy Checklist

Перед каждым деплоем на prod проверить:

### Secrets & Config
- [ ] `.env` файлы НЕ в git (`git status` чисто, `.gitignore` актуален)
- [ ] `SECRET_KEY` не является дефолтным значением
- [ ] `DEBUG=false` в production
- [ ] `ENCRYPTION_KEY` актуален и не скомпрометирован
- [ ] Все API токены (WB, DeepSeek) валидны и не истекли

### Auth & Access
- [ ] Новые endpoints защищены `Depends(get_current_seller)`
- [ ] Нет `get_optional_seller` на state-changing endpoints
- [ ] Rate limiting активен на auth endpoints
- [ ] CORS origins — только production домены

### Input Validation
- [ ] Все новые Pydantic модели имеют `max_length`, `ge`, `le` constraints
- [ ] Нет raw SQL queries (только SQLAlchemy ORM)
- [ ] Нет `f"...{user_input}..."` в SQL-подобных выражениях

### Infrastructure
- [ ] nginx security headers присутствуют (HSTS, CSP, X-Frame-Options)
- [ ] `/api/metrics` заблокирован для внешних IP
- [ ] SSL сертификат валиден (не истекает в ближайшие 30 дней)
- [ ] Celery worker не запускается от root

### Dependencies
- [ ] `pip-audit` не нашёл HIGH/CRITICAL уязвимостей
- [ ] `npm audit` не нашёл HIGH/CRITICAL уязвимостей

---

## 4. Manual Code Review: Security Checklist

При ревью PR с изменениями в auth/crypto/permissions:

### Authentication
- [ ] Пароли хэшируются через bcrypt (не MD5/SHA)
- [ ] JWT подписывается безопасным ключом (≥32 символа)
- [ ] Token expiration разумный (≤30 min для access token)
- [ ] Нет hardcoded credentials в коде

### Authorization (IDOR)
- [ ] Каждый endpoint проверяет `seller_id == current_seller.id`
- [ ] Нет доступа к чужим чатам/сообщениям/настройкам
- [ ] Pagination не позволяет enumerate все записи

### Input Handling
- [ ] Все входные данные валидированы через Pydantic
- [ ] Нет `eval()`, `exec()`, `pickle.loads()` с пользовательским вводом
- [ ] LIKE-запросы экранируют `%` и `_`

### Error Handling
- [ ] Ошибки НЕ возвращают stack traces клиенту
- [ ] Ошибки НЕ содержат internal paths, DB schema, secrets
- [ ] Broad `except Exception` оправдан и логируется

### Crypto
- [ ] Encryption keys из env vars, не из кода
- [ ] Нет самодельной криптографии
- [ ] Timing-safe сравнение для tokens/hashes

---

## 5. Threat Modeling (5-min для каждого нового endpoint)

При добавлении нового API endpoint, ответь на 5 вопросов:

1. **Кто может вызвать?** (authenticated seller / anonymous / internal service)
2. **Что произойдёт если вызовет злоумышленник?** (data leak / state change / cost)
3. **Какие данные возвращаются?** (PII / secrets / internal state)
4. **Нужен ли rate limit?** (auth endpoints, expensive operations — да)
5. **Нужен ли audit log?** (state changes, credential operations — да)

Записать ответы в docstring endpoint:

```python
@router.post("/chats/{chat_id}/reply")
async def reply_to_chat(chat_id: int, ...):
    """Send reply to customer.

    Security: auth required, seller_id check, rate limit 10/min,
    audit logged, text max 5000 chars.
    """
```

---

## 6. Secrets Rotation Schedule

| Secret | Ротация | Как |
|--------|---------|-----|
| `SECRET_KEY` (JWT signing) | Каждые 6 месяцев | Generate + update .env + restart |
| `ENCRYPTION_KEY` (Fernet) | При компрометации | Generate + re-encrypt all seller keys |
| WB API tokens | При истечении / компрометации | Regenerate в ЛК WB |
| DeepSeek API key | Каждые 6 месяцев | Dashboard → Rotate |
| SSH keys (VPS) | Каждые 12 месяцев | Generate new → update authorized_keys |
| DB password | Каждые 6 месяцев | ALTER ROLE + update .env + restart |
| SSL certificate | Auto (Let's Encrypt) | certbot auto-renewal |

### Процедура ротации SECRET_KEY:

```bash
# 1. Generate new key
NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

# 2. Update on VPS
ssh $VPS "echo SECRET_KEY=$NEW_KEY >> /opt/agentiq/.env.new"

# 3. Restart services (existing tokens invalidated — users re-login)
ssh $VPS "sudo systemctl restart agentiq-chat agentiq-celery agentiq-celery-beat"
```

---

## 7. Incident Response

### При обнаружении уязвимости:

1. **Assess** (5 min) — severity, blast radius, active exploitation?
2. **Contain** (15 min) — disable affected endpoint, revoke tokens, block IP
3. **Fix** (varies) — patch code, deploy hotfix
4. **Notify** — affected users if data leaked
5. **Post-mortem** — document in `docs/security/incidents/YYYY-MM-DD-title.md`

### Contacts
- Engineering lead: (определить)
- VPS access: SSH key holders
- WB API: через ЛК WB
- Domain/SSL: hosting provider

---

## 8. Compliance Checklist (Quarterly)

Каждый квартал проверять:

- [ ] Все findings из последнего аудита закрыты
- [ ] Secrets ротированы по расписанию
- [ ] Dependencies обновлены (`pip-audit`, `npm audit`)
- [ ] Backup шифрование работает и восстановление протестировано
- [ ] Access logs проверены на аномалии
- [ ] Неиспользуемые аккаунты/токены отозваны

---

## 9. Полезные инструменты

| Инструмент | Назначение | Команда |
|------------|-----------|---------|
| **bandit** | Python SAST | `bandit -r app/ -ll` |
| **pip-audit** | Python dependency CVEs | `pip-audit -r requirements.txt` |
| **npm audit** | JS dependency CVEs | `npm audit --production` |
| **gitleaks** | Secrets in git | `gitleaks detect --source .` |
| **trufflehog** | Deep secret scan | `trufflehog filesystem --directory .` |
| **semgrep** | Multi-lang SAST | `semgrep --config=p/security-audit .` |
| **OWASP ZAP** | Dynamic scanning (DAST) | GUI / CLI against staging |
| **nikto** | Web server scanner | `nikto -h https://agentiq.ru` |
| **testssl.sh** | SSL/TLS config check | `testssl.sh https://agentiq.ru` |

---

## 10. References

- [OWASP ASVS v4.0](https://owasp.org/www-project-application-security-verification-standard/) — Application Security Verification Standard
- [OWASP Top 10 (2021)](https://owasp.org/www-project-top-ten/) — Most Critical Web Security Risks
- [Google Security Review Process](https://cloud.google.com/docs/security/overview) — Design reviews, threat modeling
- [GitLab Security Development Lifecycle](https://about.gitlab.com/handbook/security/) — SAST, DAST, dependency scanning
- [Stripe Security Practices](https://stripe.com/docs/security) — PCI compliance, secrets management
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks) — Server hardening (nginx, PostgreSQL, Ubuntu)
