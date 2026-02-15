# AgentIQ — Security Audit Report

> **Last updated:** 2026-02-15
> **Status:** Completed (automated code review + manual verification)
> **Scope:** Full project — backend, frontend, infrastructure, secrets, dependencies

---

## Executive Summary

| Severity | Count | Key Areas |
|----------|-------|-----------|
| CRITICAL | 6 | Exposed secrets, weak crypto defaults, CORS |
| HIGH | 10 | Auth weaknesses, missing headers, rate limiting |
| MEDIUM | 12 | IDOR risk, token management, audit gaps |
| LOW | 8 | Logging, headers, operational hygiene |
| **Total** | **36** | |

**Immediate risk:** Production secrets (WB tokens, Telegram bot token, DeepSeek API key, encryption key) are present in `.env` files in the repository. Even if `.gitignore` excludes them now, they may exist in git history.

**Positive findings:** SQLAlchemy ORM used correctly (no SQL injection), bcrypt for passwords, Fernet for credential encryption, Pydantic validation on most endpoints, seller isolation enforced, no XSS vectors in React (no `dangerouslySetInnerHTML`), no command injection, no `eval`/`exec`/`pickle`.

---

## CRITICAL (6)

### C-01. Exposed Production Secrets in .env Files
**Files:** `apps/chat-center/backend/.env`, `apps/chat-center/backend/.env.wb-tokens`, `apps/reviews/.env`

**Issue:** Multiple `.env` files contain live production credentials:
- WB API tokens (JWT, valid until 2026-08-05)
- Telegram bot token
- WBCON JWT token
- DeepSeek API key
- Fernet encryption key (`ENCRYPTION_KEY`)
- SECRET_KEY for JWT signing

**Impact:** Full access to WB marketplace operations, Telegram bot takeover, paid LLM API abuse, decryption of all stored seller credentials.

**Fix:**
1. Revoke all exposed tokens immediately (WB cabinet, Telegram, DeepSeek dashboard)
2. Generate new `SECRET_KEY` and `ENCRYPTION_KEY`
3. Re-encrypt seller credentials with new key
4. Remove from git history: `git filter-branch --force --index-filter 'git rm --cached --ignore-unmatch "*.env" "*.env.*"' -- --all`

---

### C-02. Weak Default SECRET_KEY
**File:** `app/config.py:18`
```python
SECRET_KEY: str = "change-me-in-production"
```

**Issue:** If `SECRET_KEY` env var is missing, JWT tokens are signed with a publicly known string. Attacker can forge valid tokens for any user.

**Fix:** Add startup validation:
```python
@app.on_event("startup")
async def validate_secrets():
    if settings.SECRET_KEY in ("change-me-in-production", "test-secret-key"):
        raise RuntimeError("FATAL: SECRET_KEY must be changed. Generate: python -c 'import secrets; print(secrets.token_urlsafe(48))'")
```

---

### C-03. Hardcoded Database Password
**File:** `app/config.py:12`
```python
DATABASE_URL: str = "postgresql://postgres:agentiq123@localhost:5432/agentiq_chat"
```

**Impact:** If `.env` is missing, app connects with weak known password.

**Fix:** Make `DATABASE_URL` required (no default), or fail on known-weak passwords.

---

### C-04. CORS Allows Wildcard Methods and Headers
**File:** `app/main.py:69-75`
```python
allow_methods=["*"],
allow_headers=["*"],
allow_credentials=True,
```

**Impact:** Combined with `allow_credentials=True`, allows cross-origin state-changing requests from any listed origin with any HTTP method.

**Fix:**
```python
allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
allow_headers=["Content-Type", "Authorization"],
```

---

### C-05. SSH Key Path and VPS IP in Deploy Scripts
**Files:** `scripts/deploy.sh:6`, `apps/chat-center/deploy.sh:68`

**Issue:** Deployment scripts contain hardcoded VPS IP (`79.137.175.164`), SSH key path (`~/Downloads/*.pem`), and deployment paths.

