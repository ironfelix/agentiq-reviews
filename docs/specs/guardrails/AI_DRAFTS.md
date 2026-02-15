# Guardrails Spec: AI Drafts & Replies (Common)

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Scope
Эта спека общая для всех типов interaction (чаты/вопросы/отзывы) и описывает:
- как формируется AI draft,
- как хранится audit trail,
- какие запреты действуют всегда.

## 2) Hard Rules (MUST / MUST NOT)
MUST:
- Все drafts и replies должны быть привязаны к `interaction_id` и `marketplace`.
- Должна быть трассировка: кто инициировал (user/system), время, модель/версия (если есть), входной контекст.
- Нельзя отправлять reply без применения guardrails (валидации).

MUST NOT:
- Логировать секреты/токены/PII.
- Делать "авто-действия" на основании низкой уверенности (если есть классификация/линковка identity).

## 3) Output Constraints
MUST:
- Draft должен быть детерминированно формализуемым (структурированный JSON или четкий текстовый формат),
  чтобы можно было валидировать и тестировать.

## 4) Audit Trail (минимум)
MUST:
- `draft_id`
- `interaction_id`
- `created_at`
- `created_by` (user_id / system)
- `policy_version` (версия guardrails/spec)
- `input_context_refs` (какие документы/факты использовали, без утечек секретов)

## 5) Acceptance Criteria
1. Любой отправленный reply имеет запись о примененных guardrails и policy_version.
2. Любой draft можно воспроизвести на тех же входах (или зафиксировать причину недетерминизма).

