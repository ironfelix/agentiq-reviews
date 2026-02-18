# Авто-ответы: Валидация прототипа + План реализации

> Last updated: 2026-02-17
> Status: Plan (не реализовано)
> Прототип: `docs/prototypes/auto-response-settings.html`

---

## 1. Валидация прототипа

### Таблица элементов

| # | Элемент UI | Статус | Что есть в коде | Что нужно доделать | Тех. ограничения |
|---|-----------|--------|------------------|--------------------|------------------|
| 1 | **Master toggle** (вкл/выкл авто-ответы) | Частично | `auto_response_enabled` в SLA config (`sla_config.py:43`). Toggle в `SettingsPage.tsx:296-300` (`auto_replies_positive`). API: `PUT /settings/ai` синхронизирует в SLA config (`settings.py:175`). | Прототип показывает toggle как master switch для всей секции (expand/collapse). В текущем коде toggle только включает/выключает, но нет expand логики. Нужно переделать UI по прототипу. | Нет |
| 2 | **Область действия** (весь кабинет vs nm_ids) | Частично | `auto_response_nm_ids` в SLA config (`sla_config.py:46`). Ввод артикулов в `SettingsPage.tsx:342-360`. Backend: фильтрация в `auto_response.py:87-103` и `sync.py:1449-1451`. | В прототипе -- radio buttons (весь кабинет/конкретные артикулы) + nm_id tags. В коде -- просто input field без radio. Нужно: radio группа + tags display как в прототипе. | Нет |
| 3 | **Каналы** (отзывы/вопросы/чаты) | Частично | `auto_response_channels` в SLA config (`sla_config.py:45`). Чекбоксы в `SettingsPage.tsx:311-338`. Backend: проверка канала в `auto_response.py:77-84`. | В прототипе каналы -- стилизованные карточки-чекбоксы. В коде -- стандартные чекбоксы. UI нужно переделать. **Чаты**: `_send_reply()` в `auto_response.py:256-261` НЕ поддерживает канал "chat" (только review и question). | WB Chat API (`POST /api/v1/seller/message`) поддерживает отправку в чаты. Но авто-ответ в чате рискованнее -- диалог двусторонний. |
| 4 | **Пресеты** (Безопасный/Сбалансированный/Максимум) | Нет | Не реализовано. Нет ни на backend, ни на frontend. | Полная реализация. Пресеты определяют: какие сценарии включены (АВТО/ЧЕРНОВИК) + какие каналы активны. Клиентская логика: пресет выставляет значения, далее пользователь кастомизирует. | Нет |
| 5a | **Позитивные отзывы 4-5 звезд** (АВТО) | Да | Полностью реализовано. Intent `thanks` в `auto_response_intents` (`sla_config.py:44`). Рейтинг >= 4 (`auto_response.py:117`). Генерация черновика через `generate_interaction_draft()` (`auto_response.py:126`). Guardrails (`auto_response.py:148`). Отправка через `wb_feedbacks_connector.answer_feedback()` (`auto_response.py:237`). | Расширить на другие позитивные интенты (не только `thanks`). Добавить вариативность текста (AI и так генерирует разные тексты). | Нет |
| 5b | **Промокод за 5 звезд** (АВТО) | Частично | Промокоды хранятся в `settings.py` (`PromoSettingsResponse`, строки 39-41). Есть `PromoChannels` с `reviews_positive` флагом (`settings.py:15`). AI генерирует тексты, но **промокод не подставляется автоматически в текст ответа на отзыв**. | Нужно: 1) В `generate_interaction_draft()` или post-processing: если rating=5 и promo enabled, подставлять промокод в текст. 2) Логика выбора промокода (round-robin или random из активных). 3) Инкремент `sent_count` на промокоде. **КРИТИЧНО**: ответ на отзыв -- ПУБЛИЧНЫЙ. Промокод увидят ВСЕ посетители карточки. Это не баг, это feature (маркетинг), но нужен warning в UI. | WB Feedbacks API: ответ на отзыв публичный. Промокод в открытом доступе. |
| 5c | **WISMO -- "Где мой заказ?"** (АВТО) | Частично | Intent `delivery_status` есть в `ai_analyzer.py:147`. SLA config: `normal` priority, 240 мин (`sla_config.py:30`). Fallback рекомендация есть (`ai_analyzer.py:1006`). НО: intent `delivery_status` **не в** `auto_response_intents` по умолчанию (только `thanks`). | Добавить `delivery_status` в список допустимых интентов для авто-ответа. Шаблон "Отследите в ЛК WB -> Доставки" уже есть в fallback. Нужен safety check: WISMO в отзыве (rating < 4) -- БЛОК. WISMO в вопросе/чате -- АВТО. | WB Chat API не дает order_id -- нельзя дать конкретный статус заказа. Ответ будет generic: "Проверьте в ЛК WB". |
| 5d | **Pre-purchase вопросы** (АВТО) | Частично | Интенты `pre_purchase`, `sizing_fit`, `availability`, `compatibility` есть в `ai_analyzer.py:157-160`. SLA: `high` priority, 5 мин (`sla_config.py:38-41`). Fallback рекомендации есть. НО: не в `auto_response_intents` по умолчанию. | Добавить pre-purchase интенты в допустимые. Для pre-purchase нужен контекст из карточки товара (уже реализовано через `product_context.py` и `fetch_product_card()` в `wb_connector.py:561`). Авто-ответ на вопрос -- через `wb_questions_connector.patch_question()` (`auto_response.py:250`). | Карточка товара берется из CDN (`wb_connector.py:584`), но может быть неполной. AI может "выдумать" характеристики -- guardrails не ловят это. |
| 6 | **Возврат/обмен** (ЧЕРНОВИК) | Частично | Intent `refund_exchange` есть (`ai_analyzer.py:154`). AI генерирует рекомендацию. В текущей системе все обращения с needs_response=True получают AI draft. Но draft сохраняется в `extra_data.last_ai_draft`, а не как отдельная сущность "черновик в очереди". | Нужно: 1) Маппинг intent -> action (AUTO/DRAFT/BLOCK). 2) Для DRAFT: генерировать текст, сохранять, показывать в UI с кнопкой "Отправить"/"Редактировать". 3) Уведомление продавцу о новом черновике. | Нет |
| 7a | **Брак/дефект** (БЛОК) | Частично | Intent `defect_not_working` есть (`ai_analyzer.py:146`), priority `urgent`. AI генерирует draft, но **нет механизма БЛОК** -- система просто не отправляет авто-ответ (потому что intent не в allowed list). | Нужно: явный статус BLOCK в маппинге. UI: показывать "Только вручную" badge. AI все равно генерирует draft для convenience. | Нет |
| 7b | **Не тот товар** (БЛОК) | Частично | Intent `wrong_item` есть (`ai_analyzer.py:149`), priority `urgent`. Аналогично 7a. | Аналогично 7a. | Нет |
| 7c | **Жалоба на качество** (БЛОК) | Частично | Ближайший intent: нет точного `quality_complaint`. Есть `defect_not_working`, `product_spec`. В CLAUDE.md упоминается `quality_complaint` как интент, но в `ai_analyzer.py:INTENTS` его нет. | Добавить intent `quality_complaint` в AI analyzer. Маппинг -> BLOCK. | Нет |
| 8 | **Channel tags** на сценариях | Нет | Не реализовано. В прототипе каждый сценарий помечен тегами (отзывы/вопросы/чаты), показывающими в каких каналах он работает. | Новая структура данных: каждый сценарий имеет `applicable_channels: list[str]`. Frontend: отображать теги. | Нет |
| 9 | **Safety notice** (предупреждение) | Частично | Guardrails реализованы в `app/services/guardrails.py`. Проверка banned phrases, длины текста. `auto_response.py:148-158` блокирует при error-severity warnings. | В прототипе -- желтый блок с текстом о безопасности. Это статический UI элемент, нужно просто добавить в React. Динамическая часть (проверка текстов) уже работает. | Нет |
| 10 | **Random delay** между ответами | Нет | В `auto_response.py` нет никакой задержки -- ответы отправляются сразу в цикле (`sync.py:1476-1511`). | Реализовать по SLA_RULES.md: `delay = random(3, 8)` сек + `word_count / 40`. В `process_auto_responses` task: после каждой успешной отправки делать `asyncio.sleep(delay)`. | Нет |
| 11 | **Top-bar notification** в Chat Center | Нет | Не реализовано. В прототипе -- синий баннер "Экономьте до 3 часов в день -- включите авто-ответы" с кнопкой "Настроить" и dismiss. | Новый React компонент `AutoResponseBanner`. Показывать если `auto_response_enabled=False` и у продавца есть необработанные обращения. Dismiss состояние в localStorage. | Нет |
| 12 | **"Изменения в течение 3 минут"** | Да (де-факто) | `process_auto_responses` Celery task запускается каждые 180 секунд (`tasks/__init__.py:53-54`). При сохранении настроек через `PUT /settings/ai` -> `update_sla_config()` -> запись в БД. Следующий цикл worker'а прочитает новые настройки. | Текст "3 минуты" корректен: worst case -- настройки сохранены сразу после начала цикла, следующий через 3 мин. Средний случай -- 1.5 мин. Нет race condition: worker читает config в начале каждого цикла (`sync.py:1427`). | Если нужна мгновенная реакция -- trigger `process_auto_responses.delay()` из API endpoint при сохранении. Но текущий подход (3 мин) достаточен для MVP. |

