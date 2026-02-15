# Guardrails Spec: Reviews Responses

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Source Of Truth (existing)
Сейчас основные правила ответов на отзывы описаны в:
- `docs/reviews/RESPONSE_GUARDRAILS.md`

Эта спека делает это "контрактом" для нового unified inbox и будущих маркетплейсов.

## 2) Hard Rules (MUST / MUST NOT)
MUST:
- Применять banned phrases и ограничения формата до отправки ответа.
- Учитывать публичность: ответ видят будущие покупатели.

MUST NOT:
- Обещать то, что нельзя выполнить (refund/compensation), если не подтверждено политикой/инструкцией.
- Просить/публиковать персональные данные.

## 3) Formatting / Tone
TBD: (заполнить требования к длине, стилю, упоминанию конкретных действий).

## 4) Marketplace Variants
MUST:
- Валидировать ограничения длины/символов/ссылок по marketplace capabilities.

## 5) Acceptance Criteria
1. Ответ, нарушающий banned phrases, отклоняется до отправки.
2. Логи и аудит не содержат PII.

