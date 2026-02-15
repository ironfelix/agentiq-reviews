# Pilot QA Matrix + Go/No-Go Checklist (WB-first)

**Дата:** February 12, 2026  
**Контур:** `apps/chat-center` unified interactions (`review + question + chat`)

## 1. Цель

Перед `Pilot Demo / Go-NoGo (February 19, 2026)` выполнить одинаковый и проверяемый прогон:

1. `sync -> draft -> reply` по каждому каналу.
2. Проверка guardrails и timeline-переиспользования.
3. Формальный `GO/NO-GO` по endpoint `GET /api/interactions/metrics/pilot-readiness`.

## 2. Entry Conditions

1. Backend regression: green (`interactions_* + linking_policy`).
2. Frontend build: `npm run build` green.
3. Seller подключен к WB API, есть валидный `api_key`.
4. Есть данные минимум в `review/question/chat`.

## 3. Pilot QA Matrix (ручной прогон)

| Канал | Шаг | Ожидаемый результат | Статус |
|---|---|---|---|
| review | `POST /api/auth/sync-now` + `GET /api/interactions?channel=review` | Новые/обновленные обращения появились | [ ] |
| review | `POST /api/interactions/{id}/ai-draft` | Черновик сгенерирован, событие в quality учитывается | [ ] |
| review | `POST /api/interactions/{id}/reply` | Ответ отправлен, статус `responded` | [ ] |
| question | sync + list | Появились вопросы, приоритет/SLA заполнены | [ ] |
| question | ai-draft | Черновик учитывает intent/SLA | [ ] |
| question | reply | Ответ отправлен в WB, `needs_response=false` | [ ] |
| chat | sync + list | Появились chat-interactions | [ ] |
| chat | ai-draft | Черновик сгенерирован | [ ] |
| chat | reply | Outgoing message отправлен в WB | [ ] |
| timeline | `GET /api/interactions/{id}/timeline` | Есть шаги thread + `action_mode`/`policy_reason` | [ ] |
| guardrails | probabilistic link case | Только `assist_only`, без auto-actions | [ ] |
| ops alerts | `GET /api/interactions/metrics/ops-alerts` | SLA/quality алерты читаются без ошибок | [ ] |

### Автоматизированный прогон (рекомендуется)

Скрипт:
`apps/chat-center/backend/scripts/run_pilot_qa_matrix.py`

Safe-run (без отправки live ответов):

```bash
cd apps/chat-center/backend
./venv/bin/python scripts/run_pilot_qa_matrix.py \
  --base-url http://localhost:8001/api \
  --email pilot@example.com \
  --password 'your-password' \
  --register-if-needed \
  --connect-if-needed \
  --api-key "$WB_API_KEY"
```

Live-run (с отправкой ответов в каналы, только для контролируемого пилота):

```bash
cd apps/chat-center/backend
./venv/bin/python scripts/run_pilot_qa_matrix.py \
  --base-url http://localhost:8001/api \
  --email pilot@example.com \
  --password 'your-password' \
  --send-replies \
  --yes-live-replies \
  --reply-channels chat \
  --interaction-id-chat <interaction_id> \
  --max-replies 1
```

Результат: markdown-отчет пишется в  
`docs/product/reports/pilot-qa-report-<timestamp>.md`.

Примечание: ответы в `review/question` публичные. Для них требуются отдельные флаги
`--allow-public-replies`, явные `--interaction-id-review/--interaction-id-question` и `--reply-text`.

## 4. Формальный Go/No-Go

Источник истины: `GET /api/interactions/metrics/pilot-readiness`

Пороговые значения (текущие дефолты):

1. `max_sync_age_minutes = 30`
2. `max_overdue_questions = 0`
3. `max_manual_rate = 0.6`
4. `max_open_backlog = 250`
5. `required_channels = review/question`
6. `recommended_channels = chat`

Правило решения:

1. `GO`: нет blocker-checks со статусом `fail`.
2. `NO-GO`: есть хотя бы один blocker `fail`.
3. `warn` не блокирует запуск, но требует зафиксированного owner/action.

## 5. Blocker Checklist (должно быть закрыто перед GO)

1. `sync_status/sync_freshness` не в `fail`.
2. `channel_coverage` не в `fail` (обязательные каналы `review/question` присутствуют).
3. `question_sla_overdue` не в `fail`.

## 6. Non-Blocker Follow-ups (после GO, но с дедлайном)

1. `quality_manual_rate` = `warn` -> план снижения доли manual.
2. `quality_regression` = `warn` -> анализ и корректировка prompt/guardrails.
3. `open_backlog` = `warn` -> приоритизация и ресурсный план.
4. `reply_activity` = `warn` -> донабор baseline-данных.
5. `channel_coverage_recommended` = `warn` -> проверить наличие реальных chat-cases и корректность chat sync потока.

## 8. Последний живой прогон

1. `February 12, 2026` (safe-mode, без live reply):
 - отчет: `docs/product/reports/pilot-qa-report-20260212-175510.md`
 - результат: `GO`
 - предупреждения: `reply_activity`

## 7. Rollback Conditions

Немедленный rollback пилота, если:

1. Массовые сбои sync (`sync_status=error` устойчиво > 15 минут).
2. Ошибки отправки ответов в production канале WB.
3. Обнаружен случай некорректного авто-действия по probabilistic link.

Rollback шаги:

1. Отключить авто-поток действий (оставить assist-only).
2. Включить ручной режим ответов по проблемному каналу.
3. Зафиксировать инцидент и повторить прогон матрицы после фикса.