---

## 2. Что уже есть -- краткая сводка

### Backend

**Работающий pipeline авто-ответов:**
1. **Celery Beat** запускает `process_auto_responses` каждые 3 мин (`tasks/__init__.py:52-54`)
2. Task находит eligible interactions: `status=open`, `needs_response=True`, `rating >= 4`, канал в whitelist, nm_id в whitelist (`sync.py:1440-1457`)
3. AI Analyzer классифицирует intent (`sync.py:1492-1499`)
4. `process_auto_response()` проверяет: SLA config enabled, channel allowed, nm_id allowed, intent allowed, rating >= 4 (`auto_response.py:59-113`)
5. Генерирует AI draft через `generate_interaction_draft()` (`auto_response.py:126`)
6. Guardrails проверяют текст (`auto_response.py:148`)
7. Отправляет через WB API: feedbacks (`wb_feedbacks_connector.answer_feedback`) или questions (`wb_questions_connector.patch_question`) (`auto_response.py:233-255`)
8. Маркирует interaction: `is_auto_response=True`, `status=responded` (`auto_response.py:179-193`)
9. Записывает событие `auto_response_sent` (`auto_response.py:196-208`)

**Хранение конфига:**
- `RuntimeSetting` table, JSON, ключ `sla_config_v1:seller:{id}` (`sla_config.py:50-52`)
- Defaults: `auto_response_enabled=False`, `auto_response_intents=["thanks"]`, `auto_response_channels=["review"]`, `auto_response_nm_ids=[]` (`sla_config.py:43-46`)

