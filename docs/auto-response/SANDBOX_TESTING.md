# Auto-Response Testing Guide — Sandbox & Safe Testing

> Last updated: 2026-02-17
> Status: Active

---

## Table of Contents

1. [Sandbox Mode](#1-sandbox-mode)
2. [Preview Endpoint](#2-preview-endpoint)
3. [Local Development Testing](#3-local-development-testing)
4. [Production Testing (Safe)](#4-production-testing-safe)
5. [What to Check Before Going Live](#5-what-to-check-before-going-live)
6. [Troubleshooting](#6-troubleshooting)
7. [Demo Data for Testing](#7-demo-data-for-testing)

---

## 1. Sandbox Mode

### What It Does

Sandbox mode runs the **full auto-response pipeline** (AI analysis, draft generation, guardrails check) but **does not send the response to the Wildberries API**. Instead, the generated draft is stored in the interaction's metadata for review.

This allows sellers and developers to:
- Verify AI response quality without risking real customer interactions
- Test guardrails by reviewing what gets blocked vs. what passes
- Validate promo code injection logic
- Confirm intent classification accuracy on real marketplace data

### How It Works Internally

When `seller.sandbox_mode` is True, the message send step is intercepted in `sync.py`:

```python
# backend/app/tasks/sync.py (line ~1275)
if seller.sandbox_mode:
    message.status = "sent"
    message.external_message_id = f"sandbox_{uuid.uuid4().hex[:12]}"
    chat.chat_status = "responded"
    chat.unread_count = 0
    await db.commit()
    logger.info(f"[SANDBOX] Message {message_id} simulated (not sent to {chat.marketplace})")
    return
```

Key behavior:
- The message gets a `sandbox_` prefixed external ID (not a real WB message ID)
- The chat status is updated to "responded" (as if the message was sent)
- The message is marked as "sent" in the database
- **No HTTP request is made to the Wildberries API**

### How to Enable

Toggle sandbox mode via the settings API:

```bash
# Enable sandbox mode
curl -X PUT http://localhost:8001/api/settings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "sandbox_mode": true
    }
  }'
```

Or set it directly on the seller model (database level):

```sql
UPDATE sellers SET sandbox_mode = true WHERE id = <seller_id>;
```

### What Gets Logged

When auto-response runs in sandbox mode:

1. **InteractionEvent** with `event_type = "auto_response_sandbox"` is created
2. The draft is stored in `interaction.extra_data["sandbox_auto_response"]`:

```json
{
  "sandbox_auto_response": {
    "text": "Спасибо за тёплые слова! Рады, что товар оправдал ожидания.",
    "intent": "thanks",
    "rating": 5,
    "guardrails_passed": true,
    "guardrails_warnings": [],
    "promo_code": null,
    "draft_source": "ai_deepseek",
    "timestamp": "2026-02-17T14:30:00+00:00"
  }
}
```

3. Server logs show `[SANDBOX]` prefix:
```
[SANDBOX] Message 456 simulated (not sent to wildberries)
```

### How to Verify

1. Check InteractionEvent records:
```sql
SELECT ie.event_type, ie.details, ie.created_at
FROM interaction_events ie
WHERE ie.seller_id = <seller_id>
  AND ie.event_type LIKE 'auto_response%'
ORDER BY ie.created_at DESC
LIMIT 20;
```

2. Check interaction extra_data:
```sql
SELECT id, extra_data->>'sandbox_auto_response' as sandbox_draft
FROM interactions
WHERE seller_id = <seller_id>
  AND extra_data->>'sandbox_auto_response' IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

3. Check message external IDs (sandbox messages have `sandbox_` prefix):
```sql
SELECT id, text, external_message_id, status
FROM messages
WHERE external_message_id LIKE 'sandbox_%'
ORDER BY created_at DESC;
```

---

## 2. Preview Endpoint

### `POST /api/auto-response/preview`

The preview endpoint lets you test what the AI would respond to a given input **without creating any database records** or sending anything. It runs:
1. Intent classification
2. Response generation
3. Guardrails check

And returns the full result for inspection.

### Request Format

```json
{
  "text": "Customer's message text",
  "rating": 5,
  "channel": "review",
  "product_name": "Optional product name"
}
```

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `text` | Yes | string | The customer's message |
| `rating` | No | int (1-5) | Review rating (null for questions/chats) |
| `channel` | No | string | `"review"`, `"question"`, or `"chat"` (default: `"review"`) |
| `product_name` | No | string | Product name for context (default: "Товар") |

### Response Format

```json
{
  "intent": "thanks",
  "sentiment": "positive",
  "urgency": "low",
  "recommendation": "Спасибо за тёплые слова! Рады, что товар оправдал ожидания.",
  "auto_response_eligible": true,
  "guardrails": {
    "passed": true,
    "warnings": [],
    "violations": []
  },
  "would_send": true,
  "blocked_reason": null
}
```

### Example Requests by Scenario

#### Thanks (Благодарность) -- 5-star review

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Отличный товар! Всё понравилось, спасибо!",
    "rating": 5,
    "channel": "review",
    "product_name": "Чехол для iPhone 15"
  }'
```

Expected response:
```json
{
  "intent": "thanks",
  "sentiment": "positive",
  "urgency": "low",
  "recommendation": "Спасибо за отзыв! Рады, что чехол понравился. Приятных покупок!",
  "auto_response_eligible": true,
  "guardrails": {
    "passed": true,
    "warnings": [],
    "violations": []
  },
  "would_send": true,
  "blocked_reason": null
}
```

#### Delivery Status (WISMO) -- question

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Когда приедет мой заказ? Уже 5 дней жду",
    "rating": null,
    "channel": "question"
  }'
```

Expected response:
```json
{
  "intent": "delivery_status",
  "sentiment": "negative",
  "urgency": "normal",
  "recommendation": "Здравствуйте! Со своей стороны проверили — ваш заказ передан в доставку. Отслеживайте статус в личном кабинете WB в разделе «Доставки».",
  "auto_response_eligible": true,
  "guardrails": {
    "passed": true,
    "warnings": [],
    "violations": []
  },
  "would_send": true,
  "blocked_reason": null
}
```

#### Pre-Purchase -- question

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Подскажите, подойдёт ли на iPhone 15?",
    "rating": null,
    "channel": "question",
    "product_name": "Защитное стекло"
  }'
```

Expected response:
```json
{
  "intent": "compatibility",
  "sentiment": "neutral",
  "urgency": "high",
  "recommendation": "Здравствуйте! Спасибо за вопрос! Да, защитное стекло совместимо с iPhone 15. С радостью поможем с выбором!",
  "auto_response_eligible": true,
  "guardrails": {
    "passed": true,
    "warnings": [],
    "violations": []
  },
  "would_send": true,
  "blocked_reason": null
}
```

#### Sizing/Fit -- question

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Какой размер брать если обычно ношу M?",
    "rating": null,
    "channel": "question",
    "product_name": "Футболка хлопковая"
  }'
```

#### Defect (should be BLOCKED)

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Пришло сломанное, кнопка не работает",
    "rating": 1,
    "channel": "review"
  }'
```

Expected response:
```json
{
  "intent": "defect_not_working",
  "sentiment": "negative",
  "urgency": "critical",
  "recommendation": "Здравствуйте! Очень жаль, что товар оказался с дефектом...",
  "auto_response_eligible": false,
  "guardrails": {
    "passed": true,
    "warnings": [],
    "violations": []
  },
  "would_send": false,
  "blocked_reason": "intent 'defect_not_working' has action=block; rating 1 < 4 (safety gate)"
}
```

#### Quality Complaint -- low rating

```bash
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Материал дешёвый, не соответствует описанию",
    "rating": 2,
    "channel": "review"
  }'
```

Expected: `would_send: false`, `blocked_reason` mentions rating < 4 and intent = quality_complaint (always blocked).

---

## 3. Local Development Testing

### Step-by-Step Setup

```bash
# 1. Start the backend
cd /path/to/agentiq/apps/chat-center/backend
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

```bash
# 2. Start Celery worker (separate terminal)
cd /path/to/agentiq/apps/chat-center/backend
source venv/bin/activate
celery -A app.tasks worker --loglevel=info
```

```bash
# 3. Start Celery Beat (separate terminal)
cd /path/to/agentiq/apps/chat-center/backend
source venv/bin/activate
celery -A app.tasks beat --loglevel=info
```

### Login and Get Token

```bash
# Login to get auth token
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@example.com",
    "password": "demo123"
  }'

# Response:
# {"access_token": "eyJ...", "token_type": "bearer"}
```

Save the token for subsequent requests:

```bash
export TOKEN="eyJ..."
```

### Enable Sandbox Mode

```bash
curl -X PUT http://localhost:8001/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "sandbox_mode": true
    }
  }'
```

### Enable Auto-Responses with Safe Preset

```bash
# Apply the "safe" preset (only thanks intent on reviews)
curl -X POST http://localhost:8001/api/settings/auto-response/apply-preset \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"preset": "safe"}'
```

```bash
# Enable auto-response
curl -X PUT http://localhost:8001/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "auto_replies_positive": true
    }
  }'
