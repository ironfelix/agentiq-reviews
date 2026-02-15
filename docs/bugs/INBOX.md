# INBOX — Raw Notes (unstructured)

Last updated: 2026-02-15
Status: ACTIVE (triage queue)

Сюда можно скидывать заметки **как есть**, без структуры. Я сам буду:
- фильтровать (bug vs idea vs ux vs copy),
- присваивать ID,
- переносить в `docs/bugs/БАГИ.md` (структурный лог),
- при необходимости прокидывать в backlog/доки модулей.

## Как писать (минимально)

Одна заметка = одна строка (или блок), любая форма ок. Желательно указывать “Где” и прикладывать скрин.

Примеры:

- `2026-02-13` | `Workspace > Сообщения > Interaction details` | “Кнопка Reply иногда неактивна после sync” | `Screenshot ...png`
- `Landing` | “Слишком много текста в первом экране, хочется короче (идея)”

---

## Сводка

| # | Тип | Статус |
|---|-----|--------|
| 1 | BUG | ✅ FIXED — tab flicker (CSS show/hide) |
| 2 | BUG | ✅ FIXED — WB key lost on re-login |
| 3 | BUG | ✅ FIXED — дубликат #1 |
| 4 | BUG | ✅ FIXED — filter count mismatch |
| 5 | BUG | ✅ FIXED — дубликат #4 |
| 6 | IDEA | Табы как в Telegram |
| 7 | IDEA | Pre-generate AI drafts |
| 8 | BUG | ✅ FIXED — лимит 300→500 символов (ai_analyzer.py) |
| 9 | UX | ✅ DONE — Промокоды перенесены в Settings как таб |
| 10 | IDEA | ✅ DONE — Auto-reply на позитив: реализован сервис + toggle в настройках AI |
| 11 | BUG | ✅ FIXED — дубликат #2 |
| 12 | IDEA | ✅ DONE — Статика для demo dashboard |
| 13 | TODO | ✅ DONE — CJM flow проверен, всё работает |
| 14 | UX | ✅ DONE — дубликат #9 (промокоды из меню в настройки) |
| 15 | BUG | ✅ FIXED — rating-only без текста: needs_response=false + answer_state trust |
| 16 | BUG | ✅ FIXED — answered reviews: dynamic limit 1500 full / 500 incremental, per-state budget |
| 17 | INFO | DOCUMENTED — правила синхронизации 1500/1500/500 full, 500/500/500 incremental |
| 18 | UX | ✅ FIXED — sidebar badge: urgent count, скрыт в messages workspace |
| 20 | RESEARCH | ✅ DONE — rating-only отзывы НЕ видны на карточке, ответ тоже не виден |
| 19 | BUG | ✅ FIXED — при переключении каналов данные пропадают (per-channel cache) |
| 21 | BUG | ✅ FIXED — Worker crash on startup: race condition в create_all |
| 22 | BUG | ✅ FIXED — 486 questions с NULL occurred_at |
| 23 | BUG | ✅ FIXED — Ghost sellers генерируют 1080 warnings/hour |
| 24 | BUG | ✅ FIXED — Дубли nginx .bak configs |
| 25 | BUG | ✅ FIXED — bcrypt deprecation warning |
| 26 | BUG | ✅ FIXED — customer_profiles пусто → backfill |
| 27 | BUG | ✅ FIXED — Sellers 3, 12, 17 дубликаты |
| 28 | BUG | ✅ FIXED — 3-sec retry при пустом ответе после синка |
| 29 | BUG | ✅ FIXED — overflow-x:hidden + убрана min-width:300px на мобилке |
| 30 | BUG | ✅ FIXED — dots: логика на chat_status (waiting/responded/closed), не rating |
| 31 | BUG | ✅ FIXED — badge показывает total с серым фоном когда needs=0 |
| 32 | BUG | ✅ FIXED — универсальный fallback «Покупатель» для всех каналов |
| 33 | UX | ✅ FIXED — Info кнопка в header чата + context back на мобилке |
| 34 | UX | ✅ FIXED — FolderStrip перемещён выше search wrapper |
| 35 | PERF | ✅ FIXED — отложен polling аналитики до активации таба, интервалы 30/60с |
| 36 | PERF | ✅ FIXED — instant show кэшированных сообщений + async подгрузка свежих |
| 37 | PERF | ✅ FIXED — smart comparison (id+updated_at) предотвращает лишние ре-рендеры |
| 38 | AI | ✅ FIXED — переписан промпт для вопросов: дружелюбный, помогающий тон |
| 39 | BUG | ✅ FIXED — snippet duplication: strip channel prefix from subject, use extra_data.product_name for chats |
| 40 | BUG | ✅ FIXED — dot colors: 4849 answered reviews без last_reply_text → fallback на needs_response |
| 41 | DATA | ✅ FIXED — 4 sellers синкали один WB кабинет. Оставлен seller 17 (ivan2), деактивированы 3/12/18 |
| 42 | FEAT | ✅ DONE — Settings page включена в sidebar + mobile nav, Dashboard placeholder |
| 43 | PERF | ✅ FIXED — Progressive loading: sessionStorage cache (30-min TTL), instant restore без спиннера, background pagination 300ms, Apple Mail sync banner |
| 44 | UX | ✅ FIXED — Promo codes help panel: неполный контент (нет таблиц, callout, ссылки) |
| 45 | BUG | ✅ FIXED — Mobile chat: header съезжает за app-header |
| 46 | BUG | ✅ FIXED — Sync indicator не показывается при периодической синхронизации (30 сек) |
| 47 | UX | ✅ FIXED — Settings navigation: reload сбрасывает активный раздел на Подключения |
| 48 | PERF | ✅ FIXED — Секции flash на reload: isSame, CSS animation, localStorage cache |
| 49 | SEC | ✅ FIXED — 6 critical security findings (audit 36 total, docs created) |