**AI Analyzer:**
- 13 интентов: `delivery_status`, `delivery_delay`, `cancel_request`, `wrong_item`, `defect_not_working`, `usage_howto`, `product_spec`, `refund_exchange`, `thanks`, `pre_purchase`, `sizing_fit`, `availability`, `compatibility`, `other` (`ai_analyzer.py:145-162`)
- Канало-специфичные промпты: review, question, chat (`ai_analyzer.py:300-443`)
- Tone настройки: formal, friendly, neutral (`ai_analyzer.py:450-454`)
- Guardrails: banned phrases, max length, channel-aware truncation (`ai_analyzer.py:820-870`)

**API:**
- `GET /settings/ai` -- читает AI settings + синхронизирует из SLA config (`settings.py:130-156`)
- `PUT /settings/ai` -- сохраняет + синхронизирует в SLA config (`settings.py:159-199`)
- `GET/PUT /settings/sla-config` -- прямой доступ к SLA config (`settings.py:240-267`)

### Frontend

**SettingsPage.tsx (`SettingsPage.tsx:1-421`):**
- Tab `ai`: tone selector, auto_replies_positive toggle, channel checkboxes, nm_ids input
- Сохранение через `settingsApi.updateAISettings()`
- Нет: пресетов, сценариев, channel tags, safety notice, top-bar, random delay UI

---

## 3. Gap Analysis

