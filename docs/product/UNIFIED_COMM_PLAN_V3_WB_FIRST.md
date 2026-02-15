# AgentIQ Plan v3 — Unified Communications (Reviews + Questions + Chats)

**Дата:** 2026-02-12  
**Статус:** In execution (Phase 0 started)  
**Основа UI:** `docs/prototypes/app-screens-v3-ru.html`  
**Backlog:** `docs/product/BACKLOG_UNIFIED_COMM_V3.md`
**Текущий прод-контур:** `agentiq.ru/app` (`apps/chat-center`) + `apps/reviews`

**Staging demo (HTTP/IP):** `http://79.137.175.164/app/` (см. `docs/product/STAGING_DEMO_STATUS.md`)

### Execution status (live)

Сделано (2026-02-14, cont.):
 - **Bug #4 + #5 Fix: Chat list shows "Нет обращений по фильтру" after tab switch** -- badge shows (39) but list is empty.
   - **Root cause:** Bug #1/#3 fix (CSS show/hide) means ChatList never unmounts. Local `useState` for `activeFilter` and `activeChannel` persists across workspace switches. If user had "Обработаны" or "Без ответа" selected when navigating away, returning to messages kept the stale filter — matching zero items while the pipeline badge showed the full count.
   - **Fix (ChatList.tsx):** Added `isActive` prop (boolean). When `isActive` transitions from `false` to `true`, a `useEffect` resets `activeFilter` to `'all'`, `activeChannel` to `'all'`, and `searchQuery` to `''`. Uses `prevIsActiveRef` to detect the transition.
   - **Fix (App.tsx):** Added workspace-change effect that fires when `activeWorkspace` changes to `'messages'`. Resets `filters` to `{}`, restores `interactions` from the `'all|all'` cache, and sets `activeCacheKeyRef` to `'all|all'`. This ensures the App-side data scope matches ChatList's reset filter state. If `filters.has_unread` actually changed (was `true` before), the existing filter-change effect also fires and triggers a fresh API fetch.
   - **Files:** `apps/chat-center/frontend/src/App.tsx` (workspace-change effect + isActive prop), `apps/chat-center/frontend/src/components/ChatList.tsx` (isActive prop + reset effect).
   - **Build:** `npm run build` -- OK, no errors.

Сделано (2026-02-14):
 - **BL-DEMO-005: Demo data при "Пропустить подключение"** -- when user skips WB connection during onboarding, 12 demo interactions are seeded (5 reviews, 4 questions, 3 chats) so the inbox looks alive.
   - Backend: `app/services/demo_data.py` -- `seed_demo_interactions()` creates realistic Russian WB interactions with varied priorities, statuses, and channels. Idempotent (skips if demo data already exists). All demo records marked with `source="demo"` and `extra_data.is_demo=true`.
   - Backend: `POST /api/auth/seed-demo` endpoint in `app/api/auth.py` -- called from frontend skip flow, requires auth.
   - Frontend: `handleSkipConnection()` in `App.tsx` now calls `authApi.seedDemo()` after setting the skip flag, so interactions appear immediately.
   - Frontend: gray "Demo" badge (`source-badge demo`) shown on demo interactions in `ChatList.tsx`.
   - Frontend: `api.ts` -- added `authApi.seedDemo()` method.
   - CSS: `.source-badge.demo` style in `index.css` (subtle gray).
   - Demo content: 1-5 star reviews (urgent/high/normal/low priorities), pre-purchase questions (availability, sizing, pre_purchase intents), chats (defect with urgent priority, size question with seller reply, delivery inquiry with seller reply). InteractionEvent records created for replied interactions.

Сделано (2026-02-15):
 - **Bug #1 + #3 Fix: Tab/page switching flicker** -- replaced conditional rendering (ternary chain) with CSS show/hide in `App.tsx`. All workspace pages (messages, analytics, promo, settings) are now rendered simultaneously and toggled via `display: none` instead of mount/unmount. This eliminates DOM destruction/reconstruction on tab switch, preventing layout flicker and loading-state flash caused by useEffect re-fires on component mount.
   - **Root cause:** `App.tsx` used a ternary chain (`activeWorkspace === 'analytics' ? ... : activeWorkspace === 'promo' ? ... : ...`) which unmounted the old page and mounted the new one on every tab switch. Components like PromoCodes and SettingsPage had useEffect hooks that fetched data on mount, briefly showing loading states. The DOM rebuild also caused visible layout shift.
   - **Fix:** Each workspace page is now always rendered as a sibling div with `style={{ display: activeWorkspace === 'xxx' ? undefined : 'none' }}`. Settings uses `display: 'contents'` when active to preserve its flex layout.
   - **File:** `apps/chat-center/frontend/src/App.tsx` (lines 1197-1778)
   - **Build:** `npm run build` passes cleanly.

 - **Bug #2 Fix: WB API key not persisting on re-login** -- login/register response now includes `has_api_credentials`, `sync_status`, `sync_error`, `last_sync_at` so the frontend can correctly skip onboarding for users who already connected their WB API key.
   - **Root cause:** `SellerAuthInfo` schema (used by `/auth/login` and `/auth/register` responses) did not include `has_api_credentials`. The field was always `undefined` in the frontend `User` object after login, so `!user.has_api_credentials` was always `true`, triggering the onboarding screen even when the key was already saved in DB.
   - **Fix (backend):** `app/schemas/auth.py` -- added `has_api_credentials: bool`, `sync_status`, `sync_error`, `last_sync_at` to `SellerAuthInfo`.
   - **Fix (backend):** `app/api/auth.py` -- both `register()` and `login()` endpoints now pass `has_api_credentials=bool(seller.api_key_encrypted)` plus sync fields to the response.
   - **No frontend changes needed** -- `User` type in `types/index.ts` already had these as optional fields; they were just never populated from the login response.
   - **Verification:** The `/auth/me` endpoint (used on page refresh) was already correct. The bug only manifested on fresh login flow.

 - **BL-NEXT-002 (BL-P2-002): E2E Playwright Smoke Tests on CJM** -- headless Playwright test suite covering the critical user journey.
   - Directory: `apps/chat-center/e2e/` (standalone npm package with `@playwright/test`).
   - Config: `playwright.config.ts` -- headless Chromium, 30s timeout, screenshot-on-failure, configurable `BASE_URL` env.
   - Helper: `helpers/auth.ts` -- `registerUser()`, `loginUser()`, `skipOnboarding()`, `loginAndSkipToInbox()`, `navigateToWorkspace()`, `generateTestEmail()` (unique per run).
   - Tests (`tests/cjm-smoke.spec.ts`) -- 9 smoke tests:
     1. Registration (fill form, submit, verify onboarding redirect)
     2. Skip WB onboarding (verify demo banner)
     3. Main inbox with channel tabs (`filter-pill` in `.channel-filters`) and status filters (Срочно/Без ответа/Обработаны)
     4. Open interaction detail (click `.chat-item`, verify `.chat-window` / `.product-context`)
     5. Analytics page (`.analytics-page`, KPI strip, period controls, grids)
     6. Settings page (3 tabs: Подключения/AI-ассистент/Профиль)
     7. Sidebar navigation (messages -> analytics -> settings -> promo round-trip)
     8. Logout (sidebar -> login page)
     9. Demo mode (no registration)
   - Run: `cd apps/chat-center/e2e && npm install && npx playwright install chromium && npx playwright test`
   - Prereqs: backend at `:8001`, frontend at `:5173` (or `BASE_URL=https://agentiq.ru/app`).

Сделано (2026-02-14):
 - **BL-DEMO-003: Frontend source labeling (wb_api vs wbcon_fallback)** -- добавлены визуальные бейджи источника данных в список чатов.
   - `source` field добавлен в `Chat` тип (`types/index.ts`) и проброшен через `interactionToChat()` в `App.tsx`.
   - Бейдж рендерится в `ChatList.tsx` → `.chat-item-meta`: зеленый "WB API" (`wb_api`) или оранжевый "Fallback" (`wbcon_fallback`).
   - CSS: `.source-badge`, `.source-badge.wb-api`, `.source-badge.fallback` в `index.css` — следует design system (`COMPONENTS.md` badges section).
   - Build: `npm run build` — OK, без ошибок.
 - **BL-PILOT-003: LLM Intent Fallback for questions** — добавлен LLM-based fallback для классификации интента вопросов.
   - Новый модуль: `app/services/ai_question_analyzer.py` — hybrid intent classification (rule-based first, LLM fallback via DeepSeek/OpenAI-compatible API).
   - Конфиг: `ENABLE_LLM_INTENT` (default `false`) в `app/config.py` — включает LLM fallback, fail-safe, 5s timeout.
   - Интеграция: `interaction_ingest.py` — при `general_question` + `needs_response=True` вызывает LLM fallback, пересчитывает priority/SLA.
   - Новое поле `intent_detection_method` в `extra_data` (`rule_based` / `llm`) для трекинга метода классификации.
   - `_priority_for_question_with_intent()` поддерживает `intent_override` для LLM-detected интентов.
   - Тесты: `tests/test_ai_question_analyzer.py` — 20 тестов (fast path, LLM fallback, timeout resilience, invalid response, config flag, priority override).
   - Никогда не блокирует ingestion при ошибке LLM (try/except + logger.debug).