```

### Test Preview

```bash
# Test what AI would respond to a positive review
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Спасибо за отличный товар!",
    "rating": 5,
    "channel": "review"
  }'
```

### Verify Sandbox Results

```bash
# Check recent interaction events
curl http://localhost:8001/api/interactions?limit=10 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Watch Celery Logs

In the Celery worker terminal, you will see:

```
[INFO] Looking for interactions eligible for auto-response
[INFO] auto_response: found 3 eligible interactions for seller=1
[INFO] auto_response: SUCCESS interaction=42 seller=1 intent=thanks rating=5 len=87 source=ai_deepseek
[INFO] auto_response: processed=3 sent=2
```

Or in sandbox mode:

```
[INFO] [SANDBOX] Message 456 simulated (not sent to wildberries)
```

---

## 4. Production Testing (Safe)

### Step-by-step Guide for Production

Follow these steps to safely test auto-responses on a real seller account without sending real responses to customers.

#### Step 1: Enable Sandbox Mode

```bash
# On the production server
curl -X PUT https://agentiq.ru/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "sandbox_mode": true
    }
  }'
```

Verify:
```bash
curl https://agentiq.ru/api/settings \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep sandbox
```

#### Step 2: Configure Auto-Response Settings

Choose a preset or configure manually:

```bash
# Option A: Apply "safe" preset (recommended for first test)
curl -X POST https://agentiq.ru/api/settings/auto-response/apply-preset \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"preset": "safe"}'
```