---

## Notes

<!-- Пиши ниже -->

1) ~~когда перключаю табы - вижу как моргает верстка и вижу другую верстку с кнопкой~~ **FIXED (2026-02-14):** Replaced conditional rendering (ternary chain) with CSS show/hide in `App.tsx`. All workspace pages are now rendered simultaneously and toggled via `display:none` instead of mount/unmount. No more DOM rebuild flicker or loading-state flash.

2) ~~ввожу ключ, выхожу и снова ключ запраживается, почему?~~ **FIXED (2026-02-15):** Login/register response (`SellerAuthInfo`) did not include `has_api_credentials`, so frontend always showed onboarding. Fix: added `has_api_credentials`, `sync_status`, `sync_error`, `last_sync_at` to `SellerAuthInfo` schema and both auth endpoints. See execution log in `UNIFIED_COMM_PLAN_V3_WB_FIRST.md`.

3) ~~моргания при переходе из табов - остались, это реакт или в чём проблема?~~ **FIXED (2026-02-14):** Same root cause as #1. React was mounting/unmounting page components on every tab switch, causing useEffect hooks to re-fire (showing loading states) and DOM to rebuild (causing layout shift). Fix: CSS show/hide instead of conditional rendering.

4) ~~смотрю вкладки, и опять открываю чаты - а там(39) - вот Нет обращений по фильтру / Нет обработанных обращений~~ **FIXED (2026-02-14):** Root cause: bug #1/#3 fix replaced conditional rendering with CSS show/hide, so ChatList never unmounts. Local filter state (`activeFilter`, `activeChannel`) persisted across workspace switches. If user had "Обработаны" or "Без ответа" selected, navigated to Analytics/Settings, and returned -- the stale filter produced zero matching items while the pipeline badge showed the full count. Fix: (1) ChatList receives `isActive` prop and resets filters to default ('all'/'all') when it transitions from inactive to active; (2) App.tsx effect resets `filters` to `{}` and restores `interactions` from the 'all|all' cache on workspace switch to messages. Files: `App.tsx` (workspace-change effect), `ChatList.tsx` (isActive prop + prevIsActiveRef reset effect).

5) ~~если в табе переключаюсь на вопросы там 163 цифры, но пишет - нет обращений по фильтру (понял он совмещает фильтры с двух табов)~~ **FIXED (2026-02-14):** Same root cause as #4 -- filter state persisting across workspace switches. Fixed by the same isActive-reset mechanism.

6) вообще табы стоит переделать, мне нравится как сделано в telegram сверху табы, слева папки (в нашем случае чаты вопросы отзывы как папки) — **IDEA/UX**, добавить в backlog post-pilot.

7) генерацию ии рекомендации можно ли сделать до перехода в чат? — **IDEA/UX**, pre-generate AI drafts при sync, не по клику. Добавить в backlog.

8) ~~почему тут в конце `...` в AI рекомендации — текст обрезается~~ **FIXED (2026-02-15):** Backend hardcoded 300-char truncation in `ai_analyzer.py` (line 498). LLM prompt also said "max 300 chars". Fix: increased both to 500 chars. Frontend CSS was fine (no text-overflow: ellipsis).