Сделано (2026-02-13):
 - UI: включены страницы `Промокоды` и `Настройки` в `/app` (sidebar + bottom nav), без влияния на экран сообщений.
 - Promo (v3): промокоды + help-panel + автосохранение + toggles “AI предлагает промокод” / “предупреждать об отзывах”.
 - Settings (v3): `Подключения`/`AI-ассистент`/`Профиль` (AI-настройки с сохранением; logout доступен с mobile через профиль).
 - Backend: добавлен `Settings API` (`/api/settings/promo`, `/api/settings/ai`) с хранением в `runtime_settings` (namespace per seller).

Сделано (2026-02-12):
0. Demo-fixes / correctness (2026-02-12):
 - Fix ingestion timestamps: `_parse_iso_dt()` восстановлен, `occurred_at` для review/question теперь заполняется (реальные даты вместо “сегодня”).
 - Fix seller replies visibility: WB ответы сохраняются в `interaction.extra_data.last_reply_text` (review/question), UI показывает outgoing message для “Отвечено”.
 - Fix chat history: для `channel=chat` UI грузит реальные сообщения через `chat_id` из `interaction.extra_data` и `/api/messages/chat/{chat_id}` (не synthetic 1-2 сообщения).
 - Fix counters: счётчики каналов/очередей в UI берутся из `GET /api/interactions/metrics/quality` (pipeline totals), а не `len(page_size)`.
 - Fix staging assets: `/app/` отдаёт SPA entry, а ассеты обслуживаются из `/assets/*` (root), чтобы Vite build корректно грузился на staging.
 - Regression: `backend pytest` green; `frontend npm run build` green.
1. В `apps/chat-center/backend` добавлен foundation слой `interaction`.
2. Добавлены read-endpoints: `GET /api/interactions`, `GET /api/interactions/{id}`.
3. Реализован `WB Reviews ingestion` в unified entity:
 - сервис `interaction_ingest.ingest_wb_reviews_to_interactions()`,
 - коннектор `WBFeedbacksConnector` (`feedbacks-api.wildberries.ru`),
 - endpoint ручного запуска `POST /api/interactions/sync/reviews`.
4. Реализован `WB Questions ingestion` в unified entity:
 - сервис `interaction_ingest.ingest_wb_questions_to_interactions()`,
 - коннектор `WBQuestionsConnector`,
 - endpoint ручного запуска `POST /api/interactions/sync/questions`.
5. Валидация на рабочем WB токене:
 - `buyer-chat-api` (`/seller/chats`, `/seller/events`) — `200`,
 - `feedbacks-api` (`/feedbacks/count`, `/feedbacks`, `/questions/count-unanswered`, `/questions`) — успешно,
 - выявлено требование: `isAnswered` обязателен для `/feedbacks` и `/questions`.
6. Реализован `reply dispatcher` для unified interactions:
 - endpoint `POST /api/interactions/{id}/reply`,
 - channel `review` -> `POST /api/v1/feedbacks/answer`,
 - channel `question` -> `PATCH /api/v1/questions` (обязательный `state` + `answer.text`).
7. Добавлен `channel=chat` в interaction layer:
 - endpoint `POST /api/interactions/sync/chats` (строит interaction из таблицы `chats`),
 - `reply dispatcher` для `chat` создаёт `outgoing message` и отправляет через существующий marketplace send task.
8. Добавлен AI-draft endpoint:
 - `POST /api/interactions/{id}/ai-draft`,
 - поддержка `review/question/chat`,
 - кэш последнего драфта в `interaction.extra_data.last_ai_draft`.
9. Добавлен автоматический processing слой:
 - Celery task `sync_all_seller_interactions` + `sync_seller_interactions`,
 - periodic schedule в beat: каждые 5 минут (`sync-all-seller-interactions-every-5min`),
 - pipeline `reviews/questions/chats -> interactions` выполняется фоном.
10. Добавлены lightweight тесты interaction-layer:
 - файл `apps/chat-center/backend/tests/test_interactions_layer.py`,
 - покрытие: регистрация роутов + fallback draft behavior.
11. Добавлен quality metrics слой (`interaction_events`) для воронки `draft -> reply`:
 - модель `interaction_events` + сервис `interaction_metrics`,
 - endpoint `GET /api/interactions/metrics/quality`,
 - автологирование событий в `POST /api/interactions/{id}/ai-draft` и `POST /api/interactions/{id}/reply`,
 - классификация ответа: `draft_accepted` / `draft_edited` / `reply_manual`.
12. Расширены тесты interaction-layer:
 - проверка регистрации `/api/interactions/metrics/quality`,
 - unit-тесты классификации качества ответа (`accepted/edited/manual`),
 - текущий результат: `7 passed`.
13. Начат frontend data-layer переход на unified interactions:
 - в `frontend/src/types` добавлены типы `Interaction*`,
 - в `frontend/src/services/api.ts` добавлен `interactionsApi` (list/get/sync/draft/reply/quality metrics).
14. Добавлены contract/integration tests для interaction endpoints:
 - файл `apps/chat-center/backend/tests/test_interactions_api_integration.py`,
 - покрытие: `sync/reviews`, `sync/questions`, `sync/chats`, `ai-draft`, `reply`, `metrics/quality`,
 - текущий результат пакета: `10 passed`.
15. Frontend `/app` переключен на unified interactions как основной источник:
 - `App.tsx` читает список через `interactionsApi.getInteractions`,
 - карточка обращения отправляет ответ через `POST /api/interactions/{id}/reply`,
 - AI-драфт берется из `POST /api/interactions/{id}/ai-draft`,
 - выполнена сборка фронта: `npm run build` — `OK`.
16. В UI добавлен quality dashboard оператора:
 - блок `Качество ответов (30 дней)` читает `GET /api/interactions/metrics/quality`,
 - отображаются `accept/edit/manual rate` + текущий backlog.
17. В левую колонку добавлены канальные фильтры:
 - `Все / Отзывы / Вопросы / Чаты`,
 - фильтр прокидывается в backend как `channel` в `GET /api/interactions`.
18. В карточку обращения добавлен read-only блок probabilistic linking:
 - отображение `confidence`, `explanation`, `reasoning_signals` из `extra_data.link_candidates`,
 - зафиксировано правило: при confidence `< 85%` авто-действия отключены.
19. Реализован backend слой кросс-канального linking:
 - `interaction_linking.py` с deterministic/probabilistic сигналами,
 - сохранение `extra_data.link_candidates` при sync `reviews/questions/chats`,
 - reciprocal refresh связанных interaction.
20. Добавлена историческая quality-аналитика:
 - endpoint `GET /api/interactions/metrics/quality-history`,
 - агрегаты по дням (`replies_total`, `draft_accepted`, `draft_edited`, `reply_manual`, rates),
 - UI-график `Динамика ответов (по дням)`.
21. Для `questions` добавлена продуктовая приоритизация:
 - intent-классификация (`sizing_fit`, `availability_delivery`, `spec_compatibility`, etc.),
 - расчет SLA target/due и `priority_reason`,
 - сохранение в `interaction.extra_data`.
22. UX очереди для `questions` доведен в UI:
 - в деталях обращения показываются `intent`, `SLA дедлайн`, состояние SLA и причина приоритета,
 - в списке обращения с просроченным SLA выделяются как срочные.
23. Закрыты дефекты стабильности ingestion/linking:
 - нормализация naive/aware datetime в linking (UTC),
 - фикс `touched_ids` в chat-ingest,
 - regression-пакет `interactions_*`: `10 passed`.
24. Реализован deterministic thread timeline:
 - endpoint `GET /api/interactions/{id}/timeline`,
 - thread scope: `customer_order | customer | product | single`,
 - к каждому шагу добавлены `match_reason`, `confidence`, `action_mode`, `policy_reason`.
25. Добавлены action guardrails в linking-policy:
 - helper `evaluate_link_action_policy(...)`,
 - auto-actions только для `deterministic` links при confidence `>= 85%`,
 - probabilistic links всегда маркируются как `assist_only`.
26. Timeline и guardrails выведены в UI:
 - в правой панели блока обращения отображается `Deterministic Thread Timeline`,
 - для каждого шага видно `auto-allowed` vs `assist-only`.
27. Усилен reliability/surfacing слой синхронизации:
 - `sync_seller_interactions` теперь пишет `sync_status/sync_error/last_sync_at` и не теряет частичный прогресс при падении одного канала,
 - унифицированы retry-сообщения (`attempt`, `retry=scheduled|exhausted`) для chat/interactions sync,
 - добавлен ручной триггер `POST /api/auth/sync-now` (очередь `chats` + `interactions`).
28. В UI добавлен явный sync-error surfacing:
 - баннер статуса синхронизации (syncing/error) в левой колонке,
 - action `Повторить` для ручного запуска sync без переподключения API-ключа.
29. Добавлены тесты reliability-сценариев:
 - `test_manual_sync_now_queues_background_tasks`,
 - regression пакет `interactions_*`: `11 passed`.
30. Добавлен operations-alerts слой для пилота:
 - endpoint `GET /api/interactions/metrics/ops-alerts`,
 - алерты по `questions SLA` (overdue / due soon),
 - алерт регрессии качества (рост manual-rate week-over-week).
