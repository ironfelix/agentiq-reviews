# AgentIQ MVP2 — API

Base URL: `https://app.agentiq.ru`

## Аутентификация

Все API-эндпоинты (кроме health и auth callback) требуют JWT cookie `session_token`.

Cookie устанавливается автоматически при Telegram Login.

---

## Pages (HTML)

### `GET /`
Landing page с Telegram Login Widget.

### `GET /invite`
Страница ввода инвайт-кода (после первого Telegram Login).

### `GET /dashboard`
Dashboard с задачами пользователя. Требует auth.

### `GET /dashboard/report/{task_id}`
Отчёт «Анализ товара» (report.html). Требует auth + владелец задачи.

### `GET /dashboard/report/{task_id}/communication`
Отчёт «Анализ ответов» (comm-report.html). Требует auth + владелец задачи.

---

## Auth API

### `GET /api/auth/telegram/callback`
Telegram Login Widget callback. Создаёт/обновляет пользователя, устанавливает JWT cookie.

**Query params:** `id`, `first_name`, `last_name`, `username`, `photo_url`, `auth_date`, `hash`

**Response:** 302 redirect → `/invite` (новый) или `/dashboard` (повторный)

### `POST /api/auth/verify-invite`
Проверка и активация инвайт-кода.

**Body:**
```json
{"code": "BETA-2026-A3F7"}
```

**Response:**
```json
{"message": "Invite code accepted"}
```

**Errors:**
- `400` — неверный код или исчерпан лимит
- `401` — не авторизован

### `POST /api/auth/logout`
Удаляет session cookie.

**Response:**
```json
{"message": "Logged out"}
```

---

## Tasks API

### `POST /api/tasks/create`
Создать новую задачу анализа.

**Body:**
```json
{"article_id": 282955222}
```

**Response:**
```json
{
  "id": 1,
  "article_id": 282955222,
  "status": "pending",
  "progress": 0,
  "created_at": "2026-02-07T10:00:00",
  "completed_at": null,
  "error_message": null
}
```

### `GET /api/tasks/list`
Список задач текущего пользователя (последние 50).

**Response:** `TaskResponse[]`

### `GET /api/tasks/{task_id}/status`
Статус конкретной задачи.

**Response:** `TaskResponse`

### `DELETE /api/tasks/{task_id}`
Удалить задачу + отчёт + уведомления.

**Response:**
```json
{"message": "Task deleted"}
```

### `GET /api/tasks/{task_id}/report`
Получить данные отчёта как JSON.

**Response:**
```json
{
  "id": 1,
  "task_id": 1,
  "article_id": 282955222,
  "category": "flashlight",
  "rating": 4.3,
  "feedback_count": 145,
  "target_variant": "серый",
  "data": { ... },
  "created_at": "2026-02-07T10:05:00"
}
```

---

## PDF Export

### `GET /api/reports/{task_id}/pdf?type=product|communication`
Генерация и скачивание PDF.

**Query params:**
- `type` — `product` (по умолчанию) или `communication`

**Response:** PDF file (`application/pdf`)

**Filename:** `agentiq-{type}-{article_id}.pdf`

---

## Health

### `GET /health`
Health check (без авторизации).

**Response:**
```json
{"status": "ok", "version": "mvp2"}
```

---

## Статусы задач

| Status | Описание |
|--------|---------|
| `pending` | В очереди, ожидает обработки |
| `processing` | WBCON собирает отзывы / идёт анализ |
| `completed` | Отчёт готов |
| `failed` | Ошибка (см. `error_message`) |

## Прогресс задачи

| Progress | Этап |
|----------|------|
| 0-10% | Создание |
| 10-20% | WBCON: создание задачи |
| 20-50% | WBCON: ожидание сбора отзывов |
| 50-70% | Скачивание отзывов |
| 70-90% | LLM-анализ |
| 90-100% | Сохранение + уведомление |