9) ~~промокоды из меню мы хотели убрать в настройки - они в меню не нужны~~ **DONE (2026-02-15):** Removed Промокоды from sidebar and bottom nav. Added as 4th tab in SettingsPage (Подключения | AI-ассистент | **Промокоды** | Профиль). Files: `App.tsx` (removed promo workspace, sidebar button, bottom nav button, import), `SettingsPage.tsx` (added promo tab + PromoCodes render).

10) Авто-ответы на позитив - вижу, как идея, добавить там на какие звезды отвечать, на какие писать в чат (есть такая опция у WB) — **IDEA**, = BL-POST-007 (Auto-response mode). Уже в backlog.

11) ~~после логаута снова просит ключ при входе~~ — **= дубликат #2, FIXED (2026-02-15).**

12) ~~в демо-дашборд можно было бы статику загрузить, сейчас туда загружаются данные по апи~~ **DONE (2026-02-15):** Created `src/demo/analyticsData.ts` with realistic demo data for all 4 analytics endpoints (quality metrics, history, ops alerts, pilot readiness). In demo mode (`connectionSkipped && !has_api_credentials`): static data is auto-seeded via useEffect, API polling disabled. No API calls wasted.

13) ~~проверить логику работы CJM~~ **DONE (2026-02-15):** Full CJM verified on staging (`agentiq.ru`): register (201) → login (200) → seed-demo (200, 12 interactions) → interactions list (200) → interaction detail (200) → timeline (200, cross-channel linking works) → quality metrics (200) → ops-alerts (200) → pilot-readiness (200). All endpoints working correctly.

14) ~~из меню убрать пункт промокоды, убрать в настройки~~ — **= дубликат #9, DONE (2026-02-15).**

15) ~~кажется отзывы и даты некорректно приходят~~ **FIXED (2026-02-15):** Два подбага исправлены: (a) rating-only отзывы (без текста) теперь `needs_response=false` — не попадают в очередь; (b) WB API возвращает `answerText=null` даже для `isAnswered=true` — теперь используем `answer_state` (параметр API pass) как primary signal. Файл: `interaction_ingest.py:326-333`.

16) ~~а ответы на отзывы парсятся вообще?~~ **FIXED (2026-02-15):** Три исправления: (1) per-state budget — каждый `answer_state` (unanswered/answered) получает отдельный лимит вместо общего; (2) dynamic limits — full sync 1500/state, incremental 500/state (`sync.py:371,404`); (3) WB API `answerText=null` workaround (см. #15). Результат: 1213 reviews загружены (909 новых answered + 304 updated), все `status=responded`.

17) а когда ключ вводим от кабинета, какие правила синхронизации? — **DOCUMENTED (2026-02-15):** Full sync (first run, no watermark): **1500 reviews/state** + **1500 questions/state** + **500 chats**. Incremental (with watermark): **500/state** + **500/state** + **500 chats**. WB API страницами по 100. Frontend: **50/page** (max 100). Периодичность: chats каждые 30 сек, reviews+questions каждые 5 мин. Watermarks сохраняются в `runtime_settings` для incremental sync.

18) ~~в меню есть сообщения и бейдж 50~~ — **FIXED (2026-02-15):** Badge теперь показывает urgent count, скрыт в messages workspace и при count=0. Файлы: `App.tsx`.

20) ~~ответ на отзыв без комментария (rating-only) — виден ли на карточке WB?~~ — **DONE (2026-02-15):** Исследование подтвердило: rating-only отзывы (только оценка, без текста/фото/видео) **НЕ отображаются** на публичной карточке товара. WB показывает max 1000 "непустых" отзывов. Rating-only автоматически архивируются в API (`answerState` auto-archive). Ответ продавца виден только автору в ЛК. Наша логика `needs_response=false` корректна. Источники: [WB Official](https://seller.wildberries.ru/instructions/ru/ru/material/customer-reviews), [Moneyplace](https://moneyplace.io/news/na-wildberries-vyroslo-chislo-otzyvov-bez-teksta/).


### Новые после демо 2 (2026-02-15):

21) ~~Worker crash при рестарте (race condition)~~ **FIXED (2026-02-15):** 2 uvicorn workers одновременно вызывают `Base.metadata.create_all()` → `UniqueViolationError`. Fix: try/except в `main.py:82-86`.

22) ~~486 вопросов с NULL occurred_at~~ **FIXED (2026-02-15):** Все вопросы имели `occurred_at=NULL` → неправильная сортировка. Fix: backfill `UPDATE interactions SET occurred_at = created_at WHERE occurred_at IS NULL`.