```bash
# Option B: Configure manually
curl -X PUT https://agentiq.ru/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "auto_replies_positive": true,
      "auto_response_channels": ["review"],
      "auto_response_scenarios": {
        "thanks": {"action": "auto", "enabled": true, "channels": ["review"]}
      }
    }
  }'
```

#### Step 3: Wait for Sync Cycle

The auto-response task runs every **3 minutes** via Celery Beat. Wait at least one cycle (3-5 minutes) for new interactions to be processed.

Monitor via server logs:
```bash
# On the server
sudo journalctl -u agentiq-celery -f | grep auto_response
```

#### Step 4: Check Interaction Events

```sql
-- Connect to production database
SELECT
    ie.event_type,
    ie.details->>'intent' AS intent,
    ie.details->>'rating' AS rating,
    ie.created_at
FROM interaction_events ie
WHERE ie.seller_id = <seller_id>
  AND ie.event_type LIKE 'auto_response%'
ORDER BY ie.created_at DESC
LIMIT 20;
```

#### Step 5: Review AI Drafts

```sql
SELECT
    id,
    text,
    rating,
    extra_data->>'auto_response_intent' AS intent,
    extra_data->>'last_reply_text' AS draft_text,
    extra_data->>'last_reply_source' AS source
FROM interactions
WHERE seller_id = <seller_id>
  AND extra_data->>'last_reply_source' = 'auto_response'
ORDER BY created_at DESC
LIMIT 10;
```