31. Алерты выведены в UI quality dashboard:
 - бейджи `SLA overdue`, `SLA due soon`, `Manual delta`,
 - список активных алертов с severity.
32. Реализованы операторские сценарии для deterministic timeline:
 - быстрый переход в другой шаг thread (`Перейти`) прямо из правой панели,
 - быстрый переход в соответствующий раздел WB (`WB`),
 - применение шаблона ответа из предыдущего шага (`Шаблон`) в текущий draft.
33. Расширен contract timeline payload:
 - `is_current`, `wb_url`, `last_reply_text`, `last_ai_draft_text` на каждом timeline step,
 - regression пакет `interactions_*`: `11 passed`.
34. Закрыт пункт policy negative tests:
 - добавлен тестовый пакет `test_interaction_linking_policy.py`,
 - подтверждено, что probabilistic links всегда `assist_only` и не включают auto-action.
35. Обновлен regression статус:
 - пакет `interactions_* + linking_policy`: `13 passed`.
36. Добавлен pilot readiness gate (backend + frontend):
 - endpoint `GET /api/interactions/metrics/pilot-readiness` с формальными checks (`sync freshness`, `channel coverage`, `SLA overdue`, `manual-rate`, `regression`, `backlog`, `reply activity`),
 - решение `go/no-go` строится по blocker-checks (детерминированные блокеры релиза),
 - в UI quality dashboard добавлен блок `Pilot Go/No-Go readiness`.
37. Подготовлен операционный документ пилота:
 - `docs/product/PILOT_QA_MATRIX_AND_GONOGO_CHECKLIST.md`,
 - фиксирует пошаговый matrix прогон по `review/question/chat` и критерии rollback.
38. Добавлен автоматизированный pilot QA runner:
 - `apps/chat-center/backend/scripts/run_pilot_qa_matrix.py`,
 - safe-mode по умолчанию (без live reply), формирует markdown-отчет с шагами матрицы и `GO/NO-GO` snapshot.
39. Обновлена readiness-политика под WB-first приоритет:
 - обязательные каналы для blocker-check: `review/question`,
 - `chat` переведен в `recommended` (warn, non-blocker) для пилота,
 - `sync_freshness` получил fallback по факту свежего interaction-ingest.
40. Выполнен живой safe-run pilot matrix на рабочем WB токене:
 - отчет `docs/product/reports/pilot-qa-report-20260212-174823.md`,
 - результат `GO` (без live reply), warnings: `recommended chat coverage`, `reply activity baseline`.
41. Закрыт gap по chat coverage без зависимости от воркера:
 - `ingest_chat_interactions(..., direct_wb_fetch=True)` поддерживает прямой pull chat-threads из WB events API,
 - endpoint `POST /api/interactions/sync/chats?direct_wb_fetch=true` для pilot/staging прогонов.
42. Обновлен pilot QA runner для chat fallback:
 - `scripts/run_pilot_qa_matrix.py` теперь вызывает `sync/chats` с `direct_wb_fetch=true`,
 - в safe-run автоматически проверяется `draft_chat`.
43. Выполнен повторный живой safe-run после chat-fallback:
 - отчет `docs/product/reports/pilot-qa-report-20260212-175510.md`,
 - результат `GO`, warnings reduced до `reply_activity` (chat coverage подтвержден).
44. Добавлен runtime-переключатель LLM через БД (без деплоя):
 - новая таблица `runtime_settings` (`llm_provider`, `llm_model`, `llm_enabled`),
 - generation-пайплайн (`ai-draft` и analyzer) читает provider/model из БД на каждом запуске,
 - для пилота установлен профиль `deepseek / deepseek-chat / enabled=true`.
45. Закрыт false-warn по `reply_activity` для demo-safe прогонов:
 - readiness-check теперь учитывает не только `reply_sent` события, но и observed baseline answered по required каналам (`review/question`) за окно,
 - если исторические ответы есть в WB source, check проходит как `pass` даже без live `/reply` в safe-run,
 - добавлен unit-test fallback сценария в `test_interaction_metrics.py`.
46. Pilot-readiness endpoint параметризован под операции демо/пилота:
 - `GET /api/interactions/metrics/pilot-readiness` теперь принимает `min_reply_activity` и `reply_activity_window_days`,
 - пороги возвращаются в `thresholds` payload для явной трассировки калибровки.
47. QA runner синхронизирован с новой калибровкой readiness:
 - `scripts/run_pilot_qa_matrix.py` принимает `--min-reply-activity` и `--reply-activity-window-days`,
 - параметры прокидываются в вызов `GET /api/interactions/metrics/pilot-readiness`.
48. UI readiness-контроль добавлен в `/app` quality dashboard:
 - оператор может менять `min replies` и `window days` прямо в интерфейсе,
 - калибровка применяется к backend readiness-запросу и отображается в `thresholds`.
49. Закрыт UX-риск бесконечного spinner при подключении WB в local/demo:
 - `POST /api/auth/connect-marketplace` в `DEBUG` делает direct WB sync (без зависимости от Celery worker),
 - `GET /api/auth/me` получил guardrail: stale `syncing` (`>=5 min`) автоматически переводится в `error` с явным текстом для retry.
50. Внедрен demo-CJM входа: `Login -> Connect WB -> Workspace`:
 - добавлен отдельный onboarding-экран подключения WB с ветками `connect / retry / skip`,
 - skip сохраняется локально (demo-mode) и позволяет зайти в workspace без ключа.
51. Аналитика вынесена в отдельный workspace-раздел:
 - добавен переключатель `Сообщения / Аналитика` в app-shell,
 - в `Сообщениях` правая панель теперь про контекст обращения,
 - в `Аналитике` показываются quality/ops/readiness/history блоки.
52. Закрыт tech-debt инкрементального chat-sync cursor:
 - `sync_seller_chats` теперь читает/пишет last cursor в `runtime_settings` (namespace `sync_cursor:{marketplace}:{seller_id}`),
 - `WB` продолжает sync с последнего `next_cursor`, `Ozon` — с последнего `message_id`,
 - добавлен regression-тест `apps/chat-center/backend/tests/test_sync_cursor_state.py`.
53. UI flow приведен к `app-screens-v3-ru.html` (CJM-safe):
 - `workspace` навигация переведена в `app-shell + sidebar + bottom-nav` по v3 структуре,
 - onboarding/connect/sync экраны переведены на v3 классы и состояние,
 - демо-баннер подключения (`skip mode`) вынесен в верх app-shell как в прототипе.
54. Экран `Аналитика` отделен от правого manager-context (как в v3 прототипе):
 - в `Сообщениях` правая панель оставлена только под операционный контекст обращения (детали, timeline, AI, действия),
 - в `Аналитике` реализован отдельный full-page layout (`analytics-header`, period/mode controls, KPI strip, quality/ops/readiness/history блоки),
 - rationale: менеджерский контекст не смешивается с KPI-режимом, CJM-переход `Messages -> Analytics` повторяет целевой UX.

Следующие шаги:
1. Закрыть `reply_activity baseline`:
 - для demo-safe закрыто через source baseline fallback (см. пункт 45),
 - для pilot-go-live остаётся controlled live-run (`--send-replies`) и фиксация реальных `reply_sent`.
2. Подготовить финальный pre-demo smoke перед Pilot Demo / Go-NoGo (February 19, 2026):
 - повторный safe-run матрицы в день демо,
 - подтверждение, что `pilot-readiness` остается `GO` на целевом seller.

### Demo Readiness (когда показываем)

1. `Product Demo #1 (текущий инкремент)` — **February 13, 2026**
 - scope: unified inbox + timeline + guardrails + sync retry + ops alerts;
 - входной критерий: `backend regression green`, `frontend build OK`, ручной smoke на 1 seller.

2. `Product Demo #2 (pilot candidate)` — **February 17, 2026**
 - scope: + операторские сценарии timeline + policy negative tests;
 - входной критерий: закрыты пункты 1-2 из блока "Следующие шаги".

3. `Pilot Demo / Go-NoGo` — **February 19, 2026**
 - scope: live end-to-end на рабочем WB токене (`sync -> draft -> reply`) по 3 каналам;
 - входной критерий: pilot QA matrix завершен, зафиксирован SLA/quality baseline, нет blocker-ошибок.

`Definition of Demo Ready`:
1. Нет P0/P1 дефектов по demo scope.
2. Все ключевые endpoint'ы demo-сценария проходят smoke.
3. В UI есть явные статусы ошибок и понятный fallback (без "тихих" падений).

### Текущий статус архитектуры `Источник -> Ingestion -> Storage -> Dispatcher -> Processing`

1. `Источник`:
 - статус: `done (WB API first)`,
 - реализовано: WB feedbacks/questions/chats и явный `source` в interaction.
2. `Ingestion`:
 - статус: `done (MVP)`,
 - реализовано: `sync/reviews`, `sync/questions`, `sync/chats` + Celery периодический sync.
3. `Storage`:
 - статус: `done (MVP)`,
 - реализовано: `interactions` + `interaction_events` (качество и воронка).