### Что нужно доделать (приоритет: P0 = блокер MVP, P1 = важно, P2 = nice-to-have)

| # | Gap | Приоритет | Backend | Frontend | Оценка |
|---|-----|-----------|---------|----------|--------|
| G1 | **Маппинг intent -> action (AUTO/DRAFT/BLOCK)** | P0 | Новое поле `auto_response_scenario_config` в SLA config. Структура: `{intent: {action: "auto"|"draft"|"block", channels: ["review","question","chat"]}}` | UI сценариев с toggle (checked=AUTO, unchecked=DRAFT, locked=BLOCK) | 3-4 дня |
| G2 | **Пресеты (safe/balanced/max)** | P0 | Endpoint `POST /settings/auto-response/apply-preset` который записывает предопределенный scenario_config | 3 карточки пресетов, клик применяет конфигурацию к сценариям и каналам | 1-2 дня |
| G3 | **Расширение auto_response_intents** | P0 | Добавить `delivery_status`, `pre_purchase`, `sizing_fit`, `availability`, `compatibility`, `refund_exchange` как опции. По умолчанию enabled только `thanks`. | Чекбоксы сценариев в UI | 0.5 дня |
| G4 | **Промокод в авто-ответ** | P1 | В `auto_response.py` после генерации draft: если rating=5, promo enabled, есть активные промокоды -- append промокод к тексту. Инкремент `sent_count`. | Warning в UI: "Ответ на отзыв публичный -- промокод увидят все" | 2 дня |
| G5 | **Random delay** | P1 | В `process_auto_responses` task: `await asyncio.sleep(random.uniform(3, 8))` после каждой отправки. Формула из SLA_RULES.md. | Нет UI (конфиг в backend) | 0.5 дня |
| G6 | **Channel tags на сценариях** | P1 | Часть G1: `channels` поле в scenario config | Теги `отзывы`, `вопросы`, `чаты` на каждом сценарии | Включено в G1 |
| G7 | **Top-bar notification** | P1 | Endpoint для проверки: есть ли необработанные обращения + auto_response выключен | React компонент `AutoResponsePromoBanner` | 1 день |
| G8 | **Safety notice** | P2 | Нет (статический UI) | Желтый блок предупреждения | 0.5 дня |
| G9 | **Поддержка канала "chat" в авто-ответах** | P2 | Добавить case `chat` в `_send_reply()` (`auto_response.py:256`) с вызовом `WBConnector.send_message()` | Чекбокс "Чаты" уже есть | 1 день |
| G10 | **Intent `quality_complaint`** | P2 | Добавить в INTENTS dict и промпты | Отобразить в списке сценариев | 0.5 дня |
| G11 | **Scope radio buttons** | P1 | Backend уже поддерживает (пустой nm_ids = все) | Переделать UI: radio "Весь кабинет"/"Конкретные артикулы" + nm_id tags | 0.5 дня |
| G12 | **Полная переверстка Settings AI tab** | P0 | -- | Перенести дизайн из прототипа: expand section, scope, channels, presets, scenarios, safety notice, save row | 3-4 дня |

---

## 4. Архитектура

### 4.1 Модель данных сценариев (новое)

```python
# В SLA config (RuntimeSetting JSON), новый ключ:
{
    "auto_response_enabled": True,           # master toggle
    "auto_response_channels": ["review", "question"],  # глобальные каналы
    "auto_response_nm_ids": [],              # scope (пусто = все)
    "auto_response_scenarios": {             # НОВОЕ: маппинг intent -> config
        "thanks": {
            "action": "auto",                # auto | draft | block
            "channels": ["review"],          # где работает этот сценарий
            "enabled": true                  # можно отключить без смены action
        },
        "delivery_status": {
            "action": "auto",
            "channels": ["review", "question", "chat"],
            "enabled": true
        },
        "pre_purchase": {
            "action": "auto",
            "channels": ["question", "chat"],
            "enabled": true
        },
        "sizing_fit": {
            "action": "auto",
            "channels": ["question", "chat"],
            "enabled": true
        },
        "availability": {
            "action": "auto",
            "channels": ["question", "chat"],
            "enabled": true
        },
        "compatibility": {
            "action": "auto",
            "channels": ["question", "chat"],
            "enabled": true
        },
        "refund_exchange": {
            "action": "draft",
            "channels": ["review", "question", "chat"],
            "enabled": true
        },
        "defect_not_working": {
            "action": "block",
            "channels": ["review", "question", "chat"],
            "enabled": true
        },
        "wrong_item": {
            "action": "block",
            "channels": ["review", "question", "chat"],
            "enabled": true
        },
        "quality_complaint": {
            "action": "block",
            "channels": ["review", "question", "chat"],
            "enabled": true
        }
    },
    "auto_response_promo_on_5star": false,   # НОВОЕ: промокод за 5 звезд
    "auto_response_delay": {                 # НОВОЕ: настройки задержки
        "min_seconds": 3,
        "max_seconds": 8,
        "word_count_factor": 0.025
    }
}
```

