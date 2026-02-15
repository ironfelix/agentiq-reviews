# Marketplace Adapter Contract

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Goal
Задать общий контракт, чтобы добавление нового маркетплейса не ломало сущности и guardrails.

## 2) Capabilities (MUST)
Каждый marketplace adapter MUST явно объявлять:
- `supports_chats` / `supports_reviews` / `supports_questions`
- `supports_reply` (по сущности)
- `supports_close` / `supports_reopen` (для чатов)
- Лимиты: `max_reply_length`, запрещенные символы/ссылки, rate limits
- Semantics: что значит "closed", "responded", "published"

## 3) Normalization
MUST:
- Нормализация должна быть детерминированной.
- Все external ids и raw payload refs должны сохраняться (но без утечек секретов).

## 4) Error Model
MUST:
- Ошибки адаптера должны маппиться в единый набор типов: `auth_error`, `rate_limited`, `validation_error`, `transient_error`.

## 5) Acceptance Criteria
1. Новый marketplace можно подключить без изменения domain-спек сущностей: меняются только adapter + mapping.
2. Guardrails одинаково применяются к reply вне зависимости от marketplace.