Review each draft for:
- Correct intent classification
- Appropriate tone and content
- No banned phrases slipping through
- Correct promo code (if enabled)

#### Step 6: When Satisfied, Disable Sandbox Mode

```bash
curl -X PUT https://agentiq.ru/api/settings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "sandbox_mode": false
    }
  }'
```

#### Step 7: Enable Auto-Responses for Real

Auto-responses are already enabled from Step 2. With sandbox mode OFF, the system will now send real responses to the Wildberries API.

Monitor the first few real auto-responses:
```bash
sudo journalctl -u agentiq-celery -f | grep "auto_response: SUCCESS"
```

---

## 5. What to Check Before Going Live

### Pre-Launch Checklist

- [ ] **Sandbox tested for at least 10 interactions** -- verify that the AI generates appropriate responses across different review types
- [ ] **Review AI drafts** -- read every sandbox draft and confirm they are appropriate, on-topic, and natural
- [ ] **Guardrails blocking harmful content?** -- verify that responses with banned phrases, false promises, or blame language are blocked
- [ ] **Promo codes inserted correctly?** (if enabled) -- check that only 5-star reviews get promo codes and the text format is correct
- [ ] **Response timing natural?** -- verify the 3-8 second delay between responses (check logs for timing)
- [ ] **nm_id filter working?** (if specific articles) -- confirm that only whitelisted articles trigger auto-responses
- [ ] **Channel filtering correct?** -- confirm responses only go to enabled channels (review/question/chat)
- [ ] **Intent classification accurate?** -- verify that AI correctly identifies thanks vs. complaints vs. questions
- [ ] **No auto-responses on ratings < 4** -- verify the safety gate is working (check logs for "BLOCKED" messages)
- [ ] **SLA config persisted correctly** -- read back the SLA config and verify all settings match expectations
- [ ] **Celery Beat running** -- verify the `process_auto_responses` task is scheduled and executing

### Rating Safety Verification

Run this query to confirm no auto-responses were sent for low ratings:

```sql
-- This should return ZERO rows
SELECT id, rating, extra_data->>'auto_response_intent' AS intent
FROM interactions
WHERE is_auto_response = true
  AND rating < 4;
```

### Guardrails Verification

Test that guardrails catch known bad patterns:

```bash
# This should show guardrails blocking the response
curl -X POST http://localhost:8001/api/auto-response/preview \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Отличный товар!",
    "rating": 5,
    "channel": "review",
    "override_draft": "Спасибо! Наш бот рад помочь!"
  }'
```

Expected: guardrails should flag "бот" as a banned phrase.

---

## 6. Troubleshooting

### "Auto-response not triggering"

**Check in order:**

1. **auto_response_enabled is True?**
   ```bash
   curl http://localhost:8001/api/settings/sla-config \
     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep auto_response_enabled
   ```

2. **Channel is in allowed list?**
   ```bash
   curl http://localhost:8001/api/settings/sla-config \
     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep auto_response_channels
   ```

3. **Scenario for intent is enabled and action=auto?**
   ```bash
   curl http://localhost:8001/api/settings/sla-config \
     -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | grep -A5 auto_response_scenarios
   ```

4. **Rating is >= 4?**
   - Reviews with rating 1-3 are always blocked (hard safety gate)
   - Check: `SELECT rating FROM interactions WHERE id = <id>;`

5. **Interaction status is "open"?**
   - Already-responded interactions are skipped
   - Check: `SELECT status, needs_response, is_auto_response FROM interactions WHERE id = <id>;`

6. **Celery Beat is running?**
   ```bash
   sudo systemctl status agentiq-celery-beat
   ```

7. **Celery worker logs?**
   ```bash
   sudo journalctl -u agentiq-celery -f | grep auto_response
   ```

### "Guardrails blocking everything"

**Diagnosis:**

1. Run the preview endpoint to see exact warnings:
   ```bash
   curl -X POST http://localhost:8001/api/auto-response/preview \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"text": "Your test text", "rating": 5, "channel": "review"}'
   ```