4. `Dispatcher`:
 - статус: `done (MVP)`,
 - реализовано: `reply` dispatch в review/question/chat каналы.
5. `Processing`:
 - статус: `done (MVP), hardening in progress`,
 - реализовано: AI draft + кеш драфта + quality snapshot + quality history + probabilistic linking + question intent/SLA + deterministic thread timeline + action guardrails.
 - next: production alerting + расширение policy/regression тестов.

### Зачем эти функции (product intent)

1. `Deterministic thread timeline`:
 - зачем: оператор должен видеть цельную историю касаний `review -> question -> chat`, а не три изолированных тикета;
 - эффект: меньше повторных ответов, меньше противоречий, выше скорость закрытия и конверсия по вопросам.

2. `Action guardrails`:
 - зачем: исключить авто-действия на ненадежных связках и снизить риск ошибочного ответа "не тому клиенту";
 - правило: auto-actions только для deterministic links при confidence `>= 85%`, probabilistic links — только assist-only.

3. `Question intent + SLA`:
 - зачем: очередь вопросов должна сортироваться по бизнес-импакту (конверсия/риск), а не по времени поступления;
 - эффект: оператор сначала обрабатывает вопросы с наибольшим влиянием на продажу/рейтинг.

4. `Sync reliability + error surfacing`:
 - зачем: оператор и владелец пилота должны видеть, когда фон реально упал, и запускать повтор без техподдержки;
 - эффект: ниже MTTR, меньше "тихих" сбоев и выше предсказуемость пилота.

5. `Ops alerts (SLA + quality regression)`:
 - зачем: пилот должен быстро ловить деградации до жалоб клиентов и потери конверсии;
 - эффект: проактивная реакция команды на рост просрочек и ухудшение качества ответов.
6. `Pilot readiness gate`:
 - зачем: нужен формальный и воспроизводимый `go/no-go` критерий, а не субъективная оценка перед пилотом;
 - эффект: одинаковые правила запуска для команды, меньше риска "выйти в пилот с красными blocker-метриками".
7. `Incremental sync cursor persistence`:
 - зачем: без сохранения cursor каждый polling-цикл может читать источник "с начала", что повышает задержки и риск дублей;
 - эффект: стабильный latency sync, меньше лишних API-вызовов и предсказуемая загрузка перед демо/пилотом.

---

## 1. Цель плана

Собрать единый продуктовый контур коммуникаций WB с приоритетом по объему и эффекту:

1. `Отзывы` (высокий объем, влияние на рейтинг и доверие)
2. `Вопросы` (pre-purchase, влияние на конверсию)
3. `Чаты` (меньше объем, выше точечная критичность)

Ключевая цель: не "чат-центр", а **операционная система коммуникации** с единым inbox, приоритизацией, AI-помощником и аналитикой.

---

## 1.1 Корректное описание продукта (для команды и внешних материалов)

AgentIQ — это **WB-first платформа управления коммуникациями продавца** в каналах `Отзывы`, `Вопросы`, `Чаты`.

Что делаем:
1. Собираем все обращения в единую операционную очередь.
2. Приоритизируем их по влиянию на рейтинг, конверсию и SLA.
3. Даём оператору контекст товара и историю релевантных ответов.
4. Помогаем ответить быстро и качественно через AI-драфты и guardrails.
5. Показываем прозрачную аналитику по качеству коммуникаций и эффекту.

Что не делаем:
1. Не строим операционное ядро на серых API.
2. Не подменяем WB данные fallback-источником без явной маркировки.
3. Не делаем авто-действия на вероятностных связках с низкой уверенностью.

---

## 2. Нефункциональные правила (жесткие)

## 2.1 Источники данных

1. **WB API first** для операционного ядра (`reviews/questions/chats`).
2. **WBCON не используется как primary source** для рабочих очередей и SLA.
3. **WBCON используется только как fallback для аналитики**, когда по WB ключу нет нужного исторического покрытия/среза.

## 2.2 Прозрачность данных для пользователя

1. В UI всегда показывать источник метрик: `WB API` или `WBCON fallback`.
2. Для fallback-метрик добавлять бейдж `Оценка/доп. источник`.
3. Любые денежные/ROI-оценки показывать как диапазон, не как точное значение.

---

## 3. Что уже есть в коде

## 3.1 Готово

1. Чатовый контур (`apps/chat-center`) с sync/AI/отправкой сообщений.
2. Зрелый review-пайплайн (`apps/reviews`) с асинхронной обработкой и отчетами.
3. Прототип v3 уже моделирует связку каналов и analytics/promo/settings.

## 3.2 Критичные гэпы

1. `questions` не интегрированы в основной runtime-контур на уровне `chat-center` API/DB/UI.
2. `apps/reviews` сейчас завязан на WBCON как основной сборщик отзывов; нужно перевести на WB-first.
3. Нет единой канонической модели сущности обращения (`interaction`) для всех 3 каналов.

---

## 4. Реально ли сделать Core-moat "Отзывы -> Вопросы -> Чаты"?

Короткий ответ: **да, реально**, но делать в 3 уровня.

## 4.1 Уровень A (100% детерминированно, MVP)

Связка по явным ключам:
1. `seller_id`
2. `marketplace=wb`
3. `nm_id`/`article` (товар)
4. временное окно

Что получаем:
1. Общий товарный контекст для оператора (топ-жалобы, типовые вопросы, шаблоны ответа).
2. Перенос "что уже отвечали" на уровне товара и интента.

## 4.2 Уровень B (детерминированно при наличии buyer/order id)

Если API канала отдает buyer/order идентификатор:
1. Строим `customer_thread` по `(seller, marketplace, customer_id[, order_id])`.
2. Видим последовательность касаний клиента по разным каналам.

Что получаем:
1. История взаимодействия "по клиенту".
2. Точные рекомендации "не повторять прошлый ответ", "эскалировать".

Важно:
1. По release notes WB от `2026-01-19` поле `clientID` в Buyers Chat объявлено к удалению с `2026-02-02`.
2. Поэтому customer-level linking в MVP считается **опциональным ускорителем**, а не обязательной опорой архитектуры.
3. Базовый контекст должен работать без `clientID` (через уровень A + safe probabilistic assist).

## 4.3 Уровень C (вероятностное связывание, только с confidence)

Если явного customer_id нет:
1. Используем вероятностное матчинг-правило по `(nm_id + time proximity + текстовые сигналы + лексика претензии)`.
2. Связку показываем как `вероятная`, с confidence.
3. Автодействия запрещены при confidence ниже порога.

Ограничение:
1. Это не источник "истины", только вспомогательная аналитика.

## 4.4 Какие поля реально используем для связи каналов

Канальные ключи (WB API):
1. Reviews/Questions: `nmId`, `id`, даты, статус ответа (`isAnswered`), текст.
2. Buyers Chat: `chatID`, события/сообщения, `clientName` (если есть), время события, `goodCard.nmID`.
3. `clientID` учитывать как legacy-сигнал только при фактическом наличии в ответе API.

Правила установления связи:
1. **Достоверная связь (deterministic)**:
 - совпали `seller_id + marketplace + nm_id`,
 - события находятся в рабочем временном окне,
 - нет конфликта по статусу/таймлайну.
2. **Усиленная достоверная (deterministic+)**:
 - есть `customer_id/order_id`, и цепочка подтверждается хронологией.
3. **Вероятностная (probabilistic)**:
 - нет стабильного customer/order ключа,
 - совпадает товар + близость во времени + семантика обращения,
 - присваивается `confidence` и объяснение признаков.

Операционные ограничения:
1. Автоответ/автоэскалация выполняются только при deterministic связях.
2. Probabilistic связи используются как подсказка оператору (assist-only).
3. При `confidence` ниже порога связь показывается только в аналитике, не в боевом action-потоке.
4. Сигналы из legacy-полей (`clientID`, если вернулся) не должны быть единственным основанием для авто-действия.

---

## 5. Целевая data-модель (минимум для запуска)

## 5.1 Новая каноническая сущность

`interaction` (единая запись обращения):
1. `id`
2. `seller_id`
3. `marketplace`
4. `channel` (`review|question|chat`)
5. `external_id`
6. `customer_id` (nullable)
7. `order_id` (nullable)
8. `nm_id` / `product_article`
9. `text`
10. `rating` (для review, nullable)
11. `status` (open/responded/closed)
12. `priority` (urgent/high/normal/low)
13. `needs_response` (bool)
14. `created_at`, `updated_at`
15. `source` (`wb_api|wbcon_fallback`)

## 5.2 Контекстные витрины

1. `product_context_daily` (агрегаты по товару и каналу)
2. `response_history` (история ответов продавца по интентам)
3. `link_candidates` (вероятностные связи + confidence + explanation)

---

## 6. План реализации (8 недель)

## Фаза 0 (Неделя 1): Foundations и migration strategy

Задачи:
1. Зафиксировать API-контракты WB по `feedbacks/questions/chats`.
2. Спроектировать `interaction` + миграции БД.
3. Ввести флаг `data_source` и политику fallback.
4. Подготовить feature flags для поэтапного включения новых каналов.

Критерий готовности:
1. Архитектурный ADR согласован.
2. Миграции проходят на staging.

## Фаза 1 (Недели 2-3): Reviews + Questions в unified inbox (WB-first)