### 4.2 Пресеты (конфигурация на backend, применение -- клиентское)

```python
PRESETS = {
    "safe": {
        "label": "Безопасный старт",
        "description": "Только позитивные отзывы 4-5 звезд",
        "channels": ["review"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            # все остальные -- draft или block
        }
    },
    "balanced": {
        "label": "Сбалансированный",
        "description": "Позитив + WISMO + pre-purchase. ~70% обращений.",
        "channels": ["review", "question"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            "delivery_status": {"action": "auto", "enabled": True},
            "pre_purchase": {"action": "auto", "enabled": True},
            "sizing_fit": {"action": "auto", "enabled": True},
            "availability": {"action": "auto", "enabled": True},
            "compatibility": {"action": "auto", "enabled": True},
        }
    },
    "max": {
        "label": "Максимум",
        "description": "Все кроме негатива. Включает возврат/обмен.",
        "channels": ["review", "question", "chat"],
        "scenarios": {
            "thanks": {"action": "auto", "enabled": True},
            "delivery_status": {"action": "auto", "enabled": True},
            "pre_purchase": {"action": "auto", "enabled": True},
            "sizing_fit": {"action": "auto", "enabled": True},
            "availability": {"action": "auto", "enabled": True},
            "compatibility": {"action": "auto", "enabled": True},
            "refund_exchange": {"action": "auto", "enabled": True},
        }
    }
}
```

**Где хранить пресеты:** Hardcode в backend файле `app/services/auto_response_presets.py`. Пресеты -- это предустановленные наборы, не кастомные. Endpoint `GET /settings/auto-response/presets` возвращает список. Endpoint `POST /settings/auto-response/apply-preset` применяет выбранный.

### 4.3 Поток данных

```
[Продавец] -> [SettingsPage UI] -> PUT /settings/ai (или PUT /settings/sla-config)
                                         |
                                         v
                                   [RuntimeSetting table]
                                   key: sla_config_v1:seller:{id}
                                         |
                                    (каждые 3 мин)
                                         |
                                         v
                              [Celery: process_auto_responses]
                                         |
                                  Для каждого seller:
                                         |
                              1. Читает SLA config из DB
                              2. Фильтрует interactions (status=open, needs_response=True)
                              3. AI Analyzer -> intent classification
                              4. Lookup scenario config: intent -> action
                                         |
                            +------------+------------+
                            |            |            |
                         action=auto  action=draft  action=block
                            |            |            |
                   Check channel   Generate draft   Skip
                   Check rating    Save to          (interaction stays
                   Generate draft  interaction      in queue for manual)
                   Guardrails      extra_data
                   Random delay    Mark: has_draft
                   Send via WB API
                   Mark: is_auto_response=True
```

### 4.4 Промокод в авто-ответ (поток)

```
process_auto_response()
  |
  +-- draft = generate_interaction_draft()
  |
  +-- if rating == 5 AND auto_response_promo_on_5star:
  |     |
  |     +-- promo = get_next_active_promo(db, seller_id)
  |     |     (round-robin или random из активных промокодов)
  |     |
  |     +-- if promo:
  |           reply_text += f"\n\nВ знак благодарности дарим промокод {promo.code} "
  |                         f"({promo.discount_label}). {promo.scope_label}."
  |           increment_promo_sent_count(promo)
  |
  +-- guardrails check (промокод не содержит banned phrases)
  +-- send via WB API
```

