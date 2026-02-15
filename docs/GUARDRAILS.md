# AgentIQ Guardrails — Единая документация

**Last updated:** 2026-02-14
**Status:** implemented (partial — scenario engine in progress)

## Оглавление

1. [Обзор системы guardrails](#1-обзор-системы-guardrails)
2. [Content Guardrails — Banned Phrases](#2-content-guardrails--banned-phrases)
3. [Safety Policies (три группы)](#3-safety-policies-три-группы)
4. [Action Guardrails — Auto-Action Policy](#4-action-guardrails--auto-action-policy)
5. [Format & Limits](#5-format--limits)
6. [Escalation Rules](#6-escalation-rules)
7. [Validation Pipeline](#7-validation-pipeline)
8. [Source Files Reference](#8-source-files-reference)

---

## 1. Обзор системы guardrails

Система guardrails AgentIQ работает на трёх уровнях:

### 1.1 Content Guardrails
Проверка текста ответов на запрещённые фразы, обещания, blame language, упоминания AI. Различные правила для публичных каналов (reviews, questions) и приватных (chat).

### 1.2 Action Guardrails
Определение, когда AI может автоматически отправить ответ (auto-action), а когда требуется ассистирование человека (assist-only). Основано на типе линковки (deterministic/probabilistic) и уровне уверенности (confidence).

### 1.3 Audit Trail
Обязательное логирование всех AI-генераций: timestamp, policy_version, confidence, link_type, action_mode, violations, warnings. Низкая уверенность или нарушения политик блокируют авто-отправку.

---

## 2. Content Guardrails — Banned Phrases

### 2.1 Категории запрещённых фраз

| Категория | Фразы | Severity | Причина запрета |
|-----------|-------|----------|-----------------|
| **ai_mention** | "ИИ", "бот", "нейросеть", "GPT", "ChatGPT", "автоматический ответ", "искусственный интеллект", "нейронная сеть", "ИИ-ответ", "ии-ответ", "ИИ ответ", "бот-ответ", "бот ответ", "нейросет" | error | Раскрытие использования AI подрывает доверие клиента |
| **promises** | "вернём деньги", "вернем деньги", "гарантируем возврат", "гарантируем замену", "полный возврат", "бесплатную замену", "бесплатная замена", "компенсируем", "компенсация" | error | Продавец не может гарантировать результат модерации WB |
| **blame** | "вы неправильно", "вы не так", "ваша вина", "сами виноваты", "вы ошиблись", "ваша ошибка" | error (public), warning (chat) | Обвинение клиента провоцирует эскалацию конфликта |
| **dismissive** | "обратитесь в поддержку", "напишите в поддержку" | error (public), not checked (chat) | Воспринимается как отказ помочь, перекладывание ответственности |

### 2.2 Правила по каналам

| Канал | ai_mention | promises | blame | dismissive | return_logic | length_checks |
|-------|------------|----------|-------|------------|--------------|---------------|
| **review** (public) | error | error | error | error | strict | yes |
| **question** (public) | error | error | error | error | strict | yes |
| **chat** (private) | error | not checked | warning | not checked | conditional | yes |
| **unknown** | defaults to review (strictest) | | | | | |

**Примечание:** В чатах blame фразы вызывают warning (мягкое предупреждение), но не блокируют отправку. Promises и dismissive не проверяются в чатах, т.к. там возможен более свободный диалог.

### 2.3 Условные правила

#### 2.3.1 Return/Refund Logic — Only by Trigger

**Для публичных каналов (reviews, questions):**
- Упоминание возврата/замены разрешено ТОЛЬКО если клиент явно упомянул одно из триггерных слов: "возврат", "вернуть", "замена", "заменить", "обменять", "обмен"
- Если в ответе есть паттерны ["возврат", "вернуть", "вернём", "вернем", "замен", "обмен"], но в исходном тексте клиента НЕТ триггерного слова → **error**
- Причина: продавец не должен первым предлагать возврат там, где клиент не спрашивал

**Для чатов (intent-based logic):**

| Intent класс | Return/Refund допустимы? | Условия |
|--------------|--------------------------|---------|
| **return_request** | Да | Клиент явно спросил про возврат/обмен |
| **defect_complaint** | Да, если дефект подтверждён | Только для критичных дефектов (не minor cosmetic) |
| **expectation_mismatch** | Нет (unless explicit ask) | Предложить доп.информацию, не возврат |
| **sizing_issue** | Да, если клиент спрашивает | Сначала предложить размерную сетку |
| **delivery_issue** | Нет | Направить к WB Support |
| **general_inquiry** | Нет | Информационный ответ |
| **praise** | Нет | Благодарность |
| **spam** | Нет | Игнорировать |

#### 2.3.2 Fashion-Specific Rules
- Для одежды/обуви при sizing issues: сначала предложить размерную сетку/таблицу замеров
- Для косметики/ухода при аллергии: **эскалация к человеку** (no auto-action)
- Для электроники при дефекте: предложить видео-инструкцию или FAQ по настройке перед возвратом

#### 2.3.3 Confirmation Language
При возврате/обмене использовать формулировки:
- ✅ "Вы можете оформить возврат через личный кабинет WB"
- ✅ "Для обмена создайте новый заказ с нужным размером"
- ❌ "Мы вернём вам деньги" (promises)
- ❌ "Гарантируем замену" (promises)

---

## 3. Safety Policies (три группы)

### 3.1 Group A: False Authority

AI не должен имитировать полномочия, которых у продавца нет.

| Запрещено | Почему | Замена |
|-----------|--------|--------|
| "Мы одобрим ваш возврат" | Решение принимает модератор WB | "Вы можете оформить возврат через ЛК WB. Модератор рассмотрит заявку в течение 24 часов" |
| "Гарантируем замену" | Продавец не контролирует процесс возврата | "Вы можете создать новый заказ с нужным товаром" |
| "Вернём деньги сразу" | Сроки определяет WB | "Средства вернутся после одобрения возврата модератором WB" |
| "Мы изменим ваш отзыв" | Только клиент может изменить отзыв | "Вы можете отредактировать отзыв в личном кабинете WB" |

### 3.2 Group B: WB Moderation

AI не должен брать на себя функции модераторов WB.

| Запрещено | Почему | Замена |
|-----------|--------|--------|
| "Отменяем ваш заказ" | Отмену делает WB Support | "Для отмены заказа обратитесь в поддержку WB через приложение" |
| "Изменим адрес доставки" | Только WB может менять адрес | "Изменить адрес можно через поддержку WB до отгрузки товара" |
| "Продлим срок возврата" | Сроки фиксированы политикой WB | "Стандартный срок возврата — 14 дней с момента получения" |
| "Ускорим доставку" | Логистика управляется WB | "Отследить статус доставки можно в личном кабинете WB" |

### 3.3 Group C: Legal Admissions

AI не должен признавать вину или делать юридически значимые заявления.

| Запрещено | Почему | Замена |
|-----------|--------|--------|
| "Да, это брак" | Юридическое признание дефекта | "Нам жаль, что товар не соответствует ожиданиям. Вы можете оформить возврат" |
| "Мы виноваты" | Признание ответственности | "Примем ваши замечания к сведению для улучшения качества" |
| "Это контрафакт" | Юридически опасное заявление | **Эскалация к человеку** (no auto-action) |
| "Нарушили закон" | Self-incrimination | **Эскалация к юристу** |

---

## 4. Action Guardrails — Auto-Action Policy

### 4.1 Link Types: Deterministic vs Probabilistic

**Deterministic link:**
- Основан на точном совпадении уникальных идентификаторов: `order_id`, `customer_id`
- ИЛИ на точном совпадении `nm_id` или `article` + временное окно ≤ 45 дней
- Минимальный confidence для deterministic: **0.90**

**Probabilistic link:**
- Основан на нечётких сигналах: name match, semantic overlap, time proximity
- Всегда требует ассистирования человека (auto_action_allowed = False)

### 4.2 Confidence Thresholds

| Параметр | Значение | Описание |
|----------|----------|----------|
| `MIN_LINK_CONFIDENCE` | **0.55** | Минимум для создания линка вообще. Ниже = no link. |
| `AUTO_ACTION_MIN_CONFIDENCE` | **0.85** | Минимум для auto-action при deterministic link. |
| `PRODUCT_THREAD_WINDOW_DAYS` | **45** | Окно для nm_id/article-based deterministic match. |

### 4.3 Deterministic Match Reasons & Confidences

| Match Reason | Confidence | Описание |
|--------------|------------|----------|
| `order_id_exact` | **0.99** | Точное совпадение номера заказа |
| `customer_id_exact` | **0.95** | Точное совпадение ID покупателя |
| `nm_id_time_window` | **0.82** | nm_id совпал + сообщение в пределах 45 дней от отзыва/вопроса |
| `article_time_window` | **0.78** | article совпал + временное окно 45 дней |

### 4.4 Scoring Signals (Full Table)

При построении кандидата линковки (`_build_candidate`) применяются следующие сигналы:

| Signal | Score Increment | Type | Описание |
|--------|-----------------|------|----------|
| `order_id` exact | +0.88 | deterministic | Точное совпадение order_id |
| `customer_id` exact | +0.68 | deterministic | Точное совпадение customer_id |
| `nm_id` exact | +0.34 | deterministic (if in window) | Точное совпадение nm_id |
| `product_article` exact | +0.28 | deterministic (if in window) | Точное совпадение артикула |
| `time_window_24h` | +0.16 | probabilistic | Сообщение в пределах 24 часов |
| `time_window_7d` | +0.10 | probabilistic | Сообщение в пределах 7 дней |
| `time_window_30d` | +0.05 | probabilistic | Сообщение в пределах 30 дней |
| `name_match_probabilistic` | +0.12 | probabilistic | Имена совпадают (fuzzy) |
| `name_partial_match` | +0.08 | probabilistic | Частичное совпадение имён |
| `semantic_overlap_high` (≥0.45) | +0.10 | probabilistic | Высокое семантическое сходство текстов |
| `semantic_overlap_medium` (≥0.25) | +0.06 | probabilistic | Среднее семантическое сходство |

**Важно:** Если есть хотя бы один deterministic сигнал (order_id, customer_id, nm_id+window, article+window), минимальный score устанавливается в **0.90**.

### 4.5 Policy Decision Matrix

| Link Type | Confidence | auto_action_allowed | action_mode | policy_reason |
|-----------|------------|---------------------|-------------|---------------|
| deterministic | ≥ 0.85 | **True** | `auto_allowed` | `deterministic_confidence_ok` |
| deterministic | < 0.85 | **False** | `assist_only` | `deterministic_below_confidence_threshold` |
| probabilistic | any | **False** | `assist_only` | `probabilistic_link_assist_only` |

**Логика из `evaluate_link_action_policy()`:**
1. Если `link_type != "deterministic"` → `auto_action_allowed=False`, `action_mode="assist_only"`, `reason="probabilistic_link_assist_only"`
2. Если `deterministic` + `confidence < 0.85` → `auto_action_allowed=False`, `action_mode="assist_only"`, `reason="deterministic_below_confidence_threshold"`
3. Если `deterministic` + `confidence >= 0.85` → `auto_action_allowed=True`, `action_mode="auto_allowed"`, `reason="deterministic_confidence_ok"`

---

## 5. Format & Limits

### 5.1 Reply Format (Structure & Tone)

**Структура ответа:**
1. **Приветствие + эмпатия** (если негатив или жалоба)
2. **Основная часть** (ответ на вопрос, решение проблемы, объяснение)
3. **Призыв к действию** (если применимо: оформите возврат, посмотрите инструкцию, напишите нам)
4. **Благодарность/закрытие**

**Тон:**
- Вежливый, дружелюбный, без формализма
- Краткий и по делу (избегать "воды")
- Эмпатичный при негативе (но не извиняться за то, в чём не виноваты)
- Проактивный (предлагать решение, а не просто констатировать)

**"Как стоило ответить" = готовый текст от лица продавца, НЕ инструкция:**
- ✅ Правильно: "Нам жаль! Оформите возврат через ЛК WB, модератор рассмотрит заявку в течение 24 часов."
- ❌ Неправильно: "Стоило извиниться и вежливо объяснить процедуру возврата..."

### 5.2 Length Limits

| Параметр | Значение | Применение |
|----------|----------|------------|
| `REPLY_MIN_LENGTH` | **20** символов | Минимальная длина ответа (все каналы) |
| `REPLY_MAX_LENGTH` | **300** символов | Максимальная длина ответа (все каналы) |

**Примечание:** Limits применяются к финальному тексту ответа после всех substitutions. Если текст короче 20 или длиннее 300 символов → validation error.

### 5.3 Action Plan Limits

| Параметр | Значение | Описание |
|----------|----------|----------|
| `actions_max_count` | **3** | Максимум 3 действия в плане |
| `actions_max_item_length` | **120** символов | Длина одного действия |
| `actions_min_item_length` | **5** символов | Минимальная длина действия |

**Формат action plan:**
```json
{
  "actions": [
    "Действие 1 (5-120 символов)",
    "Действие 2 (5-120 символов)",
    "Действие 3 (5-120 символов)"
  ]
}
```

### 5.4 Root Cause & Strategy Limits

| Параметр | Значение | Описание |
|----------|----------|----------|
| `root_cause_valid_types` | `{"expectation_mismatch", "defect", "design_flaw", "description_gap"}` | Допустимые типы root cause |
| `root_cause_default_type` | `"expectation_mismatch"` | Дефолтный тип, если не определён |
| `explanation_max_items` | **3** | Максимум пунктов в explanation |
| `explanation_max_item_length` | **150** символов | Длина одного пункта |
| `conclusion_max_length` | **120** символов | Длина итогового вывода |
| `strategy_title_max_length` | **40** символов | Длина названия стратегии |

---

## 6. Escalation Rules

AI НЕ генерирует автоматический ответ и эскалирует к человеку в следующих случаях:

| Ситуация | Причина | Action |
|----------|---------|--------|
| **Аллергия, вред здоровью** | Медицинские/юридические риски | Эскалация к менеджеру |
| **Контрафакт, подделка** | Юридически опасное заявление | Эскалация к юристу |
| **Угрозы, оскорбления** | Требуется деэскалация человеком | Эскалация к менеджеру |
| **Массовый дефект (>10 жалоб за 7 дней)** | Требуется расследование + управленческое решение | Эскалация к product team |
| **Персональные данные в сообщении** | Риск утечки PII | Эскалация + удаление данных |
| **Низкий confidence (<0.85) при deterministic link** | Неуверенность в линковке | assist_only mode |
| **Probabilistic link (любой confidence)** | Неточная линковка | assist_only mode |
| **Нарушения guardrails (severity=error)** | Политика безопасности | Блокировка отправки |

---

## 7. Validation Pipeline

### 7.1 Draft-Time (Warnings)

**Когда:** После генерации AI-драфта, до показа оператору.

**Проверки:**
- Длина текста (20-300 символов) → warning если выходит за границы
- Blame phrases в чатах → warning (soft, не блокирует)
- Отсутствие призыва к действию в ответе на вопрос → warning

**Результат:** Warnings логируются в audit trail, но НЕ блокируют показ драфта оператору. Оператор видит предупреждение и может отредактировать.

### 7.2 Pre-Send (Blocking)

**Когда:** Перед финальной отправкой ответа клиенту (auto-action или manual send).

**Проверки (все severity=error):**
1. **ai_mention** (все каналы) → error
2. **promises** (review, question) → error
3. **blame** (review, question) → error
4. **dismissive** (review, question) → error
5. **return_without_trigger** (review, question) → error
6. **length_limits** (все каналы) → error
7. **Safety Policies violations** (Group A, B, C) → error

**Результат:** Если найдено хотя бы одно нарушение с severity=error → отправка **БЛОКИРУЕТСЯ**. В audit trail записывается violations array. Оператор видит ошибку и должен исправить текст.

**Функция:** `validate_reply_text()` в `guardrails.py`

### 7.3 Audit Trail Requirements

Каждая генерация AI-драфта ОБЯЗАНА логировать:

| Поле | Тип | Описание |
|------|-----|----------|
| `timestamp` | datetime | Время генерации (ISO 8601) |
| `policy_version` | string | Версия guardrails policy (e.g., "v1.2") |
| `confidence` | float | Link confidence score (0.0-1.0) |
| `link_type` | string | "deterministic" или "probabilistic" |
| `action_mode` | string | "auto_allowed" или "assist_only" |
| `auto_action_allowed` | boolean | True/False |
| `policy_reason` | string | Причина решения (см. 4.5) |
| `violations` | array | Список error-нарушений (пустой если OK) |
| `warnings` | array | Список warning-предупреждений (пустой если OK) |
| `draft_text` | string | Исходный AI-драфт |
| `final_text` | string | Текст после редактирования оператора (если был) |
| `sent` | boolean | Был ли отправлен (true/false) |
| `operator_edited` | boolean | Редактировал ли оператор драфт |

**Хранение:** В базе данных, таблица `ai_drafts` или аналогичная. Retention: минимум 12 месяцев для аудита.

---

## 8. Source Files Reference

| Файл | Содержание | Строки | Путь от корня |
|------|------------|--------|---------------|
| `interaction_linking.py` | Auto-Action Policy, link types, confidence thresholds, scoring signals, decision matrix | весь файл, ключевые функции: `evaluate_link_action_policy()`, `_build_candidate()` | `agentiq/backend/` |
| `guardrails.py` | Banned phrases (все категории), channel rules, validation pipeline (`validate_reply_text()`) | весь файл, основные константы в начале | `agentiq/backend/` |
| `llm_analyzer.py` | GUARDRAILS config dict, limits для actions/root_cause/strategy | строки 478-519 (GUARDRAILS dict), 608-700 (COMM_SYSTEM промпт) | `agentiq/scripts/` |
| `RESPONSE_GUARDRAILS.md` | Full policy (reviews + chat), intent classification, SLA, Safety Policies A/B/C, conditional return logic, runtime rules | весь файл, секции 7.1-8.12 (Chat Policy Pipeline) | `agentiq/docs/` |
| `QUALITY_SCORE_FORMULA.md` | Формула quality_score (1-10), процентный расчёт, примеры | весь файл | `agentiq/docs/` |
| `REVIEWS_RESPONSES.md` | Hard rules для ответов на отзывы (draft spec) | весь файл | `agentiq/docs/` |
| `CHAT_RESPONSES.md` | Hard rules для ответов в чатах (draft spec) | весь файл | `agentiq/docs/` |
| `AI_DRAFTS.md` | Audit trail structure, policy_version, no auto-actions на низких confidence (draft spec) | весь файл | `agentiq/docs/` |

**Примечание:** Относительные пути от `/Users/ivanilin/Documents/ivanilin/agentiq/`.

---

## Changelog

### 2026-02-14
- Создан консолидированный документ GUARDRAILS.md
- Объединены правила из interaction_linking.py, guardrails.py, llm_analyzer.py, RESPONSE_GUARDRAILS.md
- Добавлены таблицы scoring signals, policy decision matrix, Safety Policies A/B/C
- Структурированы правила по каналам (review/question/chat)
- Документированы escalation rules и validation pipeline
- Добавлен audit trail requirements

### Next Steps
- Интеграция scenario engine (intent-based routing для чатов)
- Автоматизация проверки guardrails в CI/CD pipeline
- Versioning системы политик (policy_version tracking)
- A/B тестирование различных confidence thresholds