Задачи backend:
1. Коннектор WB Feedbacks API: pull, статус ответа, публикация/редактирование ответа.
2. Коннектор WB Questions API: pull, публикация/редактирование ответа.
3. Нормализация обоих потоков в `interaction`.
4. SLA/priority движок для `review/question`.

Задачи frontend:
1. Единый список обращений с фильтром `channel`.
2. Карточка обращения с AI-draft и guardrails.
3. Bulk-операции для массового ответа/triage.

Критерий готовности:
1. Оператор закрывает день без переключения между разными интерфейсами.
2. Не менее 95% записей имеет корректный `channel` и `needs_response`.

## Фаза 2 (Неделя 4): Chat as escalation layer

Задачи:
1. Привести chat-контур к той же `interaction` модели (read/write).
2. Включить сценарии эскалации: `review/question -> chat`.
3. Показать в UI связанный контекст товара и последних ответов.

Критерий готовности:
1. Для любого chat-диалога виден краткий контекст по reviews/questions данного товара.

## Фаза 3 (Недели 5-6): Core-moat context engine

Задачи:
1. Реализовать уровень A/B связности как основной.
2. Реализовать уровень C (probabilistic) как "assist-only".
3. В AI-prompt включить:
 - последние N ответов продавца по этому товару,
 - типовые жалобы/вопросы,
 - запреты/guardrails по публичности канала.

Критерий готовности:
1. AI-draft учитывает историю и не повторяет конфликтующие обещания.
2. Все вероятностные связи имеют confidence и explanation.

## Фаза 4 (Неделя 7): Analytics + fallback контур WBCON

Задачи:
1. Основные operational KPI считать только из WB API-потоков.
2. Добавить fallback-джоб на WBCON только для аналитических дыр.
3. В отчете явно маркировать fallback-метрики и их покрытие.

Критерий готовности:
1. Нет operational-screen, который зависит от WBCON как единственного источника.

## Фаза 5 (Неделя 8): Hardening, QA, rollout

Задачи:
1. Нагрузочные тесты polling/jobs.
2. Контрактные тесты коннекторов WB.
3. E2E smoke по критическим сценариям всех 3 каналов.
4. Canary rollout + мониторинг SLO.

Критерий готовности:
1. Успешный canary без роста критических инцидентов.

---

## 6.1 Delivery backlog по неделям и ролям

## Неделя 1 — Architecture lock

Задачи:
1. `TL/BE`: ADR по `interaction`-модели и cross-channel linking уровня A/B/C.
2. `BE`: SQL миграции для `interaction`, `response_history`, `link_candidates`.
3. `DevOps`: feature flags + staging env для новых коннекторов.
4. `QA`: тест-стратегия (contract/integration/e2e) и quality gates.

Артефакты:
1. ADR документ.
2. Миграции в репозитории.
3. CI job skeleton для contract checks.

## Неделя 2 — WB Feedbacks connector (prod path)

Задачи:
1. `BE`: read endpoints (`count`, `list`, `get by id`) + pagination + retry/backoff.
2. `BE`: write endpoints (`answer`, `edit answer`) + идемпотентность.
3. `BE`: нормализация payload в `interaction(channel=review)`.
4. `QA`: контрактные тесты на реальные/фикстурные payload.

Артефакты:
1. Работающий connector module.
2. Contract tests green.
3. Метрики ingestion в logs/observability.

## Неделя 3 — WB Questions connector (prod path)

Задачи:
1. `BE`: read endpoints (`count`, `list`, `get by id`, unread).
2. `BE`: write endpoint (`patch questions`: view/reject/answer/edit answer).
3. `BE`: нормализация payload в `interaction(channel=question)`.
4. `QA`: regression suite по `review+question`.

Артефакты:
1. Unified ingestion `reviews+questions`.
2. Стабильный SLA/priority pipeline для двух каналов.

## Неделя 4 — Unified Inbox UI (reviews+questions)

Задачи:
1. `FE`: единый список обращений, фильтры, сортировки, bulk triage.
2. `FE`: карточка обращения с контекстом товара и AI draft.
3. `BE/FE`: guardrails (публичность ответа, ограничения текста, шаблоны).
4. `QA`: e2e сценарии основного оператора.

Артефакты:
1. Production-like inbox для high-volume каналов.
2. E2E smoke green (reviews/questions).

## Неделя 5 — Chat unification + escalation

Задачи:
1. `BE`: унификация chat-потока в `interaction(channel=chat)`.
2. `BE`: сценарии эскалации `review/question -> chat`.
3. `FE`: отображение связанных касаний и предыдущих ответов в right panel.
4. `QA`: e2e сценарий эскалации.

Артефакты:
1. Единая очередь из 3 каналов.
2. Рабочий escalation flow.

## Неделя 6 — Context engine A/B

Задачи:
1. `BE/DS`: product-context агрегаты по `nm_id`.
2. `BE`: customer-thread при наличии `customer_id/order_id`.
3. `AI`: prompt-grounding (история ответов + интенты + guardrails).
4. `QA`: offline eval на конфликтные кейсы ответов.

Артефакты:
1. Контекстная панель с доказуемым источником.
2. Улучшение качества AI-драфтов по eval-set.

## Неделя 7 — Analytics + WBCON fallback

Задачи:
1. `AN/BE`: operational KPI только WB API.
2. `BE`: WBCON fallback jobs только для аналитических "дыр".
3. `FE`: маркировка источника метрики (`WB API` / `Fallback`).
4. `QA`: тесты корректности source labeling.

Артефакты:
1. Прозрачный analytics слой.
2. Исключён silent mix разных источников.

## Неделя 8 — Stabilization + rollout

Задачи:
1. `QA/DevOps`: нагрузка, отказоустойчивость, replay/cursor tests.
2. `DevOps`: canary rollout и SLO мониторинг.
3. `PM/TL`: post-canary review, go/no-go.

Артефакты:
1. Canary report.
2. Release checklist и решение о full rollout.

---

## 7. Бэклог задач (исполняемый, по приоритету)

## P0 (обязательно до пилота)

1. `BE`: unified `interaction` schema + миграции.
2. `BE`: WB Feedbacks connector (list/reply/edit/status).
3. `BE`: WB Questions connector (list/reply/edit/status).
4. `BE`: ingestion pipeline + dedup + idempotency keys.
5. `FE`: unified inbox для reviews/questions.
6. `FE`: карточка обращения + AI-draft + guardrails публичности.
7. `QA`: contract tests against WB schemas + integration tests.
8. `OBS`: логи источника данных и качества sync.

## P1 (сильный дифференциатор)

1. `BE`: chat->interaction унификация.
2. `BE`: контекстный движок уровня A/B.
3. `FE`: "история по товару/клиенту" в правой панели.
4. `AI`: prompt-grounding на прошлых ответах и частых причинах.
5. `AN`: dashboard KPI по 3 каналам.

## P2 (после первых пилотов)

1. `BE`: probabilistic linking (уровень C) + confidence thresholds.
2. `FE`: explainability UI для вероятностных связей.
3. `AN`: ROI panel с доверительным диапазоном.
4. `OPS`: авто-алерты по деградации качества ответов.

---

## 8. Тестирование (мировая практика, адаптировано под проект)

1. Unit: нормализация payload и SLA/priority правила.
2. Contract: фиксация WB API контрактов для feedback/question/chat.
3. Integration: API + DB + worker + queue.
4. E2E: сценарии:
 - новый вопрос -> AI-draft -> ответ -> метрика SLA,
 - негативный отзыв -> ответ -> эскалация в чат,
 - чат после ответа на отзыв -> контекст подтянулся.
5. Resilience: ретраи, дедуп, replay курсоров, timeout/downstream errors.
6. Release-gate: без green contract+integration+e2e релиз блокируется.

---

## 9. Риски и решения

1. Риск: дрейф WB API контрактов.
 - Решение: nightly contract check + алерт.
2. Риск: неполные идентификаторы для кросс-канального связывания.
 - Решение: уровни A/B как default, уровень C только assist.
3. Риск: загрязнение операционных KPI fallback-данными.
 - Решение: источник метрики обязателен в data model и UI.
4. Риск: регресс качества AI-ответов при масштабировании.
 - Решение: offline eval set + weekly regression checks.

---

## 10. Definition of Done (релизный минимум)

1. Reviews + Questions работают через WB API как primary source.
2. WBCON используется только в analytics fallback задачах и явно помечен.
3. В inbox есть единая очередь минимум для `review/question/chat`.
4. Для каждого обращения доступны:
 - контекст товара,
 - история релевантных ответов,
 - канал-специфичные guardrails (публично/приватно).
5. E2E сценарии 3 каналов стабильны на staging.

---

## 11. Официальные WB API (проверено 2026-02-11)

1. Questions & Reviews API: `https://dev.wildberries.ru/openapi/user-communication`
2. Buyers Chat API: `https://dev.wildberries.ru/openapi/user-communication#tag/Buyers-chat`
3. Release Notes: `https://dev.wildberries.ru/en/release-notes` (критично отслеживать breaking changes по Customer Communication)

