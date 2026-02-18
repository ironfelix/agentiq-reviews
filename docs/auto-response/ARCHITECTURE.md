# Auto-Response System — Technical Architecture

> Last updated: 2026-02-17
> Status: Active

---

## Table of Contents

1. [Overview](#1-overview)
2. [Pipeline Flow](#2-pipeline-flow)
3. [Safety Layers](#3-safety-layers)
4. [Scenario System](#4-scenario-system)
5. [Channel Support](#5-channel-support)
6. [Promo Code Injection](#6-promo-code-injection)
7. [Configuration](#7-configuration)
8. [Celery Integration](#8-celery-integration)
9. [WB API Integration](#9-wb-api-integration)
10. [Monitoring](#10-monitoring)

---

## 1. Overview

### What the System Does

The auto-response system automatically replies to customer interactions (reviews, questions, chats) on Wildberries marketplace on behalf of sellers. It generates AI-powered responses and sends them through the WB API without manual seller intervention.

### Why It Exists

| Problem | Solution |
|---------|----------|
| Sellers spend 2-4 hours/day manually replying to reviews | Auto-respond to positive reviews in seconds |
| Pre-purchase questions have a 10-20 second decision window | AI responds within the 3-minute sync cycle |
| SLA compliance drops on weekends/nights | 24/7 automated coverage |
| Inconsistent reply quality across team members | Guardrail-enforced, template-consistent responses |
| Missed promo code opportunities on 5-star reviews | Automatic promo injection for loyal customers |

### MVP Scope

The initial (and current) scope focuses on safety-first automation:

- **ONLY** auto-responds to ratings >= 4 (hard safety guard)
- **ONLY** for intents and channels the seller explicitly enables
- **NEVER** auto-responds to negative reviews (1-3 stars)
- **NEVER** sends if guardrails detect any error-severity violation
- If ANY step fails, the system **silently skips** (seller can respond manually)

### Key Source Files

| File | Purpose |
|------|---------|
| `backend/app/services/auto_response.py` | Core pipeline (9-step process) |
| `backend/app/services/auto_response_presets.py` | Preset configurations (safe/balanced/max) |
| `backend/app/services/sla_config.py` | SLA + auto-response config storage |
| `backend/app/services/guardrails.py` | Banned phrases, length limits, validation |
| `backend/app/services/ai_analyzer.py` | AI intent classification + response generation |
| `backend/app/tasks/sync.py` | Celery task `process_auto_responses` |
| `backend/app/api/settings.py` | Settings API endpoints |

---

## 2. Pipeline Flow

The auto-response system follows a strict 9-step pipeline. Every step has a fail-safe: if it fails, the interaction is skipped (no auto-response sent, seller can reply manually).

### Pipeline Diagram

```
                     Celery Beat (every 3 min)
                              |
                              v
                 +----------------------------+
                 | process_auto_responses()   |
                 | Find eligible interactions |
                 | (open, needs_response,     |
                 |  rating >= 4, not auto)    |
                 +----------------------------+
                              |
            For each interaction:
                              |
     +------------------------+------------------------+
     |                                                 |
     v                                                 v
 Step 1: SLA Config                              (skip if disabled)
 auto_response_enabled?
     |
     v
 Step 2: Channel Check
 channel in allowed_channels?
     |
     v
 Step 2b: nm_id Whitelist
 nm_id in whitelist? (empty = all)
     |
     v
 Step 3: Scenario / Intent Check
 intent has scenario with action="auto"
 and enabled=true?
     |
     v
 Step 4: Rating Gate (SAFETY)
 rating >= 4? (hard minimum)
     |
     v
 Step 5: Generate AI Draft
 generate_interaction_draft()
     |
     v
 Step 5b: Promo Code Injection
 (only for 5-star reviews if enabled)
     |
     v
 Step 6: Guardrails Check
 apply_guardrails() -- any error = BLOCK
     |
     v
 Step 7: Send via WB API
 _send_reply() per channel connector
     |
     v
 Step 8: Mark Interaction
 is_auto_response=True, status='responded'
     |
     v
 Step 9: Log & Event
 InteractionEvent(type="auto_response_sent")
```

### Step Details

| Step | Function | Failure Mode |
|------|----------|--------------|
| 1. SLA Config | `get_sla_config(db, seller_id)` | Exception -> skip (return False) |
| 2. Channel | Compare `interaction.channel` against `auto_response_channels` | Not in list -> skip |
| 2b. nm_id | Compare `interaction.nm_id` against `auto_response_nm_ids` | Not in list -> skip (empty list = all allowed) |
| 3. Intent/Scenario | Look up `auto_response_scenarios[intent]` | No scenario or action != "auto" or disabled -> skip |
| 4. Rating | `rating >= MIN_AUTO_RESPONSE_RATING (4)` | rating < 4 or None -> **BLOCKED** (logged at INFO level) |
| 5. Draft | `generate_interaction_draft(db, interaction)` | Exception or empty draft -> skip |
| 5b. Promo | `_insert_promo_code(db, seller_id, reply_text)` | Failure is non-blocking (continues without promo) |
| 6. Guardrails | `apply_guardrails(reply_text, channel, customer_text)` | Any error-severity warning -> **BLOCKED** |
| 7. Send | `_send_reply(db, interaction, seller, reply_text)` | Exception or False -> skip |
| 8. Mark | Update interaction fields + `db.commit()` | Transaction failure -> skip |
| 9. Log | Create `InteractionEvent` + log INFO | Non-critical |

---

## 3. Safety Layers

The system has **four independent safety layers** that prevent harmful auto-responses. Each layer is a hard gate -- if any layer blocks, the response is NOT sent.

### Layer 1: Rating Gate

```python
MIN_AUTO_RESPONSE_RATING = 4
```

- **Hard-coded constant** -- cannot be overridden by seller config
- Interactions with `rating < 4` or `rating is None` are always blocked
- Logged at INFO level (not debug) because this is a safety event:
  ```
  auto_response: BLOCKED -- rating=3 < 4 for interaction=123 seller=5 (safety guard)
  ```

### Layer 2: Scenario Routing

Each intent has a configured **action** that determines behavior:

| Action | Behavior |
|--------|----------|
| `auto` | Full pipeline: generate draft, check guardrails, send if passes |
| `draft` | Generate draft for seller review, but **never** auto-send |
| `block` | Do not process at all. Used for negative/risky intents |

**Always-blocked intents** (regardless of preset or seller config):

```python
ALWAYS_BLOCK_INTENTS = {"defect_not_working", "wrong_item", "quality_complaint"}
```

### Layer 3: Guardrails

The guardrails system (`guardrails.py`) checks the generated response for:

- **Banned phrases** (AI mentions, false promises, blame, dismissive language)
- **Unsolicited return mentions** (suggesting returns when customer didn't ask)
- **Length violations** (too long or too short)

For auto-responses, **any error-severity warning** blocks sending:

```python
error_warnings = [w for w in warnings if w.get("severity") == "error"]
if error_warnings:
    # BLOCKED -- do not send
    return False
```

### Layer 4: Channel-Specific Rules

| Channel | Guardrail Level | Banned Categories |
|---------|----------------|-------------------|
| `review` | Strictest | ai_mention, promise, blame, dismissive, unsolicited_return |
| `question` | Strict | ai_mention, promise, blame, dismissive, unsolicited_return |
| `chat` | Relaxed | ai_mention (error), blame (warning only) |

### Safety Summary

```
Interaction arrives
  -> Rating < 4?              YES -> BLOCKED (hard gate)
  -> Scenario action=block?   YES -> BLOCKED
  -> Scenario action=draft?   YES -> Draft only (no send)
  -> Scenario disabled?       YES -> Skip
  -> Guardrails error?        YES -> BLOCKED
  -> Send failure?            YES -> Skip silently
  -> All passed?              YES -> SEND
```

---

## 4. Scenario System

### Intent Classification

The AI analyzer classifies each interaction into one of these intents:

| Intent | Description | Default Action | Default Priority |
|--------|-------------|---------------|------------------|
| `thanks` | Благодарность | auto | low |
| `delivery_status` | Где мой заказ? | auto (disabled) | normal |
| `pre_purchase` | Вопрос перед покупкой | auto (disabled) | high |
| `sizing_fit` | Какой размер выбрать? | auto (disabled) | high |
| `availability` | Есть ли в наличии? | auto (disabled) | high |
| `compatibility` | Подойдёт ли к...? | auto (disabled) | high |
| `refund_exchange` | Возврат или обмен | draft | normal |
| `defect_not_working` | Брак, не работает | **block** | urgent |
| `wrong_item` | Прислали не тот товар | **block** | urgent |
| `quality_complaint` | Жалоба на качество | **block** | normal |

### Scenario Configuration Structure

Each scenario is a dict with three fields:

```json
{
  "thanks": {
    "action": "auto",       // "auto" | "draft" | "block"
    "channels": ["review"], // which channels this applies to
    "enabled": true          // master toggle per scenario
  }
}
```

### Presets

Three predefined presets make it easy for sellers to configure auto-responses:

#### Safe (Безопасный старт)

```
Only positive 4-5 star reviews. Ideal for first launch.
Channels: review
Enabled scenarios: thanks
```

#### Balanced (Сбалансированный)

```
Positive + WISMO + pre-purchase questions. Covers ~70% of interactions.
Channels: review, question
Enabled scenarios: thanks, delivery_status, pre_purchase, sizing_fit, availability, compatibility
```

#### Max (Максимум)

```
Everything except negative reviews. Includes refund/exchange (templated response).
Channels: review, question, chat
Enabled scenarios: thanks, delivery_status, pre_purchase, sizing_fit,
                   availability, compatibility, refund_exchange
```

### Preset Application Logic

When a preset is applied (`build_scenario_config_for_preset`):

1. Start with `DEFAULT_SCENARIO_CONFIG` (deep copy)
2. Disable all non-block scenarios
3. Enable scenarios defined in the preset
4. **Block intents stay blocked regardless** (defect, wrong_item, quality_complaint)

### Legacy Compatibility

The system supports the older `auto_response_intents` list format:

```python
# New format (preferred):
"auto_response_scenarios": {"thanks": {"action": "auto", "enabled": true, ...}}

# Legacy format (still supported):
"auto_response_intents": ["thanks"]
```

If a seller has `auto_response_intents` but no `auto_response_scenarios`, the system generates scenarios from the legacy list.

---

## 5. Channel Support

### Review Channel

- **WB API**: `wb_feedbacks_connector.answer_feedback(feedback_id, text)`
- **Guardrails**: Strictest (all banned phrase categories)
- **Max length**: 500 characters
- **Promo codes**: Supported (5-star only)
- **Typical intents**: thanks, quality_complaint, defect

### Question Channel

- **WB API**: `wb_questions_connector.patch_question(question_id, state, answer_text)`
- **State handling**: Uses `wbRu` state by default; reads from `interaction.extra_data["state"]` if available
- **Guardrails**: Strict (same as review)
- **Max length**: 500 characters
- **Promo codes**: Not supported (questions don't have ratings)
- **Typical intents**: pre_purchase, sizing_fit, availability, compatibility

### Chat Channel

- **WB API**: `wb_connector.send_message(chat_id, text)`
- **Guardrails**: Relaxed (only AI mentions are error-level)
- **Max length**: 1000 characters
- **Promo codes**: Not supported
- **Typical intents**: delivery_status, pre_purchase, usage_howto

### Channel Comparison Table

| Feature | Review | Question | Chat |
|---------|--------|----------|------|
| Max length | 500 | 500 | 1000 |
| Public | Yes | Yes | No (private) |
| Guardrail strictness | High | High | Low |
| Rating available | Yes | No | No |
| Promo code eligible | Yes (5-star) | No | No |
| Return mention check | Yes | Yes | No |
| Blame phrase severity | error | error | warning |

---

## 6. Promo Code Injection

### When Promo Codes Are Inserted

Promo code injection happens at **Step 5b** of the pipeline, after the AI draft is generated but before guardrails check. It requires ALL of the following conditions:

1. `rating == 5` (only 5-star reviews)
2. `channel == "review"` (not questions or chats)
3. `sla_config["auto_response_promo_on_5star"] == True` (seller opted in)

### How It Works

1. Read promo settings from `RuntimeSetting` table:
   - Key: `promo_settings_v1:seller:{seller_id}`
   - Value: JSON with `promo_codes` array

2. Find first active promo code that:
   - Has `active: true`
   - Has `channels.reviews_positive: true`
   - Has a non-empty `code`

3. Append promo text to the AI-generated reply:
   ```
   {original_reply_text}

   Дарим промокод {CODE} на {discount_label} на следующий заказ!
   ```

### Promo Code Data Structure

```json
{
  "promo_codes": [
    {
      "code": "THANKS10",
      "active": true,
      "discount_label": "скидку 10%",
      "channels": {
        "reviews_positive": true,
        "reviews_negative": false
      }
    }
  ]
}
```

### Failure Handling

- If no promo codes exist, the reply is sent without a promo (non-blocking)
- If promo insertion fails (exception), the reply is sent without a promo
- Promo code used is logged in the InteractionEvent details

---

## 7. Configuration

### SLA Config Keys for Auto-Response

All auto-response settings are stored in the SLA config (`RuntimeSetting` table, key `sla_config_v1:seller:{seller_id}`).

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `auto_response_enabled` | bool | `false` | Master toggle for auto-responses |
| `auto_response_channels` | list[str] | `["review"]` | Which channels allow auto-response |
| `auto_response_nm_ids` | list[int] | `[]` (all) | Article whitelist (empty = all articles) |
| `auto_response_scenarios` | dict | See below | Per-intent scenario config |
| `auto_response_promo_on_5star` | bool | `false` | Insert promo code for 5-star reviews |
| `auto_response_intents` | list[str] | `["thanks"]` | Legacy: allowed intents list |
| `auto_response_delay` | dict | See below | Timing between responses |

### Delay Configuration

```json
{
  "auto_response_delay": {
    "min_seconds": 3,
    "max_seconds": 8,
    "word_count_factor": 0.025
  }
}
```

The delay between auto-responses is calculated as:
```
base_delay = random.uniform(min_seconds, max_seconds)
total_delay = min(base_delay + word_count * word_count_factor, 12)
```

This produces a natural-looking 3-12 second delay between responses.

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/settings` | Read all settings including auto-response config |
| `PUT` | `/api/settings` | Update settings (auto-response fields sync to SLA config) |
| `GET` | `/api/settings/auto-response/presets` | List available presets (safe/balanced/max) |
| `POST` | `/api/settings/auto-response/apply-preset` | Apply a preset |
| `GET` | `/api/settings/sla-config` | Read raw SLA config |
| `PUT` | `/api/settings/sla-config` | Update SLA config directly |
| `POST` | `/api/settings/sla-config/reset` | Reset to defaults |

### Settings Sync

When settings are updated via `PUT /api/settings`, auto-response fields are **synced** to the SLA config:

```python
# In settings.py, after saving settings:
current_sla["auto_response_enabled"] = payload.settings.auto_replies_positive
current_sla["auto_response_channels"] = payload.settings.auto_response_channels
current_sla["auto_response_nm_ids"] = payload.settings.auto_response_nm_ids
current_sla["auto_response_scenarios"] = new_scenarios
current_sla["auto_response_promo_on_5star"] = payload.settings.auto_response_promo_on_5star
```

---

## 8. Celery Integration

### Task Registration

```python
@celery_app.task(
    name="app.tasks.sync.process_auto_responses",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def process_auto_responses(self):
    ...
```

### Beat Schedule

```python
"process-auto-responses-every-3min": {
    "task": "app.tasks.sync.process_auto_responses",
    "schedule": 180.0,  # Every 3 minutes
}
```

### Execution Flow

1. **Every 3 minutes**, Celery Beat triggers `process_auto_responses`
2. The task queries **all active sellers** with API credentials
3. For each seller, checks if `auto_response_enabled == True`
4. Queries eligible interactions:
   - `status = "open"`
   - `needs_response = True`
   - `is_auto_response = False`
   - `rating >= 4`
   - `channel` in allowed channels
   - `nm_id` in whitelist (if configured)
5. **Limit**: max 10 interactions per seller per cycle
6. For each interaction:
   - Run AI analysis (intent classification)
   - Run auto-response pipeline (9 steps)
   - If sent, sleep for a calculated delay (3-12 seconds)
7. Log totals: `auto_response: processed=N sent=M`

### Retry Policy

- `max_retries = 1` (retry once on failure)
- `default_retry_delay = 30` seconds
- If the task fails after retry, it is **abandoned** (next cycle will pick up remaining interactions)

### Interaction with Other Tasks

| Task | Schedule | Relationship |
|------|----------|-------------|
| `sync_all_sellers` | 30s | Syncs new reviews/questions from WB (creates interactions) |
| `sync_all_seller_interactions` | 30s | Syncs review/question data |
| `analyze_pending_chats` | 2min | AI analysis for chats (separate from auto-response) |
| `process_auto_responses` | 3min | Processes eligible interactions for auto-response |
| `check_sla_escalation` | 5min | Escalates interactions that breach SLA |
| `auto_close_inactive_chats` | 24h | Closes chats inactive for 10+ days |

### Timing Considerations

- New interactions arrive every 30 seconds (sync cycle)
- Auto-responses are processed every 3 minutes
- **Worst case latency**: ~3.5 minutes (interaction arrives just after auto-response cycle)
- **Best case latency**: ~30 seconds (interaction arrives just before auto-response cycle)
- Max 10 interactions per seller per cycle prevents blocking other sellers

---

## 9. WB API Integration

### Send Reply by Channel

The `_send_reply` function routes to the appropriate WB connector based on channel:

```python
async def _send_reply(db, interaction, seller, reply_text) -> bool:
    channel = interaction.channel or "review"

    if channel == "review":
        connector = await get_wb_feedbacks_connector_for_seller(seller.id, db)
        return await connector.answer_feedback(
            feedback_id=interaction.external_id,
            text=reply_text,
        )

    elif channel == "question":
        connector = await get_wb_questions_connector_for_seller(seller.id, db)
        state = "wbRu"  # default state, overridden from extra_data if available
        await connector.patch_question(
            question_id=interaction.external_id,
            state=state,
            answer_text=reply_text,
        )
        return True

    elif channel == "chat":
        connector = await get_wb_connector_for_seller(seller.id, db)
        await connector.send_message(chat_id=interaction.external_id, text=reply_text)
        return True
```

### Connector Summary

| Channel | Connector | WB API Endpoint |
|---------|-----------|----------------|
| review | `WBFeedbacksConnector` | `POST /create_task_fb` (WBCON) |
| question | `WBQuestionsConnector` | `PATCH /question/{id}` |
| chat | `WBConnector` | `POST /chat/send/message` |

### Question State Handling

For questions, the reply requires a `state` parameter:

- Default: `"wbRu"` (standard response)
- Can be `"none"` (no state change)
- Read from `interaction.extra_data["state"]` if present

### Sandbox Mode

When `seller.sandbox_mode` is True (set on the Seller model), the message send is simulated:

```python
if seller.sandbox_mode:
    message.status = "sent"
    message.external_message_id = f"sandbox_{uuid.uuid4().hex[:12]}"
    chat.chat_status = "responded"
    # NOT sent to marketplace API
```

---

## 10. Monitoring

### InteractionEvent Types

The auto-response system logs the following event types in the `interaction_events` table:

| event_type | When | Details |
|------------|------|---------|
| `auto_response_sent` | Auto-response successfully sent | `intent`, `rating`, `draft_source`, `reply_length`, `promo_code` (if used) |
| `auto_response_sandbox` | Sandbox mode: draft generated but not sent | Same as above + `sandbox: true` |

### Event Details Schema

```json
{
  "intent": "thanks",
  "rating": 5,
  "draft_source": "ai_deepseek",
  "reply_length": 142,
  "promo_code": "THANKS10"  // optional, only if promo was inserted
}
```

### Interaction Extra Data

After a successful auto-response, `interaction.extra_data` is updated with:

```json
{
  "last_reply_text": "Спасибо за отзыв! ...",
  "last_reply_source": "auto_response",
  "last_reply_at": "2026-02-17T14:30:00+00:00",
  "auto_response_intent": "thanks",
  "auto_response_draft_source": "ai_deepseek",
  "last_ai_draft": { ... }
}
```

### Logging Levels

| Level | When |
|-------|------|
| `DEBUG` | Skipped interactions (disabled, wrong channel, wrong intent, etc.) |
| `INFO` | **BLOCKED by rating** (safety guard), **BLOCKED by guardrails**, **SUCCESS** |
| `WARNING` | Errors in individual steps (config read failure, draft failure, send failure) |
| `ERROR` | Top-level task failure (in Celery task wrapper) |

### Log Message Patterns

```
# Success
auto_response: SUCCESS interaction=123 seller=5 intent=thanks rating=5 len=142 source=ai_deepseek

# Blocked by rating
auto_response: BLOCKED -- rating=3 < 4 for interaction=456 seller=5 (safety guard)

# Blocked by guardrails
auto_response: BLOCKED by guardrails interaction=789 seller=5 warnings=[Запрещённая фраза: "бот"]

# Skipped (disabled)
auto_response: disabled for seller=5, skipping interaction=101

# Skipped (wrong channel)
auto_response: channel=chat not in allowed_channels=['review'] for seller=5 interaction=102

# Task summary
auto_response: processed=8 sent=5
```

### Metrics Queries

To analyze auto-response performance, query `interaction_events`:

```sql
-- Auto-response success rate by seller (last 7 days)
SELECT
    seller_id,
    COUNT(*) FILTER (WHERE event_type = 'auto_response_sent') AS sent,
    COUNT(*) AS total_events
FROM interaction_events
WHERE created_at > NOW() - INTERVAL '7 days'
  AND event_type LIKE 'auto_response%'
GROUP BY seller_id;

-- Auto-response by intent distribution
SELECT
    details->>'intent' AS intent,
    COUNT(*) AS count
FROM interaction_events
WHERE event_type = 'auto_response_sent'
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY details->>'intent'
ORDER BY count DESC;

-- Promo code usage
SELECT
    details->>'promo_code' AS promo_code,
    COUNT(*) AS times_used
FROM interaction_events
WHERE event_type = 'auto_response_sent'
  AND details->>'promo_code' IS NOT NULL
GROUP BY details->>'promo_code';
```
