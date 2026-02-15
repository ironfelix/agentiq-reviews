# Entity Spec: Questions

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Goal / Non-goals
- Goal: описать контракт "вопрос" (обычно pre-purchase), отличающийся от чатов и отзывов.
- Non-goals: обучающие материалы по продуктам (это отдельный knowledge слой).

## 2) Domain Model (нормализованная модель)
MUST:
- Question имеет внешний id, seller, product context (если доступен), текст, дату, статус ответа.
- Вопрос обычно публичен и виден потенциальным покупателям (репутационный риск).

## 3) SLA / Prioritization
MUST:
- Вопросы должны иметь свой SLA (часто короче, pre-purchase).
Related docs:
- `docs/SLA_RULES.md` (если там есть вопросы)

## 4) AI Drafting / Reply
MUST:
- Ответ на вопрос подчиняется guardrails вопросов (обещания, юридические риски, точность).
Spec:
- `../guardrails/QUESTIONS_RESPONSES.md`
- `../guardrails/AI_DRAFTS.md`

## 5) Marketplace Variants
MUST:
- Для каждого маркетплейса описать ограничения: длина, ссылки, эмодзи, запрещенные темы, модерация.
Spec:
- `../marketplaces/CONTRACT.md`
- `../marketplaces/WILDBERRIES.md`
- `../marketplaces/OZON.md`

## 6) Acceptance Criteria
1. Для вопроса можно построить корректный "контекст" (продуктовые факты) без PII.
2. AI draft не нарушает guardrails.

## 7) Tests
- Unit: проверки guardrails и форматирования.
- Integration: draft->reply на фикстурах.