**Fix:** Move to `~/.ssh/` with 600 permissions. Use env vars or SSH config for host/key.

---

### C-06. Timezone-Naive Datetime in JWT
**File:** `app/services/auth.py:69, 71, 77, 116`
```python
expire = datetime.utcnow() + expires_delta  # naive
```

**Impact:** `datetime.utcnow()` returns timezone-naive datetime. If `token_data.exp` is parsed as timezone-aware, comparison raises `TypeError` — DoS vector.

**Fix:** Replace all `datetime.utcnow()` → `datetime.now(timezone.utc)`.

---

## HIGH (10)

### H-01. No Rate Limiting on Auth Endpoints
**File:** `app/api/auth.py:125-254`

No rate limiting on `/auth/login` and `/auth/register`. Enables brute force attacks.

**Fix:** Add `slowapi` limiter: 5 attempts/minute per IP on auth endpoints. Add exponential backoff.

---

### H-02. JWT Token Expiration 7 Days
**File:** `app/services/auth.py:28`
```python
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7
```

Industry standard: 15-30 min access token + refresh token pattern.

**Fix:** Reduce to 30 min, implement refresh token endpoint.

---

### H-03. Auth Token in localStorage (XSS Risk)
**File:** `frontend/src/services/api.ts:51-55`

localStorage is accessible to any JS running on the page. If XSS occurs, token is stolen.

**Fix (long-term):** Move to httpOnly cookie with `Secure` and `SameSite=Strict` flags.
**Mitigation (short-term):** Content Security Policy header prevents inline script execution.

---

### H-04. No CSRF Protection
**File:** `app/main.py` — no CSRF middleware

POST/PUT/DELETE endpoints accept requests without CSRF token. With `allow_credentials=True`, enables cross-site request forgery.

**Fix:** Since auth uses Bearer tokens (not cookies), CSRF risk is limited. If migrating to cookies, add CSRF middleware.

---

### H-05. Missing Security Headers
**Files:** `app/main.py`, `infra/deploy/nginx.conf`

Missing: `Strict-Transport-Security`, `Content-Security-Policy`, `X-XSS-Protection`, `Permissions-Policy`.

Present: `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.

**Fix:** Add to nginx:
```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://agentiq.ru" always;
```

---

### H-06. Prometheus Metrics Endpoint Exposed
**File:** `app/main.py:169-177`

`/api/metrics` serves Prometheus metrics without authentication. Exposes internal timing, request counts, system info.

**Fix:** Block in nginx:
```nginx
location /api/metrics { deny all; }
```

---

### H-07. Sentry Test Endpoint in Production
**File:** `app/main.py:180-204`

`/api/health/sentry-test` exists in production (returns 404 but confirms existence). Remove entirely.

---

### H-08. Weak Password Policy
**File:** `app/schemas/auth.py:8-14`

Only `min_length=8`. No uppercase, digit, special char requirements.

**Fix:** Add validator requiring 12+ chars, mixed case, digits.

---

### H-09. No Content-Length Limits on API Inputs
**Files:** `app/api/messages.py`, `app/api/interactions.py`

No `max_length` on message text fields. Multi-megabyte payloads possible.

**Fix:** Add `text: str = Field(..., max_length=5000)` on all text inputs.

---

### H-10. Docker Container Runs as Root
**File:** `apps/reviews/Dockerfile`

No `USER` directive. Container processes run as root.

**Fix:** Add `RUN useradd -m -u 1000 appuser && USER appuser`.

---

## MEDIUM (12)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| M-01 | IDOR: Optional auth on `GET /chats/{id}` | `chats.py:95` | Make auth required |
| M-02 | LIKE wildcard in search (ReDoS risk) | `chats.py:67`, `interactions.py:100` | Escape `%` and `_` |
| M-03 | No token revocation mechanism | `auth.py:162` | Add `jti` claim + blacklist |
| M-04 | Verbose error messages to client | `auth.py:378` | Return generic messages |
| M-05 | Celery task inputs not validated | `tasks/sync.py` | Validate seller_id ownership |
| M-06 | No audit logging | `api/auth.py`, `api/messages.py` | Add audit_log table |
| M-07 | Celery default pickle serialization | `tasks/__init__.py` | Set `task_serializer='json'` |
| M-08 | Database backup not encrypted | `scripts/ops/db-backup.sh` | Add GPG/openssl encryption |
| M-09 | No HTTPS redirect at app level | `main.py` | Add HSTS middleware |
| M-10 | Redis connection unencrypted | `config.py:15` | Use `rediss://` with auth |
| M-11 | HS256 JWT (symmetric) | `auth.py:27` | Consider RS256 (long-term) |
| M-12 | No password in .env.example | `.env.example:2` | Use placeholder, not real password |

