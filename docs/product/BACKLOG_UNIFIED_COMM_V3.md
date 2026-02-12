# Backlog — Unified Inbox v3 (WB: Reviews + Questions + Chats)

**Source of truth UI:** `docs/prototypes/app-screens-v3-ru.html`

## P0 (Demo Blockers)

1. **BL-P0-001: CJM smoke (registration -> connect/skip -> messages) as automated check**
   - Definition:
     - backend hermetic tests cover: register/login/me, connect-marketplace (queue-fail -> error), list interactions, timeline fetch.
     - frontend build must pass.
   - Acceptance:
     - `backend`: `pytest` green without external services.
     - `frontend`: `npm run build` green.
   - Status: DONE (backend `pytest` green; frontend `npm run build` green).

2. **BL-P0-002: Staging demo доступен по веб-URL (не localhost)**
   - Definition:
     - выкатить фронт+бэк на staging (VPS `79.137.175.164`) так, чтобы открыть `/app/` в браузере.
   - Acceptance:
     - URL открывается и проходит CJM (регистрация -> подключение/пропуск -> сообщения).
     - Ошибки синка не залипают в `syncing`, есть retry/continue.
   - Status: DONE (IP staging `79.137.175.164`).

3. **BL-P0-003: Убрать “двойной backend” (API vs Celery) на staging/prod**
   - Problem:
     - сейчас Celery может запускаться из `.../apps/chat-center/backend`, а API из `/opt/agentiq/app` (риск рассинхронизации кода/задач).
   - Acceptance:
     - systemd units (`agentiq-api`, `agentiq-celery`, `agentiq-celery-beat`) используют один и тот же `WorkingDirectory`/кодовую базу.
     - нет restart-loop сервисов, нет “degraded” из-за конфликтов портов.
   - Status: PARTIAL (на staging конфликты портов убраны, но кодовая база всё ещё дублируется в `/opt/agentiq/app/...`).

4. **BL-P0-004: Correct timestamps + seller answers in unified inbox (review/question)**
   - Problem:
     - `occurred_at` для review/question был `NULL` => даты в UI становились “сегодня”.
     - ответ продавца (`answerText` / `answer.text`) не сохранялся => “Отвечено”, но reply пустой.
   - Acceptance:
     - `occurred_at` в БД и в API заполнен реальным временем события.
     - `extra_data.last_reply_text` заполнен для answered items.
   - Status: DONE.

5. **BL-P0-005: Chat history in unified inbox**
   - Problem:
     - для `channel=chat` UI показывал synthetic 1 сообщение, без реального треда.
   - Acceptance:
     - при открытии `chat` interaction UI грузит историю из `/api/messages/chat/{chat_id}`.
   - Status: DONE.

6. **BL-P0-006: Counts in channel tabs reflect real totals (not page size)**
   - Problem:
     - “Каналы: все / Отзывы / Вопросы / Чаты” и “Все/Без ответа/Обработаны” показывали `len(page)` вместо total.
   - Acceptance:
     - счётчики берутся из `GET /api/interactions/metrics/quality` pipeline totals.
   - Status: DONE.

7. **BL-P0-007: Fix staging static assets layout for `/app/`**
   - Problem:
     - Vite build references `/assets/*`, но ассеты лежали под `/app/assets/*` => 404.
   - Acceptance:
     - на staging `/assets/*` отдаётся из `/var/www/agentiq/assets/*`, `/app/` из `/var/www/agentiq/app/index.html`.
   - Status: DONE.

## P1 (Записано из “следующие шаги”)

1. **BL-P1-001: Analytics mode switch (ops/full) по v3**
   - Notes:
     - сейчас `Операционный` — рабочий (read-only), `Полный` — disabled.
   - Acceptance:
     - `Полный` режим включается в UI без редизайна и показывает дополнительные блоки (revenue/context/attribution) с явной маркировкой источников данных.

2. **BL-P1-002: Settings screen v3 (статически + минимальные API)**
   - Scope:
     - `Подключения`, `AI-ассистент`, `Профиль` по структуре v3.
   - Acceptance:
     - экраны соответствуют прототипу, состояния `loading/error/success` подключены.

3. **BL-P1-003: Promo screen v3 (help panel + хранение)**
   - Scope:
     - промокоды: ввод/список/пометка “где используется”, help slide-out panel по v3 паттерну.
   - Acceptance:
     - данные сохраняются на backend (runtime_settings / отдельная таблица), отображаются в UI, не ломают сообщения.

## P2 (Усиление демо)

1. **BL-P2-001: Demo data при “Пропустить подключение”**
   - Goal:
     - в skip-mode показывать демо-поток обращений, чтобы CJM выглядел “живым”.
   - Acceptance:
     - при skip: UI не пустой, есть демо-треды (review/question/chat), аналитика показывает демо-метрики (с яркой пометкой “demo”).

2. **BL-P2-002: E2E (Playwright) smoke на CJM**
   - Scope:
     - headless: register -> connect/skip -> messages open -> analytics open.
   - Acceptance:
     - 1 команда запуска, green в CI/stage.
