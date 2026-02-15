# Entity Spec: Reviews

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Goal / Non-goals
- Goal: отдельный контракт для отзывов (это не чат): другое SLA, публичность, репутационные риски.
- Non-goals: конкретный тональность/copy бренда (может быть отдельной спекой/гайдом).

## 2) Domain Model (нормализованная модель)
MUST:
- Review имеет внешний id в marketplace, ссылку на seller, продукт (если есть), текст, рейтинг, дату.
- Review может иметь "ответ продавца" (reply) с отдельным статусом публикации.

## 3) Processing Pipeline
MUST:
- Описать этапы: sync -> normalize -> analyze -> draft -> reply/publish.
- Все AI-операции идут через eval/guardrails (минимум: banned phrases, PII, unsafe promises).

Related docs (существующее):
- `docs/reviews/RESPONSE_GUARDRAILS.md`
- `docs/reviews/reasoning-rules.md`
- `docs/reviews/QUALITY_SCORE_FORMULA.md`

Spec:
- `../guardrails/REVIEWS_RESPONSES.md`
- `../guardrails/AI_DRAFTS.md`

## 4) Marketplace Variants
MUST:
- Указать ограничения публикации ответов (лимиты длины, задержки, модерация, редактирование).
Spec:
- `../marketplaces/CONTRACT.md`
- `../marketplaces/WILDBERRIES.md` (если применимо)

## 5) Acceptance Criteria (минимум)
1. Нормализация отзывов детерминирована.
2. Guardrails для ответов на отзывы применяются всегда.
3. Есть audit trail: кто инициировал draft/reply, на каком контексте, с какими ограничениями.

## 6) Tests
- Unit: нормализация, правила guardrails (как минимум ключевые запреты).
- Integration: "draft -> reply" на фикстурах.