2. Check for common causes:
   - AI generating responses with "бот", "ИИ", or other AI mentions
   - AI suggesting returns when customer didn't ask (unsolicited_return check)
   - Response too long (>500 chars for review/question, >1000 for chat)
   - Response too short (<20 chars)

3. Check the banned phrases list in `guardrails.py` -- it may be catching legitimate words due to word-boundary matching.

### "Wrong intent classification"

**Diagnosis:**

1. Test with the preview endpoint and different text variations:
   ```bash
   # Test same message with slight variations
   curl -X POST http://localhost:8001/api/auto-response/preview \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"text": "Спасибо, всё отлично!", "rating": 5, "channel": "review"}'
   ```

2. Check AI analyzer logs for the raw LLM response:
   ```bash
   sudo journalctl -u agentiq-celery -f | grep "ai_analyzer"
   ```

3. Common misclassifications:
   - "Спасибо" with complaints = should be `quality_complaint`, not `thanks`
   - General positive feedback without "спасибо" = may be classified as `other`
   - Questions embedded in reviews = may classify as question intent

### "Promo code not inserting"

**Check:**

1. Rating must be exactly 5 (not 4)
2. Channel must be "review" (not question or chat)
3. `auto_response_promo_on_5star` must be True in SLA config
4. Active promo code must exist with `channels.reviews_positive = true`:
   ```sql
   SELECT key, value
   FROM runtime_settings
   WHERE key LIKE 'promo_settings_v1:seller:%';
   ```

### "Responses look robotic / repetitive"

**Improvement steps:**

1. Check the AI model being used (DeepSeek vs other):
   ```sql
   SELECT key, value FROM runtime_settings WHERE key = 'llm_runtime_config';
   ```

2. Consider adjusting the tone setting in SLA config
3. Check if the product name is being passed correctly (impacts personalization)
4. Review `auto_response_draft_source` in interaction extra_data

### "Task timing / performance issues"

The auto-response task is limited to:
- **10 interactions per seller per cycle** (prevents one seller from blocking others)
- **3-12 second delay between sends** (prevents rate limiting / detection)
- **3-minute cycle** (balance between latency and server load)

If responses are too slow:
- Check Celery worker CPU/memory: `htop` or `sudo systemctl status agentiq-celery`
- Check AI API response times in logs
- Check database connection pool (are queries timing out?)

---

## 7. Demo Data for Testing

### Sample Review Texts by Intent

Use these texts with the preview endpoint to test each intent classification.

#### `thanks` -- Благодарность

```
"Отличный товар! Всё понравилось, спасибо!"
"Супер качество, рекомендую всем! Буду заказывать ещё."
"Спасибо большое! Пришло быстро, всё работает отлично."
"Прекрасный товар за свои деньги. Очень довольна покупкой!"
"Всё как в описании, даже лучше. Спасибо продавцу!"
```

#### `delivery_status` -- Где мой заказ?

```
"Когда приедет мой заказ? Уже 5 дней жду"
"Статус не обновляется второй день, где посылка?"
"Заказ должен был прийти вчера, до сих пор нет"
"Отправили или нет? Трек-номер не отслеживается"
"3 недели жду доставку, это нормально?"
```

#### `pre_purchase` -- Вопрос перед покупкой

```
"Подскажите, подойдёт ли на iPhone 15?"
"Из какого материала сделан корпус?"
"Можно ли использовать на улице в мороз?"
"Подойдёт как подарок мужчине?"
"Есть ли гарантия от производителя?"
```

#### `sizing_fit` -- Какой размер выбрать?

```
"Какой размер брать если обычно ношу M?"
"Размерная сетка соответствует? Или маломерит?"
"Рост 180, вес 75, какой размер посоветуете?"
"Подскажите по размеру обуви, обычно ношу 42"
"Между S и M — какой лучше взять?"
```

#### `availability` -- Есть ли в наличии?

```
"Когда будет в наличии синий цвет?"
"Есть ли размер XXL?"
"Будет ли поступление этого товара?"
"В наличии только белый? Чёрный когда будет?"
"Можно ли заказать, если нет на складе?"
```

#### `compatibility` -- Подойдёт ли к...?