Примечание:
1. Если WB меняет контракты/лимиты, nightly contract check должен блокировать тихие регрессии.
2. В документации и release notes возможны временные расхождения по примерам полей; приоритет у release notes + фактических контрактных тестов.

---

## 12. Identity linking policy (важно для moat)

## 12.1 Можно ли связывать по имени/ФИО?

Короткий ответ: **только как слабый признак, не как ключ связи**.

Почему нельзя использовать ФИО как детерминированный ключ:
1. Неуникальность (`Иван Иванов` встречается часто).
2. Неполные/сокращенные имена (`Мария`, `Алекс.`).
3. Опечатки, транслит, эмодзи/никнеймы.
4. Возможная смена отображаемого имени между каналами.
5. Риск ложного склеивания историй разных покупателей.

Правило:
1. `customer_id/order_id` -> сильный идентификатор (deterministic).
2. `clientName/FIO` -> только вспомогательный сигнал в probabilistic-модели.
3. По совпадению имени нельзя выполнять автоответ, автоэскалацию или автообъединение тредов.

## 12.2 Минимальный scoring для probabilistic linking

Пример весов (первичный):
1. Совпадение `nm_id` в окне 7 дней: `+0.45`
2. Временная близость < 24ч: `+0.20`
3. Семантическая близость интента/проблемы: `+0.20`
4. Совпадение `clientName` (нормализованное): `+0.10`
5. Совпадение доп. признаков (order refs/слова): `+0.05`

Пороги:
1. `>= 0.85`: high confidence (показывать как вероятную связь, без full auto).
2. `0.65-0.84`: medium confidence (только подсказка оператору).
3. `< 0.65`: не показывать в action UI, только в аналитике.

---

## 13. Это moat или нет: как валидируем

## 13.1 Почему это может быть moat

1. Не просто AI-ответ, а **контекстная операционная система** по 3 каналам.
2. Moat строится на накопленной истории ответов/исходов и качестве linking.
3. Чем больше данных и обратной связи, тем точнее приоритизация и драфты.

## 13.2 Когда это НЕ moat

1. Если есть только генерация шаблонных ответов без контекста.
2. Если кросс-канальная связка шумная и не улучшает бизнес-метрики.
3. Если продукт не меняет скорость/качество работы команды.

## 13.3 Метрики moat-эффекта (обязательно в пилотах)

1. `FRT` (first response time) по reviews/questions/chats.
2. `SLA hit rate` по каналам.
3. `Quality pass rate` ответов (внутренний аудит/LLM rubric + выборка ручной проверки).
4. `Repeat issue rate` по одинаковым интентам (должен снижаться).
5. `Operator throughput` (обращений/час) и `time-to-close`.
6. `Linking precision@K` для probabilistic связей (ручная валидация выборки).

Критерий moat-кандидата:
1. Устойчивый прирост операционных метрик минимум на 2-3 итерациях.
2. Улучшение сохраняется после роста объема обращений.

---

## 14. ТЗ на реализацию (добавить в execution)

## 14.1 API contracts (минимум)

1. `GET /interactions` — unified list с фильтрами `channel/status/priority/source`.
2. `GET /interactions/{id}` — карточка обращения + context block.
3. `POST /interactions/{id}/reply` — отправка ответа (канал-специфично).
4. `POST /interactions/{id}/ai-draft` — генерация драфта с explainability.
5. `POST /links/recompute` — пересчет link_candidates.
6. `GET /analytics/communication` — KPI c source labeling.

## 14.2 DB contracts (минимум)

1. Таблица `interactions`.
2. Таблица `response_history`.
3. Таблица `link_candidates`.
4. Таблица `metric_facts` с полем `source`.

## 14.3 Acceptance criteria

1. Любой элемент inbox открывается в карточку < 300ms на p95 (без heavy analytics).
2. Ответ публикуется в WB API с retry и идемпотентностью.
3. Источник данных явно виден в UI и API payload.
4. Probabilistic link всегда содержит `confidence` и `reasoning_signals`.
5. На low confidence нет авто-действий.

---

## Execution Log

### 2026-02-14: Alembic Migrations Setup (Claude)
- **Status:** DONE (files created; runtime test pending — Bash denied in session)
- **Files created:**
  - `apps/chat-center/backend/alembic.ini` — Alembic config, sqlalchemy.url placeholder (overridden by env var in env.py)
  - `apps/chat-center/backend/alembic/README` — standard Alembic readme
  - `apps/chat-center/backend/alembic/env.py` — async-compatible env (aiosqlite + asyncpg), loads DATABASE_URL from .env, imports all models, render_as_batch=True for SQLite
  - `apps/chat-center/backend/alembic/script.py.mako` — migration template (matches async template)
  - `apps/chat-center/backend/alembic/versions/2026_02_14_0001-0001_add_interactions_and_interaction_events.py` — initial migration creating `interactions` and `interaction_events` tables with all indexes, FKs, and unique constraints
- **Files modified:**
  - `apps/chat-center/backend/requirements.txt` — added `aiosqlite==0.20.0` (required for SQLite async driver used in dev)
- **Test results:**
  - `alembic upgrade head` / `alembic downgrade -1` — NOT RUN (Bash tool was denied during session; must be tested manually)
  - Migration file manually verified: columns, types, FKs, indexes, unique constraints all match `app/models/interaction.py` and `app/models/interaction_event.py`
- **Notes:**
  - env.py uses `load_dotenv()` + `os.getenv("DATABASE_URL")` to avoid hardcoded credentials
  - Auto-converts `postgresql://` to `postgresql+asyncpg://` and `sqlite:///` to `sqlite+aiosqlite:///`
  - `render_as_batch=True` enabled in both online and offline modes for SQLite ALTER TABLE compatibility
  - The `metadata` column in interactions uses `sa.Column('metadata', sa.JSON())` matching the model's `Column("metadata", JSON)` definition
  - For prod (PostgreSQL): run `alembic stamp head` on existing DB first if tables already exist, then use `alembic upgrade head` for new deployments
  - For dev (SQLite): run `alembic upgrade head` to create tables from scratch (or keep using `init_db()` for quick resets)
  - Manual test commands:
    ```bash
    cd apps/chat-center/backend
    source venv/bin/activate
    pip install aiosqlite  # if not already installed
    alembic upgrade head      # apply migration
    alembic downgrade -1      # rollback migration
    alembic current           # check current revision
    ```

### 2026-02-14: Contract Tests for WB Feedbacks & Questions Connectors (Claude)
- **Status:** DONE (files created; test execution pending -- Bash denied in session)
- **Files created:**
  - `apps/chat-center/backend/tests/fixtures/wb_api/feedbacks_list.json` -- mock 200 response with 2 feedbacks (Russian text, 5-star and 1-star)
  - `apps/chat-center/backend/tests/fixtures/wb_api/questions_list.json` -- mock 200 response with 2 questions (one unanswered, one with answer)
  - `apps/chat-center/backend/tests/fixtures/wb_api/error_401.json` -- unauthorized error response
  - `apps/chat-center/backend/tests/fixtures/wb_api/error_429.json` -- rate limit error response
  - `apps/chat-center/backend/tests/test_wb_feedbacks_contract.py` -- 11 tests: parse response, empty list, pagination params, answer success (204), 401 auth retry, 429 rate limit retry, timeout retry, timeout exhausted, 502 raises, auth header candidates (raw/bearer/case-insensitive), whitespace strip
  - `apps/chat-center/backend/tests/test_wb_questions_contract.py` -- 12 tests: parse response, answer parsing, pagination params, count unanswered, patch answer, patch wasViewed, 429 retry, 429 triple retry backoff, 401 auth fallback, 401 both fail, auth header candidates (raw/bearer)
