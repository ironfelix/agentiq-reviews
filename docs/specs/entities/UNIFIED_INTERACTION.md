# Entity Spec: Unified Interaction

Last updated: 2026-02-13
Status: draft

Owner:

## 1) Goal / Non-goals
- Goal: описать unified модель `Interaction`, которая агрегирует разные сущности (chat/review/question) для единого inbox.
- Non-goals: "заставить" разные сущности быть одинаковыми. Спеки сущностей остаются отдельными.

## 2) Types
MUST:
- Interaction имеет поле типа: `chat` | `review` | `question` (или эквивалент), которое управляет логикой UI/AI/синка.
- Нельзя потерять исходные external ids и marketplace source.

## 3) Normalization Contract
MUST:
- Для каждого типа задается минимальный набор полей, обязательных для UI списка и деталей.
- Поля, которых нет у конкретного marketplace, должны быть `null`/absent и корректно обрабатываться.

## 4) Routing To Specs
MUST:
- В зависимости от типа Interaction применяются:
  - domain spec соответствующей сущности
  - соответствующие guardrails
  - marketplace adapter contract

## 5) Acceptance Criteria
1. Любой Interaction однозначно маппится к сущности и marketplace.
2. Нормализация детерминирована, версия контракта зафиксирована.

## 6) Tests
- Unit: mapping и нормализация.
- Integration: sync нескольких типов в одну ленту.