**Откуда берутся промокоды:** Из `PromoSettingsResponse.promo_codes` (хранятся в `RuntimeSetting`, ключ `promo_settings_v1:seller:{id}`). Файлы: `settings.py:36-38`, `settings.py:88-108`.

**Важное ограничение:** Ответ на отзыв через WB Feedbacks API -- ПУБЛИЧНЫЙ. Промокод увидит любой посетитель карточки товара. Это нужно явно предупредить в UI (в прототипе есть: строка 934 `Ответ на отзыв публичный`).

### 4.5 Random delay (реализация)

```python
# В process_auto_responses task (sync.py ~строка 1510):
import random

# После успешной отправки:
if sent:
    total_sent += 1
    # Random delay перед следующей отправкой
    delay_config = sla_config.get("auto_response_delay", {})
    min_sec = delay_config.get("min_seconds", 3)
    max_sec = delay_config.get("max_seconds", 8)
    word_factor = delay_config.get("word_count_factor", 0.025)

    word_count = len(reply_text.split())
    base_delay = random.uniform(min_sec, max_sec)
    word_delay = word_count * word_factor
    total_delay = min(base_delay + word_delay, 12)  # cap at 12 sec

    await asyncio.sleep(total_delay)
```

Обоснование из `docs/SLA_RULES.md:96-123`: фиксированная задержка выглядит механически, нужна вариативность 3-8 сек + компонента за длину текста.

---

## 5. План реализации

### Phase 1: MVP (Сценарии + Пресеты) -- 7-10 дней

**Sprint 1 (Backend foundation) -- 3 дня:**

1. **Файл: `app/services/auto_response_presets.py`** (новый)
   - Определение `PRESETS` dict
   - Определение `DEFAULT_SCENARIO_CONFIG` -- начальный маппинг intent -> action/channels
   - Функции: `get_presets()`, `apply_preset(db, seller_id, preset_name)`

2. **Файл: `app/services/sla_config.py`** (модификация)
   - Строка 21-47: расширить `DEFAULT_SLA_CONFIG` полем `auto_response_scenarios`
   - Строка 96-114: мержить `auto_response_scenarios` из seller overrides
   - Обратная совместимость: если `auto_response_scenarios` нет -- генерировать из `auto_response_intents` (миграция на лету)

3. **Файл: `app/schemas/settings.py`** (модификация)
   - Новые Pydantic модели: `ScenarioConfig(action, channels, enabled)`, `AutoResponseScenariosConfig`
   - Расширить `SLAConfig` полем `auto_response_scenarios`
   - Добавить `auto_response_promo_on_5star: bool = False`

4. **Файл: `app/api/settings.py`** (модификация)
   - Новые endpoints:
     - `GET /settings/auto-response/presets` -- список пресетов
     - `POST /settings/auto-response/apply-preset` -- применить пресет
   - Модификация `PUT /settings/ai`: синхронизировать scenarios в SLA config

5. **Файл: `app/services/auto_response.py`** (модификация)
   - Строка 105-113: заменить простую проверку `intent in allowed_intents` на lookup в `auto_response_scenarios`
   - Новая логика: `scenarios.get(intent, {}).get("action") == "auto"` AND `channel in scenarios[intent]["channels"]`
   - Добавить random delay после отправки

6. **Файл: `app/tasks/sync.py`** (модификация)
   - Строка 1431-1451: использовать `auto_response_scenarios` для фильтрации
   - Убрать хардкод `auto_response_intents` check, использовать scenario config

**Sprint 2 (Frontend) -- 4-5 дней:**

1. **Файл: `frontend/src/components/AutoResponseSettings.tsx`** (новый)
   - Master toggle + expand section
   - Scope radio (весь кабинет / конкретные артикулы) + nm_id tags
   - Channel checkboxes (стилизованные карточки)
   - Preset cards (3 штуки)
   - Scenario grid (АВТО/ЧЕРНОВИК/БЛОК) с toggle
   - Channel tags на сценариях
   - Safety notice
   - State legend (зеленый/желтый/красный)
   - Save button + "3 минуты" hint

