# Auto-Response Guardrails — Complete Reference

> Last updated: 2026-02-17
> Status: Active

---

## Table of Contents

1. [Standard Guardrails](#1-standard-guardrails)
2. [Auto-Response Guardrails (Stricter)](#2-auto-response-guardrails-stricter)
3. [Banned Phrases — Complete List](#3-banned-phrases--complete-list)
4. [Max Length Limits per Channel](#4-max-length-limits-per-channel)
5. [Return Mention Detection](#5-return-mention-detection)
6. [Language Validation](#6-language-validation)
7. [How to Add New Banned Phrases](#7-how-to-add-new-banned-phrases)
8. [Examples — Blocked vs. Allowed Responses](#8-examples--blocked-vs-allowed-responses)

---

**Source of truth:** `backend/app/services/guardrails.py`

All banned phrases, replacements, and length constraints are defined in this single file. Both the AI draft generation and the auto-response pipeline reference this module.

---

## 1. Standard Guardrails

Standard guardrails apply to **all replies** (manual and automated) at validation time. They are invoked via:

- `apply_guardrails(draft_text, channel, customer_text)` -- returns `(text, warnings)`
- `validate_reply_text(text, channel, customer_text)` -- returns `{valid, violations, warnings}`

### What Gets Checked

| Check | Severity in review/question | Severity in chat |
|-------|----------------------------|------------------|
| AI/bot mentions | error | error |
| False promises | error | N/A (not checked) |
| Blame phrases | error | warning |
| Dismissive phrases | error | N/A (not checked) |
| Unsolicited return mention | error | N/A (not checked) |
| Too long | warning | warning |
| Too short | warning | N/A (not checked) |

### Severity Levels

| Level | Effect in manual reply | Effect in auto-response |
|-------|----------------------|------------------------|
| `error` | `validate_reply_text` returns `valid: false` (send blocked) | Auto-response is **BLOCKED** (not sent) |
| `warning` | `validate_reply_text` returns `valid: true` with warnings (send allowed) | Auto-response is **allowed** (warnings are logged) |

---

## 2. Auto-Response Guardrails (Stricter)

When the auto-response pipeline runs, guardrails are **stricter** than for manual replies:

```python
# In auto_response.py, Step 6:
_, warnings = apply_guardrails(reply_text, channel, customer_text)

# Block on ANY error-severity warning
error_warnings = [w for w in warnings if w.get("severity") == "error"]
if error_warnings:
    return False  # BLOCKED
```

### Key Differences from Manual Mode

| Aspect | Manual Reply | Auto-Response |
|--------|-------------|---------------|
| Error-severity warnings | Block send (API returns 400) | Block auto-response silently |
| Warning-severity warnings | Show warning, allow send | Allow auto-response, log warning |
| Failure mode | User sees error message | Silent skip (seller can reply manually) |
| Post-generation cleanup | Not applied automatically | `replace_banned_phrases()` applied during draft generation |

### Post-Generation Cleanup

The AI draft generator runs `replace_banned_phrases()` on generated text **before** guardrails check. This is a proactive cleanup step:

```python
# In guardrails.py
def replace_banned_phrases(text: str) -> str:
    """Replace known banned phrases with safe alternatives."""
    for phrase, replacement in BANNED_PHRASE_REPLACEMENTS.items():
        if phrase.lower() in result.lower():
            if replacement:
                result = re.sub(re.escape(phrase), replacement, result, flags=re.IGNORECASE)
            else:
                result = re.sub(r'\s*' + re.escape(phrase) + r'\s*', ' ', result, flags=re.IGNORECASE)
    return result
```

This means some banned phrases are automatically replaced with safe alternatives before the guardrails check even runs. If the AI generates "вернём деньги", it gets replaced with "Оформите возврат через ЛК WB".

---

## 3. Banned Phrases -- Complete List

### Category A: AI/Bot Mentions (`ai_mention`)

These are **always error-severity** across ALL channels (including private chat).

| Phrase | Why Banned |
|--------|-----------|
| `ИИ` | Reveals automation |
| `бот` | Reveals automation |
| `нейросеть` | Reveals automation |
| `GPT` | Reveals automation |
| `ChatGPT` | Reveals automation |
| `автоматический ответ` | Reveals automation |
| `искусственный интеллект` | Reveals automation |
| `нейронная сеть` | Reveals automation |

**Word boundary matching:** Short tokens like "ИИ" and "бот" use `\b` word boundaries. This means "работа" does NOT match "бот", and "партиИИ" does NOT match "ИИ".

**Auto-replacement:** Phrases with empty replacement are **removed** (surrounding whitespace collapsed):

| Phrase | Replacement |
|--------|-------------|
| `ИИ` | _(removed)_ |
| `бот` | _(removed)_ |
| `нейросеть` | _(removed)_ |
| `GPT` | _(removed)_ |
| `ChatGPT` | _(removed)_ |
| `автоматический ответ` | _(removed)_ |

### Category B: False Promises (`promise`)

These are **error-severity in review and question** channels. Not checked in chat.

| Phrase | Why Banned | Safe Replacement |
|--------|-----------|-----------------|
| `вернём деньги` | Seller cannot guarantee refunds on WB | `Оформите возврат через ЛК WB` |
| `вернем деньги` | Same (without ё) | `Оформите возврат через ЛК WB` |
| `гарантируем возврат` | False authority | `Оформите возврат через ЛК WB` |
| `гарантируем замену` | False authority | `Оформите возврат через ЛК WB` |
| `полный возврат` | False promise | `возврат через ЛК WB` |
| `бесплатную замену` | False promise | `возврат через ЛК WB` |
| `бесплатная замена` | False promise | `возврат через ЛК WB` |
| `компенсируем` | False promise | _(no replacement)_ |
| `компенсация` | False promise | _(no replacement)_ |
| `мы одобрим возврат` | False authority | `Оформите возврат через ЛК WB` |
| `мы одобрим заявку` | False authority | `Оформите возврат через ЛК WB` |
| `доставим завтра` | Seller doesn't control logistics | `Со своей стороны товар отгружен` |
| `отменим ваш заказ` | Seller can't cancel WB orders | `Вы можете отменить заказ в ЛК WB` |
| `ускорим доставку` | Seller doesn't control logistics | `Со своей стороны товар отгружен` |

### Category C: Blame Phrases (`blame`)

| Phrase | Why Banned | Severity (review/question) | Severity (chat) |
|--------|-----------|---------------------------|-----------------|
| `вы неправильно` | Blaming customer | error | warning |
| `вы не так` | Blaming customer | error | warning |
| `ваша вина` | Blaming customer | error | warning |
| `сами виноваты` | Blaming customer | error | warning |
| `вы ошиблись` | Blaming customer | error | warning |
| `ваша ошибка` | Blaming customer | error | warning |

**Auto-replacement:** Blame phrases are **removed** (replaced with empty string):

| Phrase | Replacement |
|--------|-------------|
| `вы неправильно` | _(removed)_ |
| `вы не так` | _(removed)_ |
| `ваша вина` | _(removed)_ |
| `сами виноваты` | _(removed)_ |

### Category D: Dismissive Phrases (`dismissive`)

These are **error-severity in review and question**. Not checked in chat.

| Phrase | Why Banned | Safe Replacement |
|--------|-----------|-----------------|
| `обратитесь в поддержку` | Dismissive, shifts responsibility | `Мы со своей стороны проверим ситуацию` |
| `напишите в поддержку` | Same | `Мы со своей стороны проверим ситуацию` |
| `мы не можем повлиять` | Dismissive | `Со своей стороны мы передали информацию` |

### Category E: Legal Admissions (`legal`)

| Phrase | Why Banned | Safe Replacement |
|--------|-----------|-----------------|
| `характеристики не соответствуют` | Legal admission of false advertising | `возможен дефект конкретного экземпляра` |
| `наша ошибка` | Legal admission of fault | `нештатная ситуация, разбираемся` |
| `мы виноваты` | Legal admission of fault | `нештатная ситуация, разбираемся` |

### Category F: Internal Jargon (`jargon`)

| Phrase | Why Banned | Safe Replacement |
|--------|-----------|-----------------|
| `уважаемый клиент` | Overly formal, robotic | _(removed)_ |
| `уважаемый покупатель` | Overly formal, robotic | _(removed)_ |
| `пересорт` | Internal warehouse term | `прислали не тот товар` |
| `FBO` | Internal logistics term | `склад WB` |
| `FBS` | Internal logistics term | `склад продавца` |
| `SKU` | Internal code | `артикул` |

---

## 4. Max Length Limits per Channel

Limits match Wildberries API constraints:

| Channel | Max Length | Min Length | Constant Name |
|---------|-----------|-----------|---------------|
| Review | 500 chars | 20 chars | `REPLY_MAX_LENGTH_REVIEW` |
| Question | 500 chars | 20 chars | `REPLY_MAX_LENGTH_QUESTION` |
| Chat | 1000 chars | _(no min)_ | `REPLY_MAX_LENGTH_CHAT` |
| Unknown | 500 chars | 20 chars | Falls back to review limits |

### Severity

| Violation | Severity | Effect on Auto-Response |
|-----------|----------|------------------------|
| Too long | `warning` | Allowed (but logged) |
| Too short | `warning` | Allowed (but logged) |

Note: Length violations are **warnings**, not errors. They do not block auto-responses. However, the WB API may reject responses that exceed its limits.

### Getter Function

```python
def get_max_length(channel: str) -> int:
    if channel == "chat":
        return REPLY_MAX_LENGTH_CHAT  # 1000
    return REPLY_MAX_LENGTH_REVIEW    # 500
```

---

## 5. Return Mention Detection

### The Rule

**A response must NOT mention returns/refunds unless the customer explicitly asked for one.**

This prevents the auto-response from proactively suggesting returns -- which could lead to unnecessary product returns and revenue loss.

### How It Works

1. Check if the customer's text contains return trigger words:
   ```python
   RETURN_TRIGGER_WORDS = [
       "возврат", "вернуть", "замена", "заменить", "обменять", "обмен"
   ]
   ```

2. Check if the reply mentions return/refund:
   ```python
   RETURN_MENTION_PATTERNS = [
       "возврат", "вернуть", "вернём", "вернем", "замен", "обмен"
   ]
   ```

3. If the reply mentions returns BUT the customer did NOT ask for one:
   - **Error-severity warning** in review and question channels
   - **Not checked** in chat channel (private, more flexible)

### Detection Logic

```python
def check_return_mention_without_trigger(reply_text, customer_text) -> bool:
    # If customer asked for return -> reply can mention it (False = no violation)
    if has_return_trigger(customer_text):
        return False

    # If customer didn't ask but reply mentions it -> violation (True)
    return any(word in reply_text.lower() for word in RETURN_MENTION_PATTERNS)
```

### Examples

| Customer Text | Reply Text | Violation? |
|--------------|------------|-----------|
| "Товар отличный, спасибо!" | "Спасибо! Если нужен возврат..." | YES -- customer didn't ask |
| "Хочу вернуть товар" | "Оформите возврат через ЛК WB" | No -- customer asked for return |
| "Размер не подошёл" | "Жаль! Если нужна замена..." | YES -- customer didn't ask for exchange |
| "Можно обменять на другой?" | "Да, оформите обмен через ЛК WB" | No -- customer asked for exchange |

---

## 6. Language Validation

### Russian Requirement

All auto-responses are generated and validated in Russian. The system prompts for AI are in Russian and instruct the model to respond in Russian.

The guardrails system operates on Russian text:
- All banned phrases are in Russian (with ё/е variants where applicable)
- Pattern matching is **case-insensitive** (`re.IGNORECASE`)
- Word boundaries work with Cyrillic characters

### Character Encoding

- All text is UTF-8
- Both `ё` and `е` variants are checked where relevant:
  - `вернём` and `вернем` are both in the banned list
  - `ёв` suffix is checked alongside `ев` in name detection

### No Explicit Language Detection

The current system does not explicitly validate that the response is in Russian. The AI model (DeepSeek) generates Russian responses due to the Russian system prompt. If a non-Russian response is generated, it would:
- Likely pass guardrails (banned phrases are Russian-specific)
- Be sent to WB (which expects Russian text)

This is a known limitation; in practice, the AI model consistently generates Russian text.

---

## 7. How to Add New Banned Phrases

### Step 1: Identify the Category

Choose the appropriate category for the new phrase:

| Category | List Name | For |
|----------|-----------|-----|
| AI mentions | `BANNED_PHRASES_COMMON` | Any AI/automation disclosure |
| Promises | `BANNED_PHRASES_PROMISES` | Commitments seller can't make |
| Blame | `BANNED_PHRASES_BLAME` | Customer-blaming language |
| Dismissive | `BANNED_PHRASES_DISMISSIVE` | Responsibility-shifting |
| Legal | `BANNED_PHRASES_LEGAL` | Legal liability admissions |
| Jargon | `BANNED_PHRASES_JARGON` | Internal terms customers don't know |

### Step 2: Add to the Phrase List

Edit `backend/app/services/guardrails.py`:

```python
# Example: adding a new promise phrase
BANNED_PHRASES_PROMISES: List[str] = [
    "вернём деньги",
    "вернем деньги",
    # ... existing phrases ...
    "подарим скидку",     # <-- NEW: don't promise discounts
]
```

### Step 3: Add Replacement (Optional)

If the phrase should be auto-replaced (not just flagged), add to `BANNED_PHRASE_REPLACEMENTS`:

```python
BANNED_PHRASE_REPLACEMENTS: Dict[str, str] = {
    # ... existing replacements ...
    "подарим скидку": "предложим специальные условия",  # <-- NEW
}
```

Use empty string `""` to remove the phrase entirely:
```python
"внутренний термин": "",  # Will be removed from text
```

### Step 4: Test

```bash
# Test that the new phrase is detected
python3 -c "
from app.services.guardrails import check_banned_phrases
violations = check_banned_phrases('Мы подарим скидку на следующий заказ!')
print(violations)
# Expected: [{'phrase': 'подарим скидку', 'category': 'promise'}]
"
```

```bash
# Test replacement
python3 -c "
from app.services.guardrails import replace_banned_phrases
result = replace_banned_phrases('Мы подарим скидку на следующий заказ!')
print(result)
# Expected: 'Мы предложим специальные условия на следующий заказ!'
"
```

### Step 5: Update AI System Prompt

If the phrase is common enough that the AI generates it frequently, add it to the "ЗАПРЕЩЕНО" section of the relevant system prompt in `ai_analyzer.py`:

```python
REVIEW_DRAFT_SYSTEM = """...
КРИТИЧЕСКИ ВАЖНО — ЗАПРЕЩЕНО писать:
...
8. "подарим скидку" — нельзя обещать скидки без подтверждения
"""
```

### Pattern Matching Details

Single-word phrases use word boundaries:
```python
# "бот" matches "бот" but NOT "работа" or "ботаник"
re.compile(r"\bбот\b", re.IGNORECASE)
```

Multi-word phrases use exact substring match:
```python
# "вернём деньги" matches anywhere in text
re.compile(re.escape("вернём деньги"), re.IGNORECASE)
```

---

## 8. Examples -- Blocked vs. Allowed Responses

### BLOCKED -- AI Mention

| Input | Draft | Violation | Result |
|-------|-------|-----------|--------|
| "Спасибо!" (5 stars) | "Спасибо за отзыв! Наш **бот** уже это учёл." | `banned_phrase: "бот" (ai_mention)` | BLOCKED |
| "Отличный товар" (5 stars) | "Благодарим! Ответ подготовлен **ИИ**-помощником." | `banned_phrase: "ИИ" (ai_mention)` | BLOCKED |
| Chat message | "Это **автоматический ответ**, менеджер скоро подключится." | `banned_phrase: "автоматический ответ" (ai_mention)` | BLOCKED |

### BLOCKED -- False Promise

| Input | Draft | Violation | Result |
|-------|-------|-----------|--------|
| "Когда доставите?" | "**Доставим завтра**, не переживайте!" | `banned_phrase: "доставим завтра" (promise)` | BLOCKED |
| "Хочу вернуть" | "Конечно, **гарантируем возврат** в течение дня!" | `banned_phrase: "гарантируем возврат" (promise)` | BLOCKED |

### BLOCKED -- Unsolicited Return

| Input | Draft | Violation | Result |
|-------|-------|-----------|--------|
| "Спасибо, хороший товар!" | "Рады! Если не подойдёт — оформите **возврат**." | `unsolicited_return` | BLOCKED |
| "Нравится цвет!" (4 stars) | "Спасибо! При необходимости всегда можно **вернуть**." | `unsolicited_return` | BLOCKED |

### BLOCKED -- Blame

| Input | Draft | Violation | Result |
|-------|-------|-----------|--------|
| "Не работает!" (2 stars) | "Скорее всего **вы неправильно** подключили." | `banned_phrase: "вы неправильно" (blame)` | BLOCKED |
| "Сломалось" (1 star) | "К сожалению, это **ваша ошибка** при эксплуатации." | `banned_phrase: "ваша ошибка" (blame)` | BLOCKED |

### ALLOWED -- Correct Responses

| Input | Draft | Why Allowed |
|-------|-------|-------------|
| "Спасибо за товар!" (5 stars) | "Спасибо за тёплые слова! Рады, что товар понравился. Приятных покупок!" | No banned phrases, correct length, no unsolicited return |
| "Отличное качество" (4 stars) | "Благодарим за отзыв! Ваше мнение очень ценно для нас." | Clean response |
| "Хочу вернуть товар" (3 stars) | "Здравствуйте! Оформите возврат через ЛК WB с пометкой «не подошло»." | Return mention is OK because customer asked for it |
| "Где мой заказ?" (question) | "Здравствуйте! Со своей стороны проверили — заказ передан в доставку. Отслеживайте статус в ЛК WB." | No banned phrases, factual response |
| "Подойдёт на iPhone 15?" (question) | "Здравствуйте! Спасибо за вопрос! Да, товар совместим с iPhone 15." | Clean, helpful response |

### ALLOWED (with warnings) -- Length Issues

| Input | Draft | Warning | Result |
|-------|-------|---------|--------|
| "Спасибо!" (5 stars) | "Спасибо!" (10 chars) | `too_short (10 < 20)` -- warning severity | ALLOWED (auto-response sends, warning logged) |
| "Расскажите о товаре" | (600 char response) | `too_long (600 > 500)` -- warning severity | ALLOWED (but WB API may truncate) |

### Channel-Specific Differences

The same draft may be treated differently depending on channel:

| Draft Text | Review Channel | Question Channel | Chat Channel |
|------------|---------------|------------------|-------------|
| "Спасибо! Наш **бот** рад помочь." | BLOCKED (error) | BLOCKED (error) | BLOCKED (error) |
| "**Вы неправильно** собрали." | BLOCKED (error) | BLOCKED (error) | WARNING (not blocked) |
| "**Обратитесь в поддержку** WB." | BLOCKED (error) | BLOCKED (error) | ALLOWED (not checked) |
| "Мы **вернём деньги**!" | BLOCKED (error) | BLOCKED (error) | ALLOWED (not checked) |
| "Оформите **возврат**" (unsolicited) | BLOCKED (error) | BLOCKED (error) | ALLOWED (not checked) |

### Post-Replacement Examples

When `replace_banned_phrases()` runs during draft generation:

| Original AI Output | After Replacement | Guardrails Result |
|-------------------|-------------------|-------------------|
| "Мы **вернём деньги** в течение 3 дней" | "Мы **Оформите возврат через ЛК WB** в течение 3 дней" | May still be flagged (grammatically broken) |
| "**Обратитесь в поддержку** WB" | "**Мы со своей стороны проверим ситуацию**" | ALLOWED |
| "Это **пересорт** на складе" | "Это **прислали не тот товар** на складе" | ALLOWED |
| "Товар на **FBO** складе" | "Товар на **склад WB** складе" | ALLOWED (may read awkwardly) |
| "Спасибо! Ответ от **ИИ**." | "Спасибо! Ответ от ." | Cleaned up, but odd spacing is collapsed by `re.sub(r'\s+', ' ', ...)` |
