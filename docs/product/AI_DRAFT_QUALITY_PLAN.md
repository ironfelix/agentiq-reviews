# План улучшения качества AI-драфтов AgentIQ

**Last updated:** 2026-02-15
**Status:** plan (не реализовано)
**Автор:** product + engineering research

---

## Оглавление

1. [Аудит текущего состояния](#1-аудит-текущего-состояния)
2. [Анализ проблем](#2-анализ-проблем)
3. [Области улучшений (по импакту)](#3-области-улучшений-по-импакту)
4. [Sprint Plan (6 спринтов)](#4-sprint-plan-6-спринтов)
5. [Этический фреймворк](#5-этический-фреймворк)
6. [Обогащение контекста](#6-обогащение-контекста)
7. [Измерение качества](#7-измерение-качества)
8. [Стратегия дообучения](#8-стратегия-дообучения)

---

## 1. Аудит текущего состояния

### 1.1 Архитектура генерации драфтов

Система генерации AI-драфтов состоит из двух параллельных pipeline:

**Pipeline A: Чаты (Chat Center)**
```
sync.py (Celery beat каждые 2 мин)
  → analyze_pending_chats() → находит чаты без ai_analysis_json
  → analyze_chat_with_ai(chat_id) → Celery task
    → analyze_chat_for_db(chat_id, db)
      → AIAnalyzer.analyze_chat(messages, product_name, customer_name)
        → _call_llm() → DeepSeek API (temperature=0.3, max_tokens=1000)
        → _parse_response() → intent, sentiment, urgency, recommendation
        → _apply_guardrails() → banned phrases, greeting normalization, truncation
      → chat.ai_suggestion_text = recommendation
      → chat.ai_analysis_json = full analysis
```

**Pipeline B: Unified Interactions (Reviews, Questions, Chats)**
```
POST /api/interactions/{id}/ai-draft
  → generate_interaction_draft(db, interaction)
    → если channel=chat → resolve Chat → analyze_chat_for_db()
    → иначе → AIAnalyzer.analyze_chat(messages=[{text, "buyer"}], product_name)
    → _apply_guardrails_to_draft() → channel-specific guardrails
    → DraftResult → cached в interaction.extra_data["last_ai_draft"]
```

**Ключевые файлы:**
| Файл | Роль | Строки |
|------|------|--------|
| `apps/chat-center/backend/app/services/ai_analyzer.py` | System/User промпты, AIAnalyzer класс, guardrails post-processing | весь файл (721 строк) |
| `apps/chat-center/backend/app/services/interaction_drafts.py` | Unified draft generation, fallback логика, guardrails application | весь файл (169 строк) |
| `apps/chat-center/backend/app/services/guardrails.py` | Channel-specific banned phrases, pre-send validation | весь файл (338 строк) |
| `apps/chat-center/backend/app/services/ai_question_analyzer.py` | LLM intent classification для вопросов (hybrid: rule + LLM) | весь файл (178 строк) |
| `apps/chat-center/backend/app/services/interaction_metrics.py` | Quality tracking: accept_rate, edit_rate, manual_rate | весь файл (865 строк) |
| `apps/chat-center/backend/app/services/llm_runtime.py` | Runtime LLM config из DB (provider, model, enabled) | весь файл (85 строк) |
| `scripts/llm_analyzer.py:608-731` | COMM_SYSTEM/COMM_USER промпты для анализа отзывов (reviews app) | строки 608-731 |
| `scripts/llm_analyzer.py:478-519` | GUARDRAILS config dict | строки 478-519 |

### 1.2 Что передается LLM сейчас

**Контекст для чатов (ai_analyzer.py:232-254):**
- `product_name` — только название товара (строка, часто "Товар" по умолчанию)
- `messages_block` — последние 10 сообщений в формате `[дата] Автор: текст`
- Имя покупателя (для персонализации приветствия)

**Контекст для interactions (interaction_drafts.py:140-154):**
- `interaction.text` или `interaction.subject` — текст отзыва/вопроса
- `interaction.subject` как product_name (или "Товар" по умолчанию)
- `customer_name` из `interaction.extra_data.user_name`

**Что НЕ передается (критические пропуски):**
- Описание товара из card.json (description, options)
- Характеристики товара (состав, размерная сетка, материал)
- Цена товара
- Рейтинг отзыва (для reviews/questions)
- Категория товара (одежда vs электроника vs корм для животных)
- История предыдущих обращений этого покупателя
- Настройки тона продавца (tone: formal/friendly/neutral)
- Промокоды продавца (для pre-purchase)
- Контекст из других каналов (cross-channel context)

### 1.3 Система промптов

**CHAT_ANALYSIS_SYSTEM (ai_analyzer.py:168-229):**
- 62 строки, хорошо структурирован
- 10 интентов (delivery_status, defect_not_working, wrong_item, etc.)
- Четкие banned phrases (7 категорий)
- 10 правил генерации recommendation
- 8 примеров хороших ответов
- Escalation triggers (аллергия, контрафакт, угрозы, PII)
- Особый кейс для "thanks" (просьба об отзыве)

**CHAT_ANALYSIS_USER (ai_analyzer.py:232-254):**
- Минимальный контекст: product_name + messages_block
- JSON output format с 8 полями
- Лимит 300 символов для recommendation

**Сильные стороны промпта:**
- Четкие примеры для каждого интента
- Хорошие banned phrases в промпте
- Правило "НЕ выдумывать характеристики"
- Разнообразие концовок (правило 10)
- Обработка "thanks" кейса

**Слабые стороны промпта:**
- Нет product context (характеристики, описание)
- Нет tone/style инструкции (формальный/дружелюбный)
- Нет few-shot примеров реальных ответов продавца
- Нет rating отзыва (1-5 звезд) для вопросов/отзывов
- Нет категории товара для category-specific советов
- Нет инструкции по длине ответа для разных каналов
- Pre-purchase интенты есть в классификации, но нет в промпте

### 1.4 Guardrails

**Двойная система проверок:**

1. **In-prompt guardrails (ai_analyzer.py:184-229):**
   - Banned phrases встроены в system prompt
   - LLM "знает" что нельзя писать при генерации

2. **Post-generation guardrails (ai_analyzer.py:447-507):**
   - Regex-based замена banned phrases на safe alternatives
   - Нормализация приветствия (убирает фамилию, ставит имя)
   - Truncation до 500 символов

3. **Channel-specific guardrails (guardrails.py):**
   - Review/Question: все категории (ai_mention, promises, blame, dismissive, return_trigger)
   - Chat: только ai_mention (error) + blame (warning)
   - Pre-send validation: `validate_reply_text()` блокирует отправку при error

**Проблема:** guardrails в ai_analyzer.py (строки 106-152) и в guardrails.py (строки 25-80) частично дублируют друг друга. Разные наборы banned phrases, разные replacement стратегии.

### 1.5 Настройки тона (AISettings)

**Что есть:**
- Схема `AISettings` в `schemas/settings.py:52-55`: `tone: "formal" | "friendly" | "neutral"`
- Frontend UI для выбора тона в `SettingsPage.tsx:215-238`
- Настройка сохраняется, но **НЕ передается в LLM промпт**

**Что требуется:**
- Передавать `tone` в system prompt как инструкцию по стилю
- Разные примеры ответов для разных тонов

### 1.6 Метрики качества

**Текущая система (interaction_metrics.py):**
- `draft_accepted` — продавец отправил драфт без изменений
- `draft_edited` — продавец отредактировал драфт перед отправкой
- `reply_manual` — продавец написал ответ вручную (без драфта)
- `accept_rate` = draft_accepted / replies_total
- `edit_rate` = draft_edited / replies_total
- `manual_rate` = reply_manual / replies_total
- History: day-level aggregation для trend charts
- Alerts: quality_manual_rate_regression (week-over-week)

**Чего не хватает:**
- Нет сохранения diff между драфтом и финальным текстом
- Нет категоризации правок (что именно продавец менял)
- Нет оценки качества драфта (хороший/плохой)
- Нет A/B тестирования разных промптов
- Нет метрики "время до отправки" (как быстро продавец принял решение)

---

## 2. Анализ проблем

### 2.1 Критические проблемы (влияют на quality)

#### P1: Минимальный product context
**Проблема:** LLM получает только `product_name` (строку "Товар" или imt_name). Нет описания, характеристик, размерной сетки, состава.

**Последствие:** Генерируются generic ответы типа "Подскажите, пожалуйста, что именно произошло?" даже когда вся информация для ответа есть в карточке товара.

**Пример:** Покупатель спрашивает "Из чего сделано?" → LLM отвечает "Уточняем информацию по товару" → Правильно: "Состав: 95% хлопок, 5% эластан" (из card.json options).

**Файлы:** `ai_analyzer.py:332-333`, `interaction_drafts.py:151-153`, `wb_connector.py:440-464`

#### P2: Tone settings не используются
**Проблема:** Продавец выбирает tone (formal/friendly/neutral) в настройках, но это никак не влияет на генерацию.

**Последствие:** Все ответы одинакового стиля, независимо от brand voice продавца.

**Файлы:** `schemas/settings.py:49-55`, `ai_analyzer.py:167-229` (нет tone injection)

#### P3: Нет рейтинга отзыва в контексте interaction draft
**Проблема:** Для reviews/questions `interaction_drafts.py:140-146` создает сообщение без рейтинга. LLM не знает, что это 1-star негативный отзыв или 5-star позитивный.

**Последствие:** Одинаковые ответы на позитив и негатив при генерации через unified pipeline.

**Файлы:** `interaction_drafts.py:140-146`, `Interaction.rating` (есть, но не передается)

#### P4: Fallback ответы слишком generic
**Проблема:** При недоступности LLM `_fallback_draft()` возвращает 11 шаблонных ответов.

**Последствие:** Продавец видит "Спасибо за отзыв. Нам жаль, что товар не оправдал ожиданий. Уточните, пожалуйста, детали — постараемся помочь." — это именно то, что guardrails называют "template" (harmful на негатив).

**Файлы:** `interaction_drafts.py:48-69`, `ai_analyzer.py:616-631`

### 2.2 Средние проблемы (влияют на UX)

#### P5: Нет cross-channel context
**Проблема:** Если покупатель оставил негативный отзыв И написал в чат — LLM не видит связи. Каждый канал анализируется изолированно.

**Последствие:** Продавец может получить два противоречивых AI-драфта для одного покупателя.

**Файлы:** `interaction_linking.py` (система линковки есть, но не используется для enrichment промпта)

#### P6: Нет feedback loop
**Проблема:** Когда продавец редактирует драфт — записывается `draft_edited` event, но diff между original и edited не сохраняется.

**Последствие:** Невозможно понять, что именно продавцы исправляют. Невозможно учиться на правках.

**Файлы:** `interaction_metrics.py:39-65`

#### P7: Дублирование guardrails
**Проблема:** BANNED_PHRASES в `ai_analyzer.py:106-152` и в `guardrails.py:25-80` — разные списки, разная логика replacement.

**Последствие:** Неконсистентное поведение. `ai_analyzer.py` делает regex replacement, `guardrails.py` только проверяет наличие.

#### P8: 500 vs 300 символов conflict
**Проблема:** `ai_analyzer.py:498` обрезает до 500 символов, но `guardrails.py:83` устанавливает `REPLY_MAX_LENGTH = 300`, промпт `CHAT_ANALYSIS_USER` (строка 245) говорит "макс 300 символов".

**Последствие:** Ответ может пройти guardrails из ai_analyzer (500), но упасть на validate_reply_text (300).

### 2.3 Низкоприоритетные проблемы (tech debt)

#### P9: Один промпт для всех каналов
**Проблема:** `CHAT_ANALYSIS_SYSTEM` написан для чатов, но используется и для reviews, и для questions через interaction_drafts.py.

**Последствие:** Промпт инструктирует "проанализировать чат" когда обрабатывается одиночный отзыв.

#### P10: Нет version control для промптов
**Проблема:** Промпты захардкожены в Python файлах. Нет версионирования, нет A/B тестирования.

#### P11: DeepSeek-only
**Проблема:** `AIAnalyzer.__init__` поддерживает только `provider="deepseek"`. Любой другой provider → fallback mode.

---

## 3. Области улучшений (по импакту)

### HIGH IMPACT (прямо влияет на accept_rate и quality)

| # | Область | Ожидаемый эффект | Сложность |
|---|---------|------------------|-----------|
| H1 | Product card context в промпте | +15-25% accept_rate | Средняя |
| H2 | Tone injection (formal/friendly/neutral) | +5-10% accept_rate | Низкая |
| H3 | Rating-aware ответы для reviews/questions | +10-15% relevance | Низкая |
| H4 | Channel-specific промпты (review vs question vs chat) | +10% relevance | Средняя |
| H5 | Feedback loop (сохранение дiffs) | Данные для итераций | Средняя |

### MEDIUM IMPACT (улучшает overall experience)

| # | Область | Ожидаемый эффект | Сложность |
|---|---------|------------------|-----------|
| M1 | Cross-channel context (linked interactions) | Coherent responses | Высокая |
| M2 | Few-shot examples из реальных ответов продавца | Персонализация стиля | Средняя |
| M3 | Category-specific правила (одежда vs электроника vs еда) | Релевантность | Средняя |
| M4 | Промо-код injection в pre-purchase | +конверсия | Низкая |
| M5 | Унификация guardrails (один source of truth) | Консистентность | Средняя |

### LOW IMPACT (tech quality / future)

| # | Область | Ожидаемый эффект | Сложность |
|---|---------|------------------|-----------|
| L1 | Prompt versioning + A/B testing framework | Итеративное улучшение | Высокая |
| L2 | Multi-provider support (Claude, GPT-4) | Resilience | Средняя |
| L3 | RAG (seller knowledge base) | Custom answers | Высокая |
| L4 | RLHF-lite (learn from edits) | Auto-improvement | Высокая |

---

## 4. Sprint Plan (6 спринтов)

### Sprint 1: Product Context Enrichment (H1 + H3) — 1.5 недели

**Цель:** Передавать LLM реальную информацию о товаре и рейтинг отзыва.

**Задачи:**

1. **Расширить `fetch_product_name` → `fetch_product_card`**
   - Файл: `apps/chat-center/backend/app/services/wb_connector.py:440-464`
   - Вместо только `imt_name` — парсить `card.json` полностью: `description`, `options[]`, `compositions[]`
   - Кэшировать карточку товара на уровне `nm_id` (Redis или DB, TTL 24h)
   - Формат: `{name, description, options: [{name, value}], compositions: [{name, value}]}`

2. **Создать product context builder**
   - Новый файл: `apps/chat-center/backend/app/services/product_context.py`
   - Функция `build_product_context(nm_id: str) -> str` — форматирует карточку в текстовый блок для промпта
   - Лимит: макс 500 символов для product context (не раздувать промпт)
   - Пример output: `"Товар: Футболка мужская\nОписание: 100% хлопок, размеры S-XXL\nХарактеристики: Состав: хлопок 95%, эластан 5%. Размерная сетка: S=44, M=46, L=48"`

3. **Передать product context в промпт**
   - Файл: `apps/chat-center/backend/app/services/ai_analyzer.py:232-254`
   - Изменить `CHAT_ANALYSIS_USER`: добавить секцию `Информация о товаре: {product_context}`
   - Изменить `_call_llm()`: принимать `product_context` параметр
   - Изменить `analyze_chat()`: передавать nm_id или product_id для fetch

4. **Передать rating в interaction drafts**
   - Файл: `apps/chat-center/backend/app/services/interaction_drafts.py:140-146`
   - Добавить `interaction.rating` в messages block для review channel
   - Формат: `"★{rating}/5. Отзыв: {text}"`

**Файлы для модификации:**
- `wb_connector.py` — расширить `fetch_product_name` → `fetch_product_card`
- `ai_analyzer.py:232-254` — изменить `CHAT_ANALYSIS_USER` template
- `ai_analyzer.py:288-366` — изменить `analyze_chat` signature + `_call_llm`
- `interaction_drafts.py:113-169` — передать product context + rating
- Новый: `product_context.py` — product card builder + cache

**Ожидаемый результат:**
- accept_rate +15-25% для вопросов о характеристиках
- Исчезнут ответы "Уточняем информацию" когда информация есть в карточке
- Корректные ответы про размеры, состав, материал

**Зависимости:** Нет

---

### Sprint 2: Tone & Channel Differentiation (H2 + H4) — 1 неделя

**Цель:** Разные промпты для разных каналов. Tone settings влияют на генерацию.

**Задачи:**

1. **Tone injection в промпт**
   - Файл: `apps/chat-center/backend/app/services/ai_analyzer.py:167-229`
   - Добавить в `CHAT_ANALYSIS_SYSTEM` секцию `ТОН ОТВЕТА:`
   - `formal`: "Пишите в деловом стиле, без сокращений, обращайтесь на «Вы»"
   - `friendly`: "Пишите дружелюбно, с эмпатией, можно использовать неформальные обороты"
   - `neutral`: "Пишите нейтрально, по делу, без излишней эмоциональности"
   - Передавать tone из seller settings в `analyze_chat()`

2. **Загрузка seller settings при анализе**
   - Файл: `apps/chat-center/backend/app/services/ai_analyzer.py:647-720`
   - В `analyze_chat_for_db()` загружать `AISettings` для seller
   - Передавать `tone` параметром в `AIAnalyzer.analyze_chat()`

3. **Channel-specific промпты**
   - Файл: `apps/chat-center/backend/app/services/ai_analyzer.py`
   - Создать `REVIEW_ANALYSIS_SYSTEM` — для ответов на отзывы:
     - Учитывать rating (1-3: эмпатия + решение; 4-5: благодарность)
     - Публичный ответ — все видят, лаконичность важна
     - Не задавать вопросов в ответе на отзыв (покупатель не ответит)
   - Создать `QUESTION_ANALYSIS_SYSTEM` — для ответов на вопросы:
     - Конкретный ответ из карточки товара
     - Вопрос публичный — помогает другим покупателям
     - Можно и нужно давать технические детали
   - Оставить `CHAT_ANALYSIS_SYSTEM` для чатов

4. **Router в `generate_interaction_draft`**
   - Файл: `apps/chat-center/backend/app/services/interaction_drafts.py:113-169`
   - Выбирать промпт по `interaction.channel`

**Файлы для модификации:**
- `ai_analyzer.py` — новые промпты, tone injection, channel routing
- `interaction_drafts.py` — routing по channel
- `schemas/settings.py` — без изменений (схема уже есть)
- `api/settings.py` — загрузка tone settings при draft generation

**Ожидаемый результат:**
- Ответы на отзывы отличаются от ответов в чатах
- Продавец может настроить стиль под свой бренд
- accept_rate +5-10%

**Зависимости:** Sprint 1 (product context)

---

### Sprint 3: Feedback Loop & Edit Tracking (H5 + M5) — 1.5 недели

**Цель:** Сохранять правки продавцов для анализа. Унифицировать guardrails.

**Задачи:**

1. **Сохранение diff при edit**
   - Файл: `apps/chat-center/backend/app/services/interaction_metrics.py:39-65`
   - В `classify_reply_quality()` при `draft_edited`:
     - Сохранять `original_draft_text` в event details
     - Сохранять `final_text` в event details
     - Вычислять `edit_distance` (Levenshtein ratio)
     - Сохранять `edit_type`: "minor" (< 20% change), "major" (20-80%), "rewrite" (> 80%)
   - Новая таблица `draft_edits` или расширение `interaction_events.details`

2. **Аналитика правок (dashboard endpoint)**
   - Новый endpoint: `GET /api/analytics/draft-edits?days=30&channel=review`
   - Агрегация: какие intent чаще всего редактируют
   - Какие слова/фразы чаще всего добавляют/убирают
   - Top-5 паттернов правок

3. **Унификация guardrails**
   - Перенести все banned phrases из `ai_analyzer.py:106-152` в `guardrails.py`
   - `ai_analyzer.py._apply_guardrails()` должен вызывать `guardrails.apply_guardrails()`
   - Удалить дублирующий код из `ai_analyzer.py`
   - Единый source of truth: `guardrails.py`

4. **Fix длина: 300 vs 500 conflict**
   - `ai_analyzer.py:498`: изменить truncation с 500 на 300
   - Или: сделать channel-dependent лимит (chat: 500, review: 300, question: 300)

**Файлы для модификации:**
- `interaction_metrics.py:39-65` — расширить event tracking
- `ai_analyzer.py:447-507` — рефакторинг _apply_guardrails
- `guardrails.py` — стать единственным source of truth
- Новый endpoint в `api/analytics.py` или расширение `api/interactions.py`

**Ожидаемый результат:**
- Понимание: что продавцы правят (данные для Sprint 4-5)
- Единая система guardrails без дублирования
- Консистентные лимиты длины

**Зависимости:** Нет

---

### Sprint 4: Few-Shot & Seller Style Learning (M2 + M3) — 2 недели

**Цель:** Использовать реальные ответы продавца как few-shot examples. Категорийные правила.

**Задачи:**

1. **Сбор best practices продавца**
   - Из `draft_edits` (Sprint 3): ответы с `edit_type="minor"` = продавец в основном согласен
   - Из `draft_accepted` events: AI-драфты которые продавец принял без правок
   - Из исторических ответов на WB: `interaction.extra_data.last_reply_text`
   - Выбирать топ-5 лучших ответов по каждому intent

2. **Few-shot injection в промпт**
   - Файл: `ai_analyzer.py` — CHAT_ANALYSIS_SYSTEM
   - Добавить динамическую секцию `ПРИМЕРЫ ОТВЕТОВ ЭТОГО ПРОДАВЦА:`
   - Формат: `"На отзыв ★2 о дефекте продавец ответил: «...»"`
   - Лимит: макс 3 примера, макс 200 символов каждый

3. **Category-specific правила**
   - Определить категорию товара из card.json (`subj_name`, `subj_root_name`)
   - Для одежды/обуви: инструкция про размерную сетку
   - Для электроники: инструкция про инструкцию/FAQ
   - Для еды/косметики: инструкция про аллергию (escalation)
   - Добавить category-specific examples в промпт

4. **Хранение seller prompt config**
   - Расширить `AISettings`:
     ```python
     class AISettings(BaseModel):
         tone: Tone = "friendly"
         custom_greeting: Optional[str] = None  # "Привет!" vs "Здравствуйте!"
         custom_signature: Optional[str] = None  # "С уважением, команда X"
         banned_words: List[str] = []  # seller-specific banned words
     ```

**Файлы для модификации:**
- `ai_analyzer.py` — dynamic few-shot section in prompt
- `product_context.py` (из Sprint 1) — category detection
- `schemas/settings.py` — расширение AISettings
- `interaction_drafts.py` — передача few-shot examples
- Новый: `services/seller_style.py` — сбор и ранжирование best practices

**Ожидаемый результат:**
- Ответы соответствуют стилю конкретного продавца
- Category-specific советы (размеры, инструкции, аллергия)
- accept_rate +10-15%

**Зависимости:** Sprint 1 (product context), Sprint 3 (edit tracking)

---

### Sprint 5: Cross-Channel Context & Promo (M1 + M4) — 1.5 недели

**Цель:** AI видит все обращения покупателя. Pre-purchase ответы содержат промокоды.

**Задачи:**

1. **Cross-channel context в промпте**
   - Файл: `interaction_drafts.py`
   - При генерации драфта: вызывать `get_deterministic_thread_timeline()` из `interaction_linking.py`
   - Если есть linked interactions — добавить в промпт:
     - "Этот покупатель также оставил отзыв ★2 на этот товар: «текст»"
     - "В чате покупатель спрашивал о возврате 3 дня назад"
   - Лимит: макс 2 linked interactions, макс 100 символов каждый

2. **Promo code injection для pre-purchase**
   - При intent `pre_purchase`, `sizing_fit`, `availability`, `compatibility`:
   - Загрузить активные промокоды продавца из `promo_settings`
   - Если есть подходящий промокод — добавить в промпт:
     - "У продавца есть промокод: {code} ({discount_label})"
   - LLM может естественно встроить промокод в ответ

3. **Pre-purchase speed optimization**
   - Для pre-purchase чатов: уменьшить `temperature` до 0.1
   - Уменьшить `max_tokens` до 500 (ответы короче)
   - Увеличить priority для Celery task

**Файлы для модификации:**
- `interaction_drafts.py` — cross-channel enrichment
- `interaction_linking.py` — уже реализовано, нужен только вызов
- `ai_analyzer.py` — promo injection, pre-purchase optimization
- `schemas/settings.py` — promo codes уже есть

**Ожидаемый результат:**
- Coherent ответы при multi-channel обращениях
- +конверсия от промокодов в pre-purchase
- Быстрые ответы на pre-purchase вопросы

**Зависимости:** Sprint 1 (product context), Sprint 2 (channel routing)

---

### Sprint 6: Quality Framework & A/B Testing (L1 + L2) — 2 недели

**Цель:** Инфраструктура для итеративного улучшения промптов.

**Задачи:**

1. **Prompt versioning**
   - Новый файл: `apps/chat-center/backend/app/services/prompt_registry.py`
   - Хранить промпты в DB таблице `prompt_versions`:
     - `id`, `channel`, `version`, `system_prompt`, `user_template`, `is_active`, `created_at`
   - API для управления версиями: activate, deactivate
   - Каждый draft event записывает `prompt_version_id`

2. **A/B testing framework**
   - Seller-level assignment: 50% трафика на prompt v1, 50% на v2
   - Метрики: accept_rate, edit_rate, response_time_to_accept
   - Автоматический rollback если accept_rate падает > 10%

3. **Multi-provider support**
   - Рефакторинг `AIAnalyzer._call_llm()` → abstract `LLMProvider`
   - Реализации: `DeepSeekProvider`, `OpenAIProvider`, `AnthropicProvider`
   - Runtime switching через `llm_runtime.py`

4. **Quality scoring для отдельных драфтов**
   - Self-assessment: после генерации — второй LLM вызов для оценки:
     - "Оцени этот ответ от 1 до 5 по критериям: релевантность, тон, конкретность"
   - Если score < 3 → regenerate с увеличенным temperature
   - Логировать self-score для каждого драфта

**Файлы для модификации:**
- Новый: `prompt_registry.py` — prompt versioning
- Новый: `llm_providers.py` — abstract provider + implementations
- `ai_analyzer.py` — использовать registry + providers
- `interaction_metrics.py` — A/B metrics
- `llm_runtime.py` — multi-provider config

**Ожидаемый результат:**
- Возможность итеративно улучшать промпты с измерением
- Resilience: fallback на другого provider при сбое
- Self-assessment предотвращает отправку плохих драфтов

**Зависимости:** Sprint 3 (feedback loop), Sprint 4 (few-shot)

---

## 5. Этический фреймворк

### 5.1 Что НИКОГДА нельзя писать (severity: error, блокирует отправку)

| Категория | Фразы | Причина | Файл-источник |
|-----------|-------|---------|---------------|
| **False Authority** | "вернём деньги", "гарантируем возврат/замену", "одобрим возврат", "отменим заказ", "ускорим доставку" | Продавец не контролирует процессы WB | `guardrails.py:36-46` |
| **Blame** | "вы неправильно", "ваша вина", "сами виноваты", "вы ошиблись" | Обвинение клиента эскалирует конфликт | `guardrails.py:48-55` |
| **AI Disclosure** | "ИИ", "бот", "нейросеть", "GPT", "ChatGPT", "автоматический ответ" | Подрывает доверие, нарушает правила WB | `guardrails.py:25-34` |
| **Legal Admission** | "характеристики не соответствуют", "наша ошибка", "мы виноваты", "это подделка" | Юридически опасные признания | `ai_analyzer.py:131-133` |
| **Dismissive** | "обратитесь в поддержку", "напишите в поддержку" | Воспринимается как отказ помочь | `guardrails.py:57-60` |

### 5.2 Условные правила

| Правило | Условие | Что делать | Что НЕ делать |
|---------|---------|------------|---------------|
| **Return mention** | Покупатель САМ написал "возврат/замена" | "Оформите возврат через ЛК WB" | НЕ предлагать возврат первым |
| **Return for defect** | Intent = `defect_not_working` или `wrong_item` | Сразу инструкция по возврату (дефект очевиден) | НЕ ждать запроса покупателя |
| **Allergy/Health** | Упоминание аллергии, здоровья, реакции | STOP → эскалация к человеку | НЕ генерировать AI-ответ |
| **Counterfeit** | "подделка", "контрафакт", "не оригинал" | STOP → эскалация к юристу | НЕ подтверждать и не отрицать |
| **Legal threat** | "суд", "Роспотребнадзор", "жалоба" | STOP → эскалация к менеджеру | НЕ угрожать в ответ |
| **PII in message** | Паспорт, адрес, банковские данные | STOP → не обрабатывать | НЕ повторять PII в ответе |

### 5.3 Что ВСЕГДА должно быть в ответе

| Элемент | Когда | Пример |
|---------|-------|--------|
| **Приветствие по имени** | Всегда, если имя известно | "{Имя}, здравствуйте!" |
| **Эмпатия** | При негативе (1-3 stars, жалоба) | "Нам жаль", "Понимаем разочарование" |
| **Конкретный ответ** | Всегда | Факт/инструкция/объяснение |
| **Открытость к диалогу** | При чатах и вопросах | "Если нужна помощь — пишите" |
| **Благодарность за отзыв** | При позитивных отзывах | "Спасибо за обратную связь!" |

### 5.4 Auto-action vs Assist-only

| Ситуация | Режим | Причина |
|----------|-------|---------|
| Pre-purchase чат (sizing, availability) | **Auto** (с задержкой 3-5 сек) | Покупатель на карточке, окно 10-20 сек |
| Позитивный отзыв (4-5 stars, нет жалобы) | **Auto** (после одобрения seller) | Низкий риск |
| Негативный отзыв (1-3 stars) | **Assist-only** | Высокий риск, нужен контроль человека |
| Эскалация (аллергия, контрафакт, суд) | **Assist-only** | STOP, только человек |
| Probabilistic link | **Assist-only** | Неуверенность в линковке |
| Deterministic link, confidence < 0.85 | **Assist-only** | Недостаточная уверенность |

---

## 6. Обогащение контекста

### 6.1 Product Card Context (Sprint 1)

**Источник:** WB CDN API `basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json`

**Полезные поля:**
```json
{
  "imt_name": "Футболка мужская",
  "description": "Футболка из 100% хлопка...",
  "subj_name": "Футболки",
  "subj_root_name": "Одежда",
  "options": [
    {"name": "Состав", "value": "хлопок 95%, эластан 5%"},
    {"name": "Размерный ряд", "value": "S, M, L, XL, XXL"},
    {"name": "Страна производства", "value": "Турция"}
  ],
  "compositions": [
    {"name": "Хлопок", "id": 1, "value": 95},
    {"name": "Эластан", "id": 2, "value": 5}
  ]
}
```

**Формат для промпта (макс 500 символов):**
```
Информация о товаре:
Название: Футболка мужская
Категория: Одежда > Футболки
Описание: Футболка из 100% хлопка...
Характеристики: Состав: хлопок 95%, эластан 5%. Размерный ряд: S, M, L, XL, XXL. Страна: Турция
```

### 6.2 Buyer History (Sprint 5)

**Источник:** `interaction_linking.py` → `get_deterministic_thread_timeline()`

**Формат для промпта:**
```
История обращений покупателя:
- [Отзыв ★2, 05.02] "Размер не подошёл, заказывала M, но маломерит"
- [Чат, 07.02] Покупатель спрашивал про возврат
```

### 6.3 Seller Style (Sprint 4)

**Источник:** `draft_accepted` events + исторические ответы

**Формат для промпта:**
```
Стиль ответов этого продавца:
- На жалобу о размере: "Марина, приносим извинения! Эта модель действительно маломерит на размер. Рекомендуем взять на размер больше."
- На благодарность: "Спасибо за отзыв! Рады, что понравилось!"
```

### 6.4 Promo Codes (Sprint 5)

**Источник:** `seller.promo_settings.promo_codes`

**Формат для промпта:**
```
Активные промокоды продавца:
- WELCOME10: скидка 10% на все товары (до 01.03.2026)
```

### 6.5 Category-Specific Context (Sprint 4)

**Таблица категорийных правил:**

| Категория | Дополнительный контекст | Особые инструкции |
|-----------|------------------------|-------------------|
| Одежда/Обувь | Размерная сетка, состав | "Рекомендуйте ориентироваться на замеры в карточке" |
| Электроника | Характеристики, гарантия | "Предложите проверить настройки / FAQ" |
| Еда / Корм | Состав, срок годности | "При аллергии — эскалация. Порекомендуйте проверить состав" |
| Косметика | Состав, тип кожи | "При аллергии — STOP. Порекомендуйте patch test" |
| Детские товары | Возрастные ограничения | "Повышенная осторожность в рекомендациях" |

---

## 7. Измерение качества

### 7.1 Текущие метрики (уже реализовано)

| Метрика | Формула | Файл | Что показывает |
|---------|---------|------|----------------|
| `accept_rate` | draft_accepted / replies_total | `interaction_metrics.py:277` | Доля драфтов принятых без правок |
| `edit_rate` | draft_edited / replies_total | `interaction_metrics.py:278` | Доля драфтов с правками |
| `manual_rate` | reply_manual / replies_total | `interaction_metrics.py:279` | Доля ручных ответов (без AI) |
| `quality_regression` | current_manual_rate - previous_manual_rate | `interaction_metrics.py:502` | Week-over-week regression |

### 7.2 Новые метрики (предлагаемые)

| Метрика | Формула | Что показывает | Sprint |
|---------|---------|----------------|--------|
| `edit_severity` | avg(levenshtein_ratio) для edited drafts | Насколько сильно правят | Sprint 3 |
| `time_to_accept` | median(accept_timestamp - draft_shown_timestamp) | Как быстро продавец решает | Sprint 3 |
| `intent_accept_rate` | accept_rate по каждому intent | Где AI хорош, а где нет | Sprint 3 |
| `channel_accept_rate` | accept_rate по каналу (review/question/chat) | Какой канал проблемный | Sprint 3 |
| `self_assessment_score` | avg(LLM self-score 1-5) | Оценка LLM своих ответов | Sprint 6 |
| `prompt_version_accept_rate` | accept_rate по version промпта | Какой промпт лучше | Sprint 6 |
| `few_shot_lift` | accept_rate с few-shot - accept_rate без | Эффект few-shot examples | Sprint 4 |

### 7.3 Target KPIs

| KPI | Текущее (оценка) | Target Sprint 2 | Target Sprint 4 | Target Sprint 6 |
|-----|-------------------|-----------------|-----------------|-----------------|
| accept_rate | ~30-40% | 45-55% | 60-70% | 70-80% |
| edit_rate | ~30% | 25% | 20% | 15% |
| manual_rate | ~30-40% | 20-30% | 10-20% | 5-10% |
| median time_to_accept | unknown | <30s | <15s | <10s |
| guardrail violations | unknown | <5% | <2% | <1% |

### 7.4 Мониторинг (ops)

**Dashboard:**
- Daily accept_rate trend (line chart)
- Accept rate by channel (bar chart)
- Top-5 most edited intents (table)
- Guardrail violation rate (gauge)
- LLM latency p50/p95 (time series)

**Alerts:**
- `accept_rate < 30%` за 24h → warning
- `manual_rate > 50%` за 24h → high alert
- `guardrail_violations > 10%` → critical
- `llm_latency_p95 > 15s` → warning
- `llm_error_rate > 5%` → critical

---

## 8. Стратегия дообучения

### 8.1 Few-Shot Learning (Sprint 4)

**Подход:** Использовать реальные ответы продавца как примеры в промпте.

**Реализация:**
1. Собрать `draft_accepted` events за 30 дней
2. Группировать по intent
3. Для каждого intent — выбрать top-3 по длине и уникальности
4. Вставить в dynamic section промпта

**Преимущества:**
- Не требует fine-tuning модели
- Работает с любым LLM provider
- Адаптируется автоматически (новые ответы = новые примеры)

**Ограничения:**
- Лимит context window (макс 3-5 примеров)
- Может закрепить плохие паттерны если продавец принимает плохие драфты

### 8.2 RLHF-lite (Sprint 6+)

**Подход:** Использовать edit signals для scoring.

**Реализация:**
1. `draft_accepted` = reward signal (хороший драфт)
2. `draft_edited` с `edit_severity > 0.5` = penalty signal (плохой драфт)
3. `reply_manual` = strong penalty (AI драфт бесполезен)
4. Собирать (prompt, draft, reward) трiples
5. Использовать для selection промптов (не для fine-tuning модели)

**Practical approach (без fine-tuning):**
- Собрать dataset из 100+ (input, draft, edited_draft, reward)
- Тестировать разные промпты на этом dataset (offline evaluation)
- Выбирать промпт с лучшим совпадением с edited_draft
- Это "prompt optimization" а не RLHF

### 8.3 RAG — Seller Knowledge Base (Sprint 6+)

**Подход:** Продавец загружает FAQ / инструкции / размерные сетки → RAG retrieval при генерации.

**Реализация:**
1. UI для загрузки документов (txt, pdf, images)
2. Chunking + embedding (text-embedding-3-small)
3. Vector store (pgvector или Qdrant)
4. При генерации: retrieve top-3 chunks → inject в промпт

**Преимущества:**
- Ответы со 100% точной информацией от продавца
- Покрывает edge cases которых нет в card.json
- Конкурентное преимущество (уникальные ответы)

**Ограничения:**
- Высокая сложность реализации
- Требует от продавца initial setup
- Стоимость embeddings

### 8.4 Multi-Model Strategy

**Текущее:** DeepSeek-only (deepseek-chat).

**Предложение:**
| Задача | Модель | Почему |
|--------|--------|--------|
| Pre-purchase (fast) | DeepSeek или GPT-4o-mini | Скорость важнее качества |
| Review draft | Claude 3.5 Sonnet или GPT-4o | Нужна эмпатия + нюанс |
| Question draft | DeepSeek | Фактический ответ, скорость |
| Chat draft | DeepSeek | Баланс скорости и качества |
| Self-assessment | GPT-4o-mini | Дешевая оценка качества |
| Intent classification | DeepSeek (текущий) | Работает хорошо |

**Priority:** L2, делать только после Sprint 6 prompt versioning.

---

## Приоритеты для product review

**Must-have (Sprint 1-3):**
- Product card context в промпте — самый большой impact
- Tone injection — уже есть UI, нужно только подключить
- Rating в контексте — тривиальная правка
- Feedback loop — необходим для измерения всех остальных улучшений

**Should-have (Sprint 4-5):**
- Few-shot examples — требует данных из Sprint 3
- Cross-channel context — использует существующий linking engine
- Category-specific правила — зависит от product context

**Nice-to-have (Sprint 6+):**
- Prompt versioning + A/B testing
- Multi-provider support
- RAG
- RLHF-lite

---

## Source Files Reference

| Файл | Полный путь | Роль в системе |
|------|-------------|----------------|
| ai_analyzer.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/ai_analyzer.py` | System/User промпты, AIAnalyzer класс, chat analysis |
| interaction_drafts.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/interaction_drafts.py` | Unified draft generation, DraftResult, fallback |
| guardrails.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/guardrails.py` | Channel-specific guardrails, pre-send validation |
| ai_question_analyzer.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/ai_question_analyzer.py` | Hybrid intent classification (rule + LLM) |
| interaction_metrics.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/interaction_metrics.py` | Quality tracking, ops alerts, pilot readiness |
| interaction_linking.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/interaction_linking.py` | Cross-channel linking, deterministic/probabilistic |
| llm_runtime.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/llm_runtime.py` | Runtime LLM config from DB |
| wb_connector.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/services/wb_connector.py` | WB Chat API, fetch_product_name |
| sync.py | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/tasks/sync.py` | Celery tasks: sync, analyze_pending, analyze_chat_with_ai |
| settings.py (schemas) | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/schemas/settings.py` | AISettings, PromoSettings schemas |
| interactions.py (API) | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/backend/app/api/interactions.py` | POST /{id}/ai-draft, POST /{id}/reply |
| AIPanel.tsx | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/frontend/src/components/AIPanel.tsx` | Frontend AI suggestion panel |
| ChatWindow.tsx | `/Users/ivanilin/Documents/ivanilin/agentiq/apps/chat-center/frontend/src/components/ChatWindow.tsx` | Chat UI with AI suggestion inline |
| GUARDRAILS.md | `/Users/ivanilin/Documents/ivanilin/agentiq/docs/GUARDRAILS.md` | Consolidated guardrails documentation |
| RESPONSE_GUARDRAILS.md | `/Users/ivanilin/Documents/ivanilin/agentiq/docs/reviews/RESPONSE_GUARDRAILS.md` | Review + chat response policy |
| QUALITY_SCORE_FORMULA.md | `/Users/ivanilin/Documents/ivanilin/agentiq/docs/reviews/QUALITY_SCORE_FORMULA.md` | Quality score calculation (reviews app) |
| llm_analyzer.py | `/Users/ivanilin/Documents/ivanilin/agentiq/scripts/llm_analyzer.py` | COMM_SYSTEM промпт (reviews), GUARDRAILS config |
