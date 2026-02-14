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
| 10 | IDEA | Auto-reply на позитив (= BL-POST-007) |
| 11 | BUG | ✅ FIXED — дубликат #2 |
| 12 | IDEA | ✅ DONE — Статика для demo dashboard |
| 13 | TODO | ✅ DONE — CJM flow проверен, всё работает |
| 14 | UX | ✅ DONE — дубликат #9 (промокоды из меню в настройки) |
| 15 | BUG | OPEN — фантомные отзывы (rating-only без текста) + sync не обновляет статус |
| 16 | BUG | OPEN — ответы продавца на отзывы не загружаются (max_items budget) |
| 17 | INFO | DOCUMENTED — правила синхронизации 300/300/500, frontend 50/page |
| 18 | UX | OPEN — sidebar badge скрыть в активном workspace, показывать urgent |
| 19 | BUG | ✅ FIXED — при переключении каналов данные пропадают (per-channel cache) |

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

15) кажется отзывы и даты некорректно приходят, в карточке последний отзыв — Евгений, 11 октября 2025, а в интерфейсе — 14 февраля 2026 г. Николай — **BUG (2026-02-15):** Проверка через WB seller API: Николай 14.02.2026 — реальный отзыв в API (`id=NWc8J6hS4hFHjJmWfLvK`), но это **rating-only** (5★ без текста). WB не показывает такие отзывы на публичной карточке. Евгений (окт 2025) — отзыв на другой nmId в том же `imtId=331294168` (WB группирует по модели). Два подбага: (a) показываем rating-only отзывы без текста как обычные — нужно фильтровать или помечать; (b) sync не обновляет статус отзыва — Николай был `isAnswered=False` при первом fetch, WB позже пометил `isAnswered=True`, но re-sync не обновляет уже виденные записи.

16) а ответы на отзывы парсятся вообще? — **BUG (2026-02-15):** Код парсинга ответов написан и работает (`interaction_ingest.py:320-378`). Для **вопросов** — ок (316 из 330 с ответами). Для **отзывов** — ответы НЕ загружаются на проде. Причина: `max_items=300` бюджет на sync. У продавца 608 неотвеченных отзывов, sync сначала грузит unanswered (608 > 300 → бюджет исчерпан), до answered отзывов очередь не доходит. Fix: (1) увеличить `max_items` для reviews, (2) разделить бюджет для answered/unanswered, (3) починить watermarks чтобы incremental sync не перезагружал уже виденные записи.

17) а когда ключ вводим от кабинета, какие правила синхронизации? — **DOCUMENTED (2026-02-15):** Initial sync = те же лимиты что periodic, спец режима нет. Правила: **300 reviews** + **300 questions** + **500 chats** per sync cycle. WB API страницами по 100. Frontend показывает **50/page** (max 100). Периодичность: chats каждые 30 сек, reviews+questions каждые 5 мин. Watermarks (incremental sync) — код написан, но для reviews/questions watermarks не сохраняются → каждый цикл re-fetch с нуля.

18) в меню есть сообщения и бейдж 50 — не нужен в активном чат-центре, показывать в других разделах — **UX (2026-02-15):** Badge = `chats.filter(c => c.unread_count > 0).length` (динамический, не хардкод). Проблемы: (1) всегда виден, даже при count=0, (2) показывается в активном workspace. Fix: скрыть при `activeWorkspace === 'messages'`, показывать urgent count (`sla_priority === 'urgent'` + SLA overdue) вместо unread. Файлы: `App.tsx:956,1004,1626`.
