# Pilot QA Report

- Generated: 2026-02-16 15:06:04 UTC
- API: `http://localhost:8001/api`
- Seller: `pilot.qa.20260216.codex@example.com`
- Safe mode: `True`

## Run Summary

- Decision: `go`
- Go/No-Go: `GO`
- Checks: total=8, pass=8, warn=0, fail=0
- Blockers: `none`

## Matrix Steps

- [PASS] `auth_register` Register: Пользователь зарегистрирован
- [PASS] `connect_marketplace` Connect WB API key: WB ключ подключен
- [PASS] `sync_now` Trigger /auth/sync-now: queued=chats,interactions
- [PASS] `sync_poll` Poll /auth/me during sync: sync finished with status=success
- [PASS] `sync_review` Sync review: fetched=121 created=0 updated=121
- [PASS] `sync_question` Sync question: fetched=125 created=0 updated=125
- [PASS] `sync_chat` Sync chat: fetched=39 created=0 updated=39
- [PASS] `list_review` List review: interaction_id=9191
- [PASS] `list_question` List question: interaction_id=10466
- [PASS] `list_chat` List chat: interaction_id=10569
- [PASS] `draft_review` AI draft review: source=cache
- [SKIP] `reply_review` Reply review: Пропущено (safe mode, без --send-replies)
- [PASS] `draft_question` AI draft question: source=llm
- [SKIP] `reply_question` Reply question: Пропущено (safe mode, без --send-replies)
- [PASS] `draft_chat` AI draft chat: source=llm
- [SKIP] `reply_chat` Reply chat: Пропущено (safe mode, без --send-replies)
- [PASS] `timeline` Deterministic timeline: scope=product steps=1
- [PASS] `ops_alerts` Ops alerts: alerts=0
- [PASS] `pilot_readiness` Pilot readiness: decision=go, pass=8, warn=0, fail=0

## Selected Interactions

- `review`: id=9191, external_id=UBA2makS3AIYT2BWMhJg, status=responded, needs_response=False
- `question`: id=10466, external_id=j25dmZgBXdRCGubiYvza, status=responded, needs_response=False
- `chat`: id=10569, external_id=1:2afade85-5391-5123-f7e7-eb6fb3b22251, status=open, needs_response=True

## Pilot Readiness Checks

- [PASS] `sync_freshness` (blocker=False): Последний sync 0 мин назад.
- [PASS] `channel_coverage` (blocker=False): Есть данные по обязательным каналам: review, question.
- [PASS] `channel_coverage_recommended` (blocker=False): Есть данные по рекомендованным каналам: chat
- [PASS] `question_sla_overdue` (blocker=False): Просроченных вопросов: 0.
- [PASS] `quality_manual_rate` (blocker=False): Manual rate 0.0%.
- [PASS] `quality_regression` (blocker=False): Регрессия quality не обнаружена.
- [PASS] `open_backlog` (blocker=False): Открытый backlog 17.
- [PASS] `reply_activity` (blocker=False): Нет reply_sent через dispatcher, но в source есть 178 отвеченных обращений за 30 дн.

## Ops Alerts Snapshot

- Alerts count: `0`
