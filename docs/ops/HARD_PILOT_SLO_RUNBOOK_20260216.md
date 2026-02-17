# Hard Pilot SLO/p95 Runbook

**Date:** 2026-02-16  
**Owner:** Codex (GPT-5.3-Codex, docs-only фиксация)  
**Scope:** `agentiq.ru/app` + `agentiq.ru/api` (WB-first pilot)

## 1. Цель

Перед hard pilot закрепить единые операционные пороги (SLO/p95), чтобы Go/No-Go и инциденты оценивались по одним правилам.

## 2. SLO Targets (hard pilot baseline)

| Metric | Target | Alert |
|---|---|---|
| API uptime (30d) | `>= 99.5%` | `< 99.5%` = P1 |
| API 5xx rate (15m window) | `<= 1.0%` | `> 1.0%` = P1 |
| `GET /api/interactions` latency p95 | `<= 800ms` | `> 1200ms` = P2 |
| `GET /api/interactions/metrics/ops-alerts` latency p95 | `<= 600ms` | `> 1000ms` = P2 |
| `POST /api/auth/sync-now` latency p95 (enqueue) | `<= 1500ms` | `> 2500ms` = P2 |
| `POST /api/interactions/{id}/ai-draft` latency p95 | `<= 15s` | `> 25s` = P2 |
| Sync freshness (`pilot-readiness`) | `<= 30 min` | `> 30 min` = P1 |
| Sync success rate (`ops-alerts`) | `>= 99%` | `< 99%` = P1 |
| Overdue questions (`pilot-readiness`) | `= 0` | `> 0` = P1 |

## 3. Источники истины

1. `GET /api/interactions/metrics/pilot-readiness`
2. `GET /api/interactions/metrics/ops-alerts`
3. HTTP/Nginx access logs + backend service logs (`journalctl`)
4. Smoke checks из `apps/chat-center/backend/scripts/ops/smoke-test.sh`

## 4. Alerting Policy

1. `P1` (blocker): uptime/5xx/sync freshness/sync success/overdue questions.
2. `P2` (degradation): p95 latency хуже порога без полного падения.
3. `GO` на pilot разрешён только при отсутствии активных `P1`.

## 5. Операционный чек перед pilot (каждый запуск)

1. Проверить `pilot-readiness` и убедиться, что blocker-checks не в `fail`.
2. Проверить `ops-alerts` на отсутствие активных критических алертов.
3. Прогнать safe QA matrix (`run_pilot_qa_matrix.py`) и сохранить отчёт в `docs/product/reports/`.
4. Зафиксировать результат в `docs/product/MVP_READINESS_STATUS.md` и backlog execution history.

## 6. Действия при нарушении порогов

1. `P1`: freeze релиза, перевести поток в assist-only при риске auto-action, открыть incident запись.
2. `P2`: не блокировать работу, но открыть task с owner и ETA; повторный замер в течение 24 часов.
3. После восстановления: повторный safe QA matrix, затем обновление статусов в продуктовых docs.

## 7. Связанные документы

- `docs/product/PILOT_QA_MATRIX_AND_GONOGO_CHECKLIST.md`
- `docs/product/MVP_READINESS_STATUS.md`
- `docs/product/HARD_PILOT_STABILIZATION_LOG_20260216.md`