2. **Файл: `frontend/src/components/SettingsPage.tsx`** (модификация)
   - Заменить текущий AI settings блок (строки 243-389) на `<AutoResponseSettings />`
   - Или добавить новый tab "Авто-ответы"

3. **Файл: `frontend/src/components/AutoResponseBanner.tsx`** (новый)
   - Top-bar notification component
   - Показывается на странице чатов если auto_response выключен
   - Dismiss в localStorage

4. **Файл: `frontend/src/services/api.ts`** (модификация)
   - Новые API методы: `getPresets()`, `applyPreset(name)`
   - Обновить типы

5. **Файл: `frontend/src/types.ts`** (модификация)
   - Новые типы: `ScenarioConfig`, `Preset`, `AutoResponseSettings`

### Phase 2: Промокод + Polish -- 3-4 дня

1. **Промокод в авто-ответ** (backend):
   - Файл: `app/services/auto_response.py` -- пост-обработка draft с подстановкой промокода
   - Файл: `app/api/settings.py` -- чтение promo settings
   - Файл: `app/services/promo_service.py` (новый) -- `get_next_promo(db, seller_id) -> PromoCode`

2. **Random delay** (backend):
   - Файл: `app/services/auto_response.py` или `app/tasks/sync.py` -- asyncio.sleep

3. **Канал "chat"** (backend):
   - Файл: `app/services/auto_response.py:256` -- добавить case для chat

4. **Intent `quality_complaint`** (backend):
   - Файл: `app/services/ai_analyzer.py:145` -- добавить в INTENTS
   - Файл: промпты -- добавить описание

5. **UI polish** (frontend):
   - Animation при toggle сценариев
   - Toast notification при сохранении
   - Responsive (mobile breakpoints)

### Phase 3: Аналитика + Advanced -- 5+ дней

1. **Дашборд авто-ответов:**
   - Сколько авто-ответов отправлено (за день/неделю/месяц)
   - По интентам
   - По каналам
   - Сколько заблокировано guardrails

2. **Draft queue:**
   - Отдельная секция в UI: "Черновики для проверки"
   - Push-уведомления о новых черновиках

3. **A/B тестирование текстов:**
   - Варианты ответов на один intent
   - Метрики эффективности

---

## 6. Оценка трудозатрат

| Блок | Backend | Frontend | Тестирование | Итого |
|------|---------|----------|--------------|-------|
| Scenario config (G1) | 2 дня | 2 дня | 1 день | 5 дней |
| Presets (G2) | 0.5 дня | 1 день | 0.5 дня | 2 дня |
| Расширение intents (G3) | 0.5 дня | -- | 0.5 дня | 1 день |
| Промокод (G4) | 1.5 дня | 0.5 дня | 0.5 дня | 2.5 дня |
| Random delay (G5) | 0.5 дня | -- | 0.5 дня | 1 день |
| Top-bar banner (G7) | 0.5 дня | 0.5 дня | 0.5 дня | 1.5 дня |
| Safety notice (G8) | -- | 0.5 дня | -- | 0.5 дня |
| Chat канал (G9) | 0.5 дня | -- | 0.5 дня | 1 день |
| Переверстка UI (G12) | -- | 3 дня | 0.5 дня | 3.5 дня |
| **Итого Phase 1+2** | **~6 дней** | **~7.5 дней** | **~4 дня** | **~17.5 дней** |

Реалистичная оценка с учетом интеграции и code review: **3-4 недели** (1 разработчик fullstack).

---

## 7. Риски и ограничения

### Технические

| Риск | Вероятность | Импакт | Митигация |
|------|-------------|--------|-----------|
| **WB модерация отклоняет авто-ответ с промокодом** | Средняя | Высокий | Тестировать на реальном API. Промокод -- не ссылка, должен пройти. Но нужно проверить. |
| **AI неверно классифицирует intent** | Средняя | Высокий | Guardrails блокируют опасные ответы. BLOCK интенты (defect, wrong_item) никогда не отправляются автоматически. Fallback: если intent сомнителен -- DRAFT, не AUTO. |
| **Race condition: настройки меняются во время обработки** | Низкая | Средний | Worker читает config в начале цикла и работает с ним. Изменения подхватятся в следующем цикле (через 3 мин). Atomic reads через SQLAlchemy. |
| **Rate limit WB API при массовой отправке** | Средняя | Средний | Random delay (3-8 сек) между отправками. Лимит 10 interactions на seller на цикл (`sync.py:1456`). WB rate limit ~10 msg/min. |
| **Промокод виден всем (публичный ответ на отзыв)** | Уверенность | Средний | Explicit warning в UI. Это feature, не bug -- маркетинговый инструмент. Но продавец должен осознанно включить. |