```
"Подойдёт к Samsung Galaxy S24?"
"Совместим ли с macOS?"
"Работает с блютуз 5.0?"
"Подходит для стиральной машины Bosch?"
"Можно использовать с аккумулятором 18650?"
```

#### `defect_not_working` -- Брак, не работает (ALWAYS BLOCKED)

```
"Пришло сломанное, кнопка не работает"
"Не включается, сразу после распаковки"
"Экран разбитый, пришёл с трещиной"
"Брак! Застёжка сломалась в первый же день"
"Провод оголён, опасно для жизни!"
```

#### `quality_complaint` -- Жалоба на качество (ALWAYS BLOCKED)

```
"Материал дешёвый, не соответствует описанию"
"Запах ужасный, пахнет химией"
"Цвет совсем другой, не как на фото"
"Качество отвратительное за такую цену"
"Швы кривые, нитки торчат"
```

#### `wrong_item` -- Прислали не тот товар (ALWAYS BLOCKED)

```
"Заказывала синий, пришёл красный"
"Не тот размер! Заказывал L, пришёл XS"
"Это вообще другой товар! Заказывала чехол, пришла плёнка"
"Прислали б/у вместо нового"
"Артикул не совпадает с заказанным"
```

#### `refund_exchange` -- Возврат или обмен

```
"Хочу оформить возврат, товар не подошёл"
"Можно обменять на другой размер?"
"Как вернуть деньги? Товар не устроил"
"Нужна замена, пришёл с дефектом"
"Хочу отказаться от заказа и вернуть деньги"
```

### Quick Test Script

```bash
#!/bin/bash
# test_auto_response_preview.sh
# Tests all intent types via the preview endpoint

TOKEN="YOUR_TOKEN_HERE"
BASE_URL="http://localhost:8001"

echo "=== Testing auto-response preview ==="

# Thanks (should be auto-eligible)
echo -e "\n--- thanks (rating=5, review) ---"
curl -s -X POST "$BASE_URL/api/auto-response/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Отличный товар! Спасибо!","rating":5,"channel":"review"}' \
  | python3 -m json.tool

# Delivery status (question)
echo -e "\n--- delivery_status (question) ---"
curl -s -X POST "$BASE_URL/api/auto-response/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Когда приедет заказ?","rating":null,"channel":"question"}' \
  | python3 -m json.tool

# Pre-purchase (question)
echo -e "\n--- pre_purchase (question) ---"
curl -s -X POST "$BASE_URL/api/auto-response/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Подойдёт ли на iPhone 15?","rating":null,"channel":"question","product_name":"Защитное стекло"}' \
  | python3 -m json.tool

# Defect (should be BLOCKED)
echo -e "\n--- defect (rating=1, review) -- SHOULD BE BLOCKED ---"
curl -s -X POST "$BASE_URL/api/auto-response/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Пришло сломанное!","rating":1,"channel":"review"}' \
  | python3 -m json.tool

# Quality complaint (should be BLOCKED)
echo -e "\n--- quality_complaint (rating=2, review) -- SHOULD BE BLOCKED ---"
curl -s -X POST "$BASE_URL/api/auto-response/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Качество отвратительное","rating":2,"channel":"review"}' \
  | python3 -m json.tool

echo -e "\n=== Done ==="
```

### Test Matrix

Use this matrix to ensure comprehensive testing:

| Intent | Channel | Rating | Expected: would_send | Expected: blocked_reason |
|--------|---------|--------|---------------------|--------------------------|
| thanks | review | 5 | true | null |
| thanks | review | 4 | true | null |
| thanks | review | 3 | false | rating < 4 |
| thanks | question | null | depends on config | channel not in allowed_channels |
| delivery_status | question | null | depends on config | scenario disabled (safe preset) |
| pre_purchase | question | null | depends on config | scenario disabled (safe preset) |
| defect_not_working | review | 1 | false | intent blocked + rating < 4 |
| quality_complaint | review | 2 | false | intent blocked + rating < 4 |
| wrong_item | review | 1 | false | intent blocked + rating < 4 |
| refund_exchange | review | 4 | false | action=draft (not auto) |
