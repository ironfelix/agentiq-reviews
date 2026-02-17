# AgentIQ — Documentation Home

Главная навигация по проекту: что за модули есть в продукте, где их документация и где смотреть архитектуру.

Last updated: 2026-02-17

## Start Here

- `../README.md` — коротко: что делает AgentIQ и структура репозитория
- `docs-home.html` — HTML-портал документации (навигация + статусы + карта модулей)
- `product/PRODUCT.md` — что это “простыми словами” (ценность для продавца)
- `PROJECT_MAP.md` — карта модулей и архитектуры (как устроен продукт внутри)
- `../QUICK_START_CHECKLIST.md` — чеклист быстрого запуска (если нужен)
- `../next-actions.md` — roadmap / текущие действия

## Products Inside The Product

### Unified Communications Workspace (WB-first)

Единый workspace, в котором в одном списке живут: `чаты`, `вопросы`, `отзывы` (unified entity: `Interaction`).

- `product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md` — живой execution-log и текущий scope
- `chat-center/INDEX.md` — документация Chat Center (как запустить, схема БД, исследования)
- `chat-center/SCENARIO_ENGINE.md` — сценарность, P0-P3, guardrails (MD)
- `chat-center/scenario-engine.html` — то же "по-человечески" (HTML)
- **`chat-center/LOADING_ARCHITECTURE.md`** — архитектура загрузки данных: flow, кэш, пагинация, риски, мировая практика (Zendesk, Intercom, etc.)

### Reviews Reports (legacy / отдельный контур)

Отдельный контур генерации детальных отчётов и PDF по отзывам (WBCON pipeline). Сейчас используется как самостоятельный сервис и как источник знаний/метрик.

- `reviews/README.md` — запуск и компоненты
- `reviews/PROJECT_SUMMARY.md` — что внутри и как работает pipeline
- `reviews/QUICKSTART.md` — детальный quickstart
- `reviews/API.md` — API endpoints

## Architecture & Tech Debt

- **`PROJECT_ANALYSIS_2026.md`** — технический анализ проекта (Feb 2026): оценка 7.5/10, Tech Debt каталог (18 items, 11 resolved)
- `PROJECT_MAP.md` — high-level архитектура и границы модулей
- `architecture/architecture.md` — текущая архитектура (общая)
- `architecture/architecture-mvp2.md` — MVP2 Reviews (архитектурные детали)
- `architecture/AGENTIQ_2.0_ARCHITECTURE.md` — vision / 2.0
- `architecture/SCALING_NOTES.md` — заметки о масштабировании AI analysis pipeline (MVP → enterprise)
- `chat-center/LOADING_ARCHITECTURE.md` — архитектура загрузки UI: polling, пагинация, кэш, риски, мировые практики
- `SLA_RULES.md` — SLA targets + rationale (WB, benchmarks)
- `BILLING_ARCHITECTURE.md` — дизайн биллинга (план)

## Ops / Deploy / Security

- `ops/DEPLOYMENT.md`
- `ops/SECURITY_FIXES_APPLIED.md`
- `ops/RULES.md`
- **`ops/RELEASE_CYCLE.md`** — релизный цикл (окружения, AI code review, CI/CD, testing strategy, monitoring)
- **`security/SECURITY_AUDIT.md`** — полный security audit (36 findings: 6 CRITICAL, 10 HIGH, 12 MEDIUM, 8 LOW)
- **`security/SECURITY_REVIEW_PROCESS.md`** — процесс security review при разработке и релизах (CI checks, checklists, secrets rotation, incident response)

## Design System & Prototypes

- `design-system/README.md`
- `design-system/HELP_PANEL.md`
- `prototypes/` — прототипы экранов
- `prototypes/legacy/` — старые прототипы

## Research

- `research/INDEX.md` — индекс исследований (рынок, UX, WB research)
- `research/WB_LOGISTICS_CJM.html` — пример "человеческой" CJM-документации (HTML)
- **`product/CRM_PERFORMANCE_INTEGRATION_PLAN.md`** — исследование интеграции CRM-маркетинга и performance-каналов (2026, РФ рынок)
- **`../crm-performance-plan.html`** — HTML версия CRM research для GitHub Pages

## Changelog

- `CHANGELOG.md` — changelog Chat Center

## Specs (Spec-Driven Development)

- `specs/README.md` — как мы пишем спеки и как по ним кодим с AI-агентом
- `specs/CATALOG.md` — карта спек и инвентарь API (что уже есть и где это описано)
- `specs/SPEC_DRIVEN_RULES.md` — правила/guardrails для Spec-Driven
- `specs/TEMPLATE_FEATURE_SPEC.md` — шаблон спеки на фичу/эндпоинт/интеграцию
- `specs/TEMPLATE_FUNCTION_SPEC.md` — шаблон контракта функции

## Bugs / Ideas Log

- `bugs/БАГИ.md` — единый лог багов, UX/copy и идей/гипотез (demo notes)
- `bugs/INBOX.md` — сырой поток заметок (без структуры) для триажа