### Продуктовые

| Риск | Описание | Митигация |
|------|----------|-----------|
| **Продавец включит MAX пресет без понимания** | Авто-ответы на все обращения, включая возврат/обмен. Может отправить некорректный ответ. | Пресет "Безопасный старт" по умолчанию. Confirmation dialog при переключении на MAX. Safety notice всегда видим. |
| **Pre-purchase AI ответ с неверными характеристиками** | AI может "выдумать" размер/состав, если карточка товара неполная. | 1) Использовать `fetch_product_card()` для контекста. 2) В промпте: "НЕ выдумывай характеристики". 3) Guardrails не ловят фактические ошибки -- это ограничение. |
| **Негативный отзыв с рейтингом 4** | Текст негативный, но рейтинг 4. Система отправит авто-ответ "Спасибо за отзыв!". | AI Analyzer определяет sentiment. Добавить проверку: если sentiment=negative И rating >= 4 -- не отправлять AUTO, перевести в DRAFT. |

### Ограничения WB API

| Ограничение | Влияние | Workaround |
|-------------|---------|------------|
| **Нет webhooks** | Задержка 30-180 сек от получения обращения до авто-ответа | polling каждые 30 сек (`tasks/__init__.py:42-43`). Реалистичный SLA: 30 сек (sync) + 3 мин (auto-response cycle) = 3.5 мин worst case |
| **Нет order_id в Chat API** | WISMO ответ не может включать конкретный статус заказа | Generic: "Проверьте в ЛК WB". Это ограничение WB, не AgentIQ |
| **1000 символов макс в чате** | Длинный ответ с промокодом может не влезть | `get_max_length(channel)` в guardrails. Промокод ~50 символов, OK |
| **Ответ на отзыв -- публичный** | Промокод виден всем | Warning в UI. Это ожидаемое поведение WB |

### Миграции БД

**Не нужны.** Вся конфигурация хранится в `RuntimeSetting` (key-value, JSON). Новые поля добавляются в JSON без изменения schema. Обратная совместимость: если `auto_response_scenarios` отсутствует в JSON, используется legacy `auto_response_intents`.

---

## Приложение A: Ключевые файлы

| Файл | Путь | Роль |
|------|------|------|
| auto_response.py | `apps/chat-center/backend/app/services/auto_response.py` | Основная логика авто-ответов (262 строки) |
| sla_config.py | `apps/chat-center/backend/app/services/sla_config.py` | SLA конфигурация + defaults (178 строк) |
| sync.py | `apps/chat-center/backend/app/tasks/sync.py` | Celery tasks, включая process_auto_responses (1580 строк) |
| settings.py (API) | `apps/chat-center/backend/app/api/settings.py` | API endpoints настроек (281 строка) |
| settings.py (schemas) | `apps/chat-center/backend/app/schemas/settings.py` | Pydantic схемы (134 строки) |
| ai_analyzer.py | `apps/chat-center/backend/app/services/ai_analyzer.py` | AI классификация, 13 интентов (1147 строк) |
| wb_connector.py | `apps/chat-center/backend/app/services/wb_connector.py` | WB Chat API коннектор (660 строк) |
| SettingsPage.tsx | `apps/chat-center/frontend/src/components/SettingsPage.tsx` | Текущий UI настроек (421 строка) |
| tasks/__init__.py | `apps/chat-center/backend/app/tasks/__init__.py` | Celery Beat schedule (62 строки) |
| SLA_RULES.md | `docs/SLA_RULES.md` | SLA правила и задержки (272 строки) |
| Прототип | `docs/prototypes/auto-response-settings.html` | HTML прототип авто-ответов (1101 строка) |
