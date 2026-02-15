# AgentIQ Plan v3 — Unified Communications (Reviews + Questions + Chats)

**Дата:** 2026-02-11  
**Статус:** Draft for execution  
**Основа UI:** `docs/prototypes/app-screens-v3-ru.html`  
**Текущий прод-контур:** `agentiq.ru/app` (`apps/chat-center`) + `apps/reviews`

---

## 1. Цель плана

Собрать единый продуктовый контур коммуникаций WB с приоритетом по объему и эффекту:

1. `Отзывы` (высокий объем, влияние на рейтинг и доверие)
2. `Вопросы` (pre-purchase, влияние на конверсию)
3. `Чаты` (меньше объем, выше точечная критичность + влияение на рейтиг если вопрос решили хорошо, и конверсию, можем коммуникации делать с клиентов в период открытого окна чата)

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

## 4.3 Уровень C (вероятностное связывание, только с confidence)

Если явного customer_id нет:
1. Используем вероятностное матчинг-правило по `(nm_id + time proximity + текстовые сигналы + лексика претензии)`.
2. Связку показываем как `вероятная`, с confidence.
3. Автодействия запрещены при confidence ниже порога.

Ограничение:
1. Это не источник "истины", только вспомогательная аналитика.

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

Примечание:
1. Если WB меняет контракты/лимиты, nightly contract check должен блокировать тихие регрессии.