- **Mocking strategy:** `unittest.mock.AsyncMock` + `patch("httpx.AsyncClient")` -- no new packages needed (no pytest-httpx/respx)
- **Test results:** NOT RUN (Bash tool was denied during session; must be tested manually)
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  python -m pytest tests/test_wb_feedbacks_contract.py tests/test_wb_questions_contract.py -v
  ```
- **Coverage:**
  - Success paths: list feedbacks/questions, answer feedback (204), patch question (answer/view), count unanswered
  - Error paths: 401 auth retry with header fallback, 429 rate limit with exponential backoff, timeout with retry, 502 immediate raise
  - Auth header logic: raw token -> [raw, Bearer raw], Bearer-prefixed -> [original, raw], case insensitivity, whitespace stripping
  - Pagination: skip/take/isAnswered/order/nmId params verified
- **Notes:**
  - All tests mock at httpx.AsyncClient level (not at connector method level) to verify real connector logic
  - Real `httpx.Response` objects used (with `raise_for_status()`) for authentic HTTP behavior
  - Fixtures use realistic Russian text matching WB API payload structure
  - `asyncio.sleep` patched in retry tests to avoid real delays
  - All tests run fully offline -- zero real API calls

### 2026-02-14: Channel Guardrails (Claude)
- **Status:** DONE (files created; test execution pending -- Bash denied in session)
- **Files created:**
  - `apps/chat-center/backend/app/services/guardrails.py` -- channel-specific guardrails service ported from `scripts/llm_analyzer.py:478-519`. Contains 4 banned phrase lists (AI mentions, promises, blame, dismissive), return trigger detection, channel-specific apply functions (review/question/chat), unified `apply_guardrails()`, and blocking `validate_reply_text()`.
  - `apps/chat-center/backend/tests/test_guardrails.py` -- 37 tests covering: all banned phrase categories, return trigger detection, return mention without trigger, channel-specific differences (review=strict, question=strict, chat=relaxed), edge cases (partial word matching, case sensitivity, empty/None text, multiple violations), and pre-send validation (blocking vs warning severity).
- **Files modified:**
  - `apps/chat-center/backend/app/services/interaction_drafts.py` -- added `guardrail_warnings` field to `DraftResult` dataclass, added `_apply_guardrails_to_draft()` helper, all draft generation paths now run channel guardrails and attach warnings.
  - `apps/chat-center/backend/app/schemas/interaction.py` -- added `guardrail_warnings: List[Dict[str, Any]]` field to `InteractionDraftResponse` schema.
  - `apps/chat-center/backend/app/api/interactions.py` -- (1) draft endpoint now passes `guardrail_warnings` through to response (both cached and fresh); (2) reply endpoint now runs `validate_reply_text()` pre-send validation (HTTP 422 with violation details if blocked).
- **Channel rules:**
  - `review` (PUBLIC): strictest -- all 4 banned phrase categories + unsolicited return check + length checks
  - `question` (PUBLIC): same as review (delegates to `apply_review_guardrails`)
  - `chat` (PRIVATE): relaxed -- only AI mentions blocked (error), blame phrases soft-warned (warning), promises/dismissive allowed
- **Key design decisions:**
  - Guardrails are ADDITIVE at draft stage (warn, don't block) -- warnings attached to `DraftResult.guardrail_warnings`
  - `validate_reply_text()` is the ONLY blocking check -- used in the reply endpoint, returns 422 on error-severity violations
  - Word-boundary regex (`\b`) for short tokens like "бот"/"ИИ" to prevent false positives (e.g., "работа" does not match "бот")
  - Case-insensitive matching throughout
  - None/empty text handled gracefully in all functions
- **Test results:** NOT RUN (Bash tool was denied during session; must be tested manually)
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  python -m pytest tests/test_guardrails.py -v
  ```

### BL-PILOT-005: Sync Observability (metrics + alerting) (2026-02-14)

**Task:** Add structured logging and metrics for sync operations, plus alerting logic for anomalies.

**Files created/modified:**
- **NEW** `apps/chat-center/backend/app/services/sync_metrics.py` -- SyncMetrics dataclass + SyncHealthMonitor + module-level singleton
- **MODIFIED** `apps/chat-center/backend/app/tasks/sync.py` -- `sync_seller_interactions()` now records per-channel SyncMetrics (review, question, chat) + aggregate metrics; emits structured JSON logs; feeds into in-memory ring buffer via `sync_health_monitor`
- **MODIFIED** `apps/chat-center/backend/app/services/interaction_metrics.py` -- `get_ops_alerts()` now appends sync health alerts + `sync_health` dict to response
- **MODIFIED** `apps/chat-center/backend/app/schemas/interaction.py` -- `InteractionOpsAlertsResponse` now includes optional `sync_health: Dict[str, Any]`
- **MODIFIED** `apps/chat-center/backend/app/api/interactions.py` -- `ops_alerts()` endpoint passes `sync_health` through to response
- **NEW** `apps/chat-center/backend/tests/test_sync_metrics.py` -- 30 tests covering SyncMetrics serialization, health check thresholds, alert generation, ring buffer eviction, multi-seller isolation

**Architecture:**
- **Storage:** Option C (structured logging + in-memory ring buffer). No new DB tables, no external deps.
- **SyncMetrics** dataclass captures per-channel metrics (fetched/created/updated/skipped/errors/rate_limited/duration). `.finish()` calculates duration, `.log()` emits JSON at appropriate log level (INFO/WARNING/ERROR). `.apply_ingest_stats()` merges IngestStats dict.
- **SyncHealthMonitor** singleton maintains thread-safe ring buffers (deque maxlen=10) keyed by `{seller_id}:{channel}`. `check_sync_health()` evaluates 4 health signals: sync staleness, error rate, rate limiting, zero-fetch streaks. `get_active_alerts()` returns alert dicts compatible with existing `InteractionOpsAlert` schema.
- **Alert types:** `sync_stale` (>15 min), `sync_errors` (>20% error rate), `sync_rate_limited` (recent 3 syncs), `sync_zero_fetch` (3+ consecutive zero-fetch).
- **Integration:** `get_ops_alerts()` in `interaction_metrics.py` calls `sync_health_monitor.get_active_alerts(seller_id)` and appends to existing alerts list. New `sync_health` field in API response provides raw health status.

**Key design decisions:**
- In-memory only (no Redis dependency) -- suitable for single-process Celery worker. State lost on restart is acceptable for MVP.
- Thread-safe via `threading.Lock` for concurrent Celery workers in prefork mode.
- Ring buffer size of 10 per seller/channel prevents unbounded memory growth.
- Aggregate "all" channel metrics recorded alongside per-channel metrics for dashboard-level views.
- Backward compatible: `sync_health` field is Optional in schema, existing clients unaffected.

**Test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  python -m pytest tests/test_sync_metrics.py -v
  ```

### 2026-02-14: DB Performance Indexes for Interactions (BL-PILOT-004) (Claude)
- **Status:** DONE (files created; migration execution pending)
- **Task:** Add optimized indexes for production-load critical queries (list_interactions, linking, needs_response filter)
- **Analysis of query patterns:**
  - `list_interactions` (main): filters by `seller_id` + optional (channel, status, priority, needs_response, marketplace, source, search), orders by `occurred_at DESC`
  - Ingestion lookups: `(seller_id, marketplace, channel, external_id)` -- already covered by `uq_interactions_identity` UniqueConstraint
  - Linking queries (`interaction_linking.py`): `(seller_id, marketplace, channel != X)` + `(order_id OR customer_id OR nm_id OR product_article)`
- **Existing indexes (migration 0001):**
  - `ix_interactions_id` -- (id)
  - `ix_interactions_seller_id` -- (seller_id)
  - `idx_interactions_channel_status` -- (seller_id, channel, status)
  - `idx_interactions_priority` -- (seller_id, priority, needs_response)
  - `idx_interactions_occurred` -- (seller_id, occurred_at)
  - `idx_interactions_source` -- (seller_id, source)
  - `uq_interactions_identity` -- (seller_id, marketplace, channel, external_id)
- **New indexes added (migration 0002):**
  1. `idx_interactions_list_main` -- (seller_id, occurred_at DESC, needs_response) -- covers main list query with primary sort + common filter
  2. `idx_interactions_linking_nm` -- (seller_id, marketplace, nm_id) -- linking by product
  3. `idx_interactions_linking_customer` -- (seller_id, marketplace, customer_id) -- linking by customer
  4. `idx_interactions_linking_order` -- (seller_id, marketplace, order_id) -- linking by order
  5. `idx_interactions_needs_response` -- (seller_id, needs_response, occurred_at DESC) -- "needs response" filter with recency sort
- **Files created:**
  - `apps/chat-center/backend/alembic/versions/2026_02_14_0002-0002_add_performance_indexes.py` -- migration with idempotent upgrade (checks index existence for both PostgreSQL and SQLite before creating)
- **Files modified:**
  - `apps/chat-center/backend/app/models/interaction.py` -- added 5 new Index entries to `__table_args__` to keep model in sync with migration
- **Key design decisions:**
  - Migration is idempotent: `_index_exists()` checks `pg_indexes` (PostgreSQL) or `sqlite_master` (SQLite) before creating
  - DESC sort on `occurred_at` in composite indexes for optimal ORDER BY performance
  - No existing indexes were duplicated (verified against 0001 migration)
  - Naming convention follows existing pattern: `idx_interactions_<purpose>`
  - Revision chain: `0001` -> `0002`
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  alembic upgrade head     # apply new indexes
  alembic downgrade -1     # rollback to 0001
  alembic current          # verify current revision
  ```

### 2026-02-14: Nightly WB Contract Checks -- BL-PILOT-007 (Claude)
- **Status:** DONE (script created and tested; GitHub Action created)
- **Files created:**
  - `scripts/check_wb_contract.py` -- WB API contract validator with two modes:
    - `offline`: validates fixture files (`feedbacks_list.json`, `questions_list.json`) against schema snapshots
    - `online`: fetches live WB API responses and validates against the same snapshots (requires `--token`)
    - `both`: runs both modes sequentially
    - Exit codes: 0 (pass), 1 (violations), 2 (runtime error)
  - `apps/chat-center/backend/tests/fixtures/wb_api/feedbacks_schema_snapshot.json` -- expected schema for feedbacks API (envelope, required/optional fields, types, productDetails, answerState enum)
  - `apps/chat-center/backend/tests/fixtures/wb_api/questions_schema_snapshot.json` -- expected schema for questions API (envelope, required/optional fields, types, productDetails, answer object with nested required/optional)
  - `.github/workflows/wb-contract-check.yml` -- GitHub Action: daily at 03:00 UTC + manual trigger, offline always runs, online runs only if `WB_API_TOKEN` secret is set
