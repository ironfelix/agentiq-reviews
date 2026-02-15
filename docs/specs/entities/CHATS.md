# Entity Spec: Chats

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Goal / Non-goals
- Goal: определить единый контракт "Chat" для UI и AI-логики, независимо от маркетплейса.
- Non-goals: описывать конкретные экраны UI (это в `docs/prototypes/...`).

## 2) Domain Model (нормализованная модель)
MUST:
- Chat имеет стабильный `chat_id` (внутренний) и ссылку на marketplace + external ids.
- Chat содержит сообщения (`messages`) с автором, временем, текстом и метаданными.

## 3) Lifecycle / Status
MUST:
- Статусы чата и правила переходов должны быть описаны явно в одном месте (истина).

Related docs/code (ссылки для заполнения):
- `docs/chat-center/CHAT_PRIORITIZATION_PLAN.md`
- `_recalculate_chat_status()` (упоминается в `CLAUDE.md`, найти в `sync.py`)

## 4) SLA Priority
MUST:
- SLA priority вычисляется по правилам, завязанным на intent и тип взаимодействия.
- UI-группировка не должна зависеть от `unread_count` (есть правило в `CLAUDE.md`).

## 5) AI Analysis / Drafting
MUST:
- AI анализ и draft-ответы на чат должны подчиняться guardrails для чатов.
Spec:
- `../guardrails/CHAT_RESPONSES.md`
- `../guardrails/AI_DRAFTS.md`

## 6) Marketplace Variants
MUST:
- Указать для каждого маркетплейса capabilities: можно ли закрывать чат, можно ли редактировать ответ, лимиты/таймауты, типы событий.
Spec:
- `../marketplaces/CONTRACT.md`
- `../marketplaces/WILDBERRIES.md`
- `../marketplaces/OZON.md`

## 7) Acceptance Criteria (минимум)
1. Для чата всегда можно построить timeline из сообщений в строгом порядке времени.
2. Статус и SLA priority воспроизводимы (детерминированы) на одном и том же входе.
3. AI draft не нарушает guardrails (banned phrases, PII, unsafe actions).

## 8) Tests
- Unit: правила статуса/SLA/интентов (детерминизм, edge cases).
- Integration: sync pipeline с заглушенным marketplace adapter.

