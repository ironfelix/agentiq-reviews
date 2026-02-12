# WBCON API v2 (2026) — Token-based Auth

**Base URL:** https://19-fb.wbcon.su
**Docs:** https://19-fb.wbcon.su/docs
**Token valid until:** 2026-03-10

## Authentication

Все запросы требуют заголовок:
```
token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Current token (expires 2026-03-10):**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyLCJleHAiOjE4MDE5NDU5MTR9.OHaWLN3umrgutFYv6DjY8XZ0MLgpsxKPAo7ZKTrYX2E
```

## Endpoints

### 1. POST /create_task_fb — Создать задачу на сбор отзывов

**Request:**
```bash
curl -X POST https://19-fb.wbcon.su/create_task_fb \
  -H "Content-Type: application/json" \
  -H "token: YOUR_TOKEN" \
  -d '{"article": 282955222}'
```

**Response:**
```json
{
  "task_id": "01-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

### 2. GET /task_status — Проверить статус задачи

**Request:**
```bash
curl https://19-fb.wbcon.su/task_status?task_id=01-xxxxx \
  -H "token: YOUR_TOKEN"
```

**Response:**
```json
{
  "task_id": "01-xxxxx",
  "is_ready": true,
  "status": "completed"
}
```

### 3. GET /get_results_fb — Получить отзывы

**Request:**
```bash
curl "https://19-fb.wbcon.su/get_results_fb?task_id=01-xxxxx&offset=0" \
  -H "token: YOUR_TOKEN"
```

**Response:**
```json
[
  {
    "feedback_count": 407,
    "rating": 4.5,
    "feedbacks": [
      {
        "fb_id": "12345",
        "valuation": 5,
        "fb_text": "Отличный фонарик!",
        "fb_created_at": "2026-01-15T10:30:00",
        "answer_text": "Спасибо за отзыв!",
        "answer_created_at": "2026-01-15T15:20:00",
        "color": "серый",
        "size": null
      }
    ]
  }
]
```

**Pagination:**
- `offset=0` — первые 100 отзывов
- `offset=100` — следующие 100 отзывов
- Продолжать пока `len(feedbacks) < 100`

## Изменения от старой версии (2025)

| Параметр | Старая версия | Новая версия (2026) |
|----------|---------------|---------------------|
| **Auth** | `email` + `password` в URL | Заголовок `token: ...` |
| **Base URL** | Custom env var `WBCON_FB_BASE` | Fixed `https://19-fb.wbcon.su` |
| **create_task** | `POST ...?email=...&password=...` | `POST ...` + header `token` |
| **task_status** | `GET ...?task_id=...&email=...&password=...` | `GET ...?task_id=...` + header `token` |
| **get_results** | `GET ...?task_id=...&offset=...&email=...&password=...` | `GET ...?task_id=...&offset=...` + header `token` |

## Bash Script Example

См. [`scripts/wbcon-reviews-fetch.sh`](../scripts/wbcon-reviews-fetch.sh)

```bash
export WBCON_TOKEN='eyJhbGciOi...'
./scripts/wbcon-reviews-fetch.sh 282955222 > reviews.json
```

## Python Example

```python
import requests
import time

TOKEN = "eyJhbGciOi..."
BASE = "https://19-fb.wbcon.su"
HEADERS = {"token": TOKEN}

# 1. Create task
resp = requests.post(
    f"{BASE}/create_task_fb",
    json={"article": 282955222},
    headers=HEADERS
)
task_id = resp.json()["task_id"]

# 2. Wait for ready
while True:
    status = requests.get(
        f"{BASE}/task_status",
        params={"task_id": task_id},
        headers=HEADERS
    ).json()
    if status.get("is_ready"):
        break
    time.sleep(5)

# 3. Fetch results (with pagination)
all_feedbacks = []
offset = 0
while True:
    data = requests.get(
        f"{BASE}/get_results_fb",
        params={"task_id": task_id, "offset": offset},
        headers=HEADERS
    ).json()

    feedbacks = data[0]["feedbacks"]
    all_feedbacks.extend(feedbacks)

    if len(feedbacks) < 100:
        break
    offset += 100
```

## Known Issues

1. **Pagination offset bug** — offset может возвращать дубликаты, используй deduplication по `fb_id`
2. **Token expiration** — токен действителен до 2026-03-10, после нужен новый

## Environment Variables

**Old (.env):**
```bash
WBCON_EMAIL=your@email.com
WBCON_PASS=yourpassword
WBCON_FB_BASE=https://old-api.wbcon.su
```

**New (.env):**
```bash
WBCON_TOKEN=eyJhbGciOi...
# No email/password needed anymore
```

## Migration Checklist

- [ ] Update `.env.example` with `WBCON_TOKEN` instead of `WBCON_EMAIL`/`WBCON_PASS`
- [ ] Update `scripts/wbcon-reviews-fetch.sh` (✅ done)
- [ ] Update `scripts/wbcon-questions-fetch.sh`
- [ ] Update `scripts/wbcon-images-fetch.sh`
- [ ] Update `apps/reviews/backend/tasks.py` (Celery worker)
- [ ] Update documentation