23) ~~Ghost sellers генерируют 1080 warnings/hour~~ **FIXED (2026-02-15):** 12 тестовых продавцов деактивированы. Осталось 2 активных (3 + 14).

24) ~~Дубли nginx .bak configs~~ **FIXED (2026-02-15):** `sudo rm /etc/nginx/sites-enabled/agentiq.bak*`.

25) ~~bcrypt deprecation warning~~ **FIXED (2026-02-15):** Downgrade bcrypt → 4.0.1 (совместим с passlib).

26) ~~customer_profiles пусто~~ **FIXED (2026-02-15):** Backfill SQL → 12 профилей создано.

27) ~~Sellers 3, 12, 17 дубликаты~~ **FIXED (2026-02-15):** Деактивированы 12, 17. Оставлен seller 3.

### Новые после демо 1 (от пользователя):

28) ~~сообщения не показываются после синка, появляются через 30 сек~~ **FIXED (2026-02-15):** Добавлен 3-sec retry в `fetchInteractions` когда initial fetch возвращает 0 items. Файл: `App.tsx`.

29) ~~сломана верстка в мобилке — экран листается влево-вправо~~ **FIXED (2026-02-15):** `html { overflow: hidden }`, `overflow-x: hidden` на body и `.app-shell-page`, убран `min-width: 300px` из `.product-context` на мобилке, добавлен `min-width: 0` на панели. Файл: `index.css`.

30) ~~оценка срочности dots некорректная: на 5★ без ответа всё зелёное~~ **FIXED (2026-02-15):** Заменена логика `needs_response` boolean → полная проверка `chat_status` (waiting/responded/client-replied/auto-response/closed) по наличию reply_text и статусу. Файл: `App.tsx`.

31) ~~при переключении таба спиннер + badge 0 в отзывах~~ **FIXED (2026-02-15):** Badge теперь показывает `total` count с серым фоном когда `needs_response=0`. `getBadgeCount` возвращает `{needs, total}`. Файлы: `FolderStrip.tsx`, `index.css`.

32) ~~в вопросах «автор вопроса» вместо имени клиента~~ **FIXED (2026-02-15):** Универсальный fallback «Покупатель» для всех каналов. Файл: `App.tsx`.

33) ~~мобильная навигация chatlist→window→context panel~~ **FIXED (2026-02-15):** Добавлена Info кнопка в header чата → открывает context panel. Back кнопка в context → возврат к чату. `data-mobile-view` переключает панели. Файлы: `App.tsx`, `ChatWindow.tsx`, `index.css`.

34) ~~папки (каналы) должны быть над поиском~~ **FIXED (2026-02-15):** FolderStrip перемещён выше search wrapper в ChatList. Файл: `ChatList.tsx`.

35) ~~очень долго всё загружается~~ **FIXED (2026-02-15):** Отложен polling аналитики (qualityHistory, opsAlerts, pilotReadiness) до активации таба. Интервалы увеличены: qualityMetrics 15→30с, analytics 30→60с. Файл: `App.tsx`.
Так много ошибок делаешь. Может, какие-то доп. тесты нужны? А почему так происходит? 
36) ~~загрузка чата вместе с AI рекомендацией~~ **FIXED (2026-02-15):** Instant show кэшированных сообщений из `interactionCacheRef` для не-chat каналов, свежие данные загружаются async. Файл: `App.tsx`.

37) ~~коммуникации грузятся заново каждый раз~~ **FIXED (2026-02-15):** Smart comparison (id + updated_at + needs_response) перед обновлением `interactionCache`, предотвращает лишние ре-рендеры когда данные не изменились. Файл: `App.tsx`.

38) ~~ответы на вопросы «посылающие» клиентов~~ **FIXED (2026-02-15):** Переписан `QUESTION_DRAFT_SYSTEM` промпт: добавлен принцип «ПОМОГИ ПОКУПАТЕЛЮ», эмпатия, запрет на отсылающие фразы. Fallback текст тоже обновлён. Файлы: `ai_analyzer.py`, `interaction_drafts.py`.

новые:
39) ~~в сниппетах в чатлисте снова пишем чат чат с покупателем, отзыв отзыв, вопрос вопрос по товару~~ **FIXED (2026-02-15):** `App.tsx:85-89` использовал fallback "Отзыв по товару"/"Вопрос по товару"/"Чат покупателя", а `ChatList.tsx:229-234` уже показывает channel label "Отзыв"/"Вопрос"/"Чат" → дубликат. Fix: fallback заменён на `Арт. {nm_id}` или null (пустая строка пропускается). Теперь: "Отзыв · Арт. 123456 · Ожидает ответа".