---

## LOW (8)

| ID | Issue | File | Fix |
|----|-------|------|-----|
| L-01 | DB URL partially logged | `main.py:99` | Log only "Database initialized" |
| L-02 | Missing request context in error logs | `main.py:77-91` | Add seller_id, IP to logs |
| L-03 | SSH key in ~/Downloads/ | `deploy.sh:6` | Move to ~/.ssh/ |
| L-04 | No secrets rotation schedule | — | Document quarterly rotation |
| L-05 | No SECURITY.md for responsible disclosure | — | Create SECURITY.md |
| L-06 | DEBUG=true in dev .env | `.env:5` | Ensure false in prod |
| L-07 | No resource limits in Docker Compose | `docker-compose.yml` | Add CPU/memory limits |
| L-08 | Prometheus high-cardinality labels | `main.py:47` | Aggregate status codes |

---

## Verified Secure Practices

| Area | Status | Details |
|------|--------|---------|
| SQL Injection | **Safe** | SQLAlchemy ORM with parameterized queries throughout |
| XSS | **Safe** | React escapes all content, no `dangerouslySetInnerHTML` |
| Command Injection | **Safe** | No `subprocess`, `os.system`, `eval`, `exec` with user input |
| Password Hashing | **Safe** | bcrypt via passlib (update version recommended) |
| Credential Encryption | **Safe** | Fernet symmetric encryption for API keys |
| Seller Isolation | **Safe** | `require_seller_ownership()` on all endpoints |
| Dependencies | **Safe** | All packages recent, no known CVEs |
| Deserialization | **Safe** | No `pickle`, no `yaml.load` without SafeLoader |

---

## Action Plan

### Immediate (сегодня)
1. Revoke all exposed tokens (WB, Telegram, DeepSeek, WBCON)
2. Rotate `SECRET_KEY`, `ENCRYPTION_KEY`, DB password
3. Re-encrypt seller credentials
4. Add startup validation for SECRET_KEY
5. Remove `.env` files from git history

### Sprint 1 (1 неделя)
6. Fix `datetime.utcnow()` → `datetime.now(timezone.utc)` in auth.py
7. Restrict CORS methods/headers
8. Add rate limiting on auth endpoints
9. Add missing security headers in nginx
10. Add `max_length` on text inputs
11. Block `/api/metrics` in nginx
12. Remove sentry-test endpoint
13. Make auth required on `GET /chats/{id}`

### Sprint 2 (2 недели)
14. Implement refresh token pattern (reduce access token to 30 min)
15. Add audit logging table
16. Celery: switch to JSON serialization
17. Encrypt database backups
18. Strengthen password policy
19. Escape LIKE wildcards in search

### Long-term (1-2 месяца)
20. Migrate auth token from localStorage to httpOnly cookie
21. Consider RS256 for JWT
22. Implement token revocation with `jti` claims
23. Set up automated security scanning (bandit, pip-audit) in CI
24. Create incident response plan
25. Quarterly secrets rotation schedule