- **Validation checks performed by the script:**
  1. **Required fields** -- verifies all required fields present in each item (feedbacks: id, text, productValuation, createdDate, productDetails; questions: id, text, createdDate, state, productDetails)
  2. **Field types** -- checks each field matches expected Python type from snapshot (str, int, bool, null_or_dict)
  3. **New field detection** -- warns about fields present in response but absent from snapshot (potential API additions)
  4. **Structural diff** -- compares overall response shape against snapshot, detects missing required fields across all items and unexpected new fields
  5. **Nested validation** -- productDetails checked for required nmId/productName; questions answer object checked for required text field when non-null
- **Test results:** PASS (offline mode verified locally)
  ```
  PASS: feedbacks schema validation
  PASS: feedbacks structural diff
  PASS: questions schema validation
  PASS: questions structural diff
  RESULT: PASS -- all contract checks passed
  ```
- **Violation detection verified:** missing fields, wrong types, new unknown fields, broken answer objects -- all correctly detected
- **No new dependencies:** script uses only stdlib (json, argparse, pathlib, sys, os); httpx imported only for online mode (already in requirements)
- **Run commands:**
  ```bash
  python scripts/check_wb_contract.py --mode offline
  python scripts/check_wb_contract.py --mode online --token <WB_TOKEN>
  python scripts/check_wb_contract.py --mode both --token <WB_TOKEN>
  ```

### 2026-02-14: Configurable reply_pending_window_minutes -- BL-PILOT-006 (Claude)
- **Status:** DONE
- **Problem:** `_reply_pending_override()` in `interaction_ingest.py` had `window_minutes=180` hardcoded. Sellers need to configure how long an AgentIQ reply remains in "pending" state while WB moderation processes it.
- **Files created:**
  - `apps/chat-center/backend/tests/test_reply_pending_window.py` -- 9 unit tests covering default window (180 min), custom short/long windows, boundary conditions, non-agentiq source, and missing data
- **Files modified:**
  - `apps/chat-center/backend/app/schemas/settings.py` -- added `GeneralSettings`, `GeneralSettingsResponse`, `GeneralSettingsUpdateRequest` schemas with `reply_pending_window_minutes` field (min=30, max=1440, default=180)
  - `apps/chat-center/backend/app/api/settings.py` -- added `get_seller_setting()` public helper (reads a single field from seller's general settings), added `_general_key()`, added `GET/PUT /api/settings/general` endpoints
  - `apps/chat-center/backend/app/services/interaction_ingest.py` -- added `_DEFAULT_REPLY_PENDING_WINDOW = 180` constant, added `reply_pending_window_minutes` optional param to both `ingest_wb_reviews_to_interactions()` and `ingest_wb_questions_to_interactions()`, both functions now load the setting from DB (via `get_seller_setting()`) if not explicitly passed; both `_reply_pending_override()` calls now pass the resolved window
- **Key design decisions:**
  - Three-level resolution: explicit parameter > seller DB setting > module-level default (180 min)
  - Fully backward compatible: all existing callers pass no explicit window, so they get DB setting or default
  - Validation via Pydantic: min 30 min, max 1440 min (24h), default 180 min
  - Reuses existing `runtime_settings` table with namespace `general_settings_v1:seller:{id}`
  - No circular imports: `interaction_ingest.py` imports from `api/settings.py` (not vice versa)
  - `get_seller_setting()` is a public helper usable by any service needing seller config
- **API endpoints:**
  - `GET /api/settings/general` -- returns current general settings (defaults if not configured)
  - `PUT /api/settings/general` -- updates general settings with validation
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  pytest -v tests/test_reply_pending_window.py
  ```

### 2026-02-14: Rate Limiting + Backoff for WB Connectors -- BL-PILOT-002 (Claude)
- **Status:** DONE (files created; test execution pending -- Bash denied in session)
- **Task:** Add unified rate limiter preventing WB API rate limit violations across all connector calls for a given seller
- **Problem:** WB API has rate limits (~30 req/min). Current connectors have per-request 429 retry with exponential backoff, but no global rate limiter per seller. Multiple concurrent sync tasks for the same seller could overwhelm WB API.
- **Solution (3 layers):**
  1. **Token-bucket rate limiter** (`rate_limiter.py`): per-seller isolation, default 30 RPM, configurable per seller, async-compatible, no external dependencies
  2. **Inter-page delay** in ingestion: 0.5s sleep between paginated API calls (~2 req/sec = 120/min, well within limits)
  3. **Per-seller sync lock** in Celery task: prevents concurrent `sync_seller_interactions` tasks for the same seller
- **Files created:**
  - `apps/chat-center/backend/app/services/rate_limiter.py` -- WBRateLimiter class (token-bucket), singleton `get_rate_limiter()`, per-seller sync lock (`try_acquire_sync_lock`/`release_sync_lock`)
  - `apps/chat-center/backend/tests/test_rate_limiter.py` -- 16 tests: acquire without wait, RPM enforcement, per-seller isolation, custom seller config, bucket reset, concurrent safety, singleton behavior, sync lock acquire/release/isolation/idempotent
- **Files modified:**
  - `apps/chat-center/backend/app/services/interaction_ingest.py` -- added `asyncio` import, `rate_limiter` import, `_INTER_PAGE_DELAY` constant (0.5s), rate limiter acquire + inter-page sleep in both `ingest_wb_reviews_to_interactions` and `ingest_wb_questions_to_interactions` page loops
  - `apps/chat-center/backend/app/tasks/sync.py` -- imported `try_acquire_sync_lock`/`release_sync_lock`, added per-seller sync lock guard at start of `sync_seller_interactions` (skip if already running), added `finally: release_sync_lock()` for cleanup on both success and error paths
  - `apps/chat-center/backend/app/config.py` -- added `WB_RATE_LIMIT_RPM: int = 30` setting
- **Architecture decisions:**
  - In-process token bucket (no Redis): each Celery worker has its own bucket; effective per-seller budget = `RPM / num_workers`; with `worker_prefetch_multiplier=1` (already configured) at most 1 task/worker
  - Rate limiting at ingestion level (not connector internals): simpler, less intrusive, keeps existing per-request 429 retry as second defense layer
  - Inter-page delay is the primary throttle; token bucket is the safety net for burst scenarios
  - Sync lock is non-blocking: if another sync is already running for the seller, the new task logs and returns (no queue buildup)
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  python -m pytest tests/test_rate_limiter.py -v
  ```

### 2026-02-14: Incremental Sync (Claude)
- **Status:** DONE
- **Approach:** Watermark-based (last `occurred_at` per seller+channel)
  - On each sync cycle, the `occurred_at` of the newest fetched record is saved as a watermark
  - On the next cycle, ingestion stops pagination when it encounters records older than the watermark
  - A 2-second overlap buffer prevents records created in the same second from being missed
  - When no watermark exists (first sync), full sync is performed (backward compatible)
  - `force_full_sync` flag on the Celery task allows manual override to ignore watermarks
- **Storage:** `runtime_settings` table, key pattern `sync_watermark:{channel}:{seller_id}`
  - Separate namespace from chat cursor keys (`sync_cursor:...`)
  - Watermark stored as ISO 8601 string (UTC)
- **Files modified:**
  - `apps/chat-center/backend/app/services/interaction_ingest.py` -- added `since_watermark` parameter to both `ingest_wb_reviews_to_interactions()` and `ingest_wb_questions_to_interactions()`; return type changed from `Dict[str, int]` to `IngestStats` (which has `.as_dict()` for backward compat); added watermark tracking (`max_occurred_at`), overlap buffer (`_WATERMARK_OVERLAP_SECONDS`), and early pagination stop when hitting watermark
  - `apps/chat-center/backend/app/tasks/sync.py` -- added `_watermark_key()`, `_load_watermark()`, `_save_watermark()` helpers; modified `sync_seller_interactions` to accept `force_full_sync` flag, load watermarks before ingestion, and save new watermarks after successful ingestion
  - `apps/chat-center/backend/app/api/interactions.py` -- updated sync endpoint callers to use `result.as_dict()` instead of raw dict
  - `apps/chat-center/backend/app/api/auth.py` -- updated direct sync callers to use `result.as_dict()` instead of raw dict
- **Files created:**
  - `apps/chat-center/backend/tests/test_incremental_sync.py` -- 12 tests covering: watermark roundtrip, namespace isolation, overwrite, key format, None/empty noop, IngestStats as_dict backward compat, review stops at watermark, full sync when no watermark, question stops at watermark, overlap buffer edge case, max occurred_at tracking
- **Edge cases handled:**
  - Same-second records: 2-second overlap buffer ensures records created in the same second as the watermark are re-processed (deduplicated by `external_id` unique constraint)
  - Timezone: all watermarks stored and compared in UTC; `_as_utc_dt()` normalizes naive datetimes
  - Missing watermark: triggers full sync (no behavioral change from before)
  - API error during ingestion: watermark is NOT saved (no partial progress), will retry from old watermark next cycle
  - Mixed answer_states: watermark stops apply across both `is_answered=False` and `is_answered=True` passes
- **Manual test commands:**
  ```bash
  cd apps/chat-center/backend
  source venv/bin/activate
  python -m pytest tests/test_incremental_sync.py -v
  ```