40) ~~цвета dots сломаны~~ **FIXED (2026-02-15):** Root cause: 4849 из 4853 answered reviews не имели `last_reply_text` в extra_data (WB API `isAnswered=true`, но `answerText` пустой). Frontend derivation: `hasReply=false + needs_response=false → 'waiting'` (жёлтый) вместо `'responded'` (зелёный). Fix: добавлен fallback `if (!interaction.needs_response) return 'responded'` в `App.tsx:150`. Теперь все answered reviews/questions показывают зелёный dot.

### Новые после демо 3 (2026-02-15):

44) ~~Promo codes help panel: неполный контент на проде~~ **FIXED (2026-02-15):** Help panel промокодов показывал только 3 секции вместо полного контента. Добавлено: (1) СОЗДАНИЕ с путём в ЛК WB, (2) ПАРАМЕТРЫ таблица (скидка/длительность/макс.акций/код/использование), (3) КАК ПРИМЕНЯЕТСЯ, (4) жёлтый callout "Важно" со списком правил WB, (5) ЧАТЫ VS ОТЗЫВЫ таблица сравнения, (6) внешняя ссылка на инструкцию WB. Файлы: `PromoCodes.tsx` (+60 строк контент), `index.css` (+58 строк стили для таблиц/callout/ссылки). Commit: `e4bba04`.

45) ~~Mobile chat: header съезжает за app-header~~ **FIXED (2026-02-15):** На mobile при открытии чата `.chat-window` имел `position:absolute; top:0`, из-за чего chat-header скрывался за app-header (56px). Fix: изменён `top: 56px` и `height: calc(100dvh - 56px - 56px)` для `.chat-center[data-mobile-view="chat"] .chat-window`. Файл: `index.css:2203-2206`. Commit: `e4bba04`.

46) ~~Sync indicator не показывается при периодической синхронизации~~ **FIXED (2026-02-15):** Apple Mail-style sync banner внизу чат-листа показывался только при первой загрузке (loadingProgress.loaded < total), но не при фоновой синхронизации каждые 30 сек. Root cause: при периодической синхронизации `allLoaded=true` и `loadingProgress=null`. Fix: добавлено условие `syncStatus === 'syncing'` OR `loadingProgress` для отображения banner. Теперь показывается "Синхронизация..." при фоновой синхронизации. Файл: `ChatList.tsx:645-656`. Commit: `e4bba04`.

47) ~~Settings navigation: reload сбрасывает активный раздел~~ **FIXED (2026-02-15):** При reload страницы настроек пользователь возвращался к разделу "Подключения" вместо последнего активного (например, "Промокоды"). Root cause: `tab` state хранился локально и сбрасывался в `'connections'` при mount. Fix: (1) добавлена функция `getInitialTab()` которая читает URL hash (`#settings-promo`) при mount, (2) функция `changeTab()` обновляет state + window.location.hash при переключении табов. Теперь активный раздел сохраняется в URL и восстанавливается после reload. Файл: `SettingsPage.tsx`. Commit: `e4bba04`.

### Security & Performance (2026-02-15, night):

48) ~~Секции «В работе» / «Ожидают ответа» мерцают при каждом reload~~ **FIXED (2026-02-15):** Три итерации фикса: (1) smart isSame comparison по визуальным полям (priority, status, needs_response, text, chat_status, ai_draft.sla_priority) вместо `updated_at`; (2) убрана CSS анимация `.queue-section` (`queueSectionIn`); (3) `sessionStorage` → `localStorage` для interaction cache (сохраняется между закрытиями tab / iOS eviction). Файлы: `App.tsx`, `index.css`.

49) ~~Security audit: 6 CRITICAL findings~~ **FIXED (2026-02-15):** Полный security audit проекта (36 findings). 6 критических исправлены: (C-01) startup validation SECRET_KEY, (C-02) `datetime.utcnow()` → `datetime.now(timezone.utc)` в JWT, (C-03) CORS methods/headers restricted, (C-04) max_length на text inputs, (C-05) sentry-test endpoint удалён, (C-06) IDOR fix — `get_optional_seller` → `get_current_seller` на resource endpoints. 458 тестов прошли. Файлы: `main.py`, `auth.py`, `chats.py`, `messages.py`, `schemas/chat.py`, `schemas/message.py`. Доки: `docs/security/SECURITY_AUDIT.md`, `docs/security/SECURITY_REVIEW_PROCESS.md`.