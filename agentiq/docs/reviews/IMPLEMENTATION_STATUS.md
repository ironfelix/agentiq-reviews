# AgentIQ Implementation Status

**Last Updated**: 2026-02-07
**Active Model**: DeepSeek (for communication analysis)
**Main Contributors**: Claude Sonnet 4.5

---

## 1. Overview

AgentIQ is a Wildberries review analysis platform with LLM-powered communication quality analysis. It analyzes seller responses to customer reviews, detects problematic product variants, estimates revenue impact from poor communication, and provides actionable recommendations.

**Core capabilities:**
- Communication quality scoring (1-10 scale, DeepSeek LLM)
- Response speed calculation (data-based, no LLM)
- Money loss estimation (review-to-purchase conversion methodology)
- Product info fetching (WB Public Card API, no auth)
- Variant comparison, trend detection, reason classification
- Root cause analysis (expectation mismatch vs. defect)

---

## 2. Active Features

### Communication Quality Analysis (LLM-Powered)
- Analyzes ALL reviews (1-5★) for response quality
- Detects 8 response types: blame, ignore, amplify, deny, template, no_answer, ok, good
- Identifies hidden risks (ignored complaints in positive reviews)
- Provides buyer perception insights and action plan
- Outputs: quality_score (1-10), verdict, error_types, worst_responses, hidden_risks, action_plan

### Response Speed Calculation (Data-Based)
- Computed from timestamps (no LLM)
- Metrics: median, avg, max hours
- Separate stats for negative (1-3★) vs all reviews
- Same-day response count, slow response count (>7 days)

### Money Loss Estimation
- Estimates revenue loss from poor communication
- Inputs: review count, time period, product price, LLM quality score
- Assumptions: 3-5% review rate, 30-50% read reviews, category coefficient 0.8
- **CR impact ranges** (updated 2026-02-07):
  - Quality 7-10: 1-2% loss
  - Quality 4-6: 2-4% loss
  - Quality 1-3: 3-6% loss
- Outputs: purchases/month, revenue/month, loss/month (min/max)
- **Disclaimer**: Estimate only, requires real sales data for accuracy

### Product Info Fetching (WB Public Card API)
- No authentication needed
- Returns: name (`imt_name`), description, options, category (`subj_name`), **price**
- URL pattern: `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json`
- Basket number computed from `nmId // 100000` via range table

### Variant Comparison & Trend Detection
- Color normalization (filters non-colors like "4 шт. · 120 м")
- Checks BOTH recent (30-day) AND all-time windows for real colors
- Trend detection: 30-day window or split-half fallback (if <3 reviews)
- Signal detection: >=5 reviews per variant, >=0.3 rating gap

### Reason Classification
- Multi-label classification (one review can have multiple reasons)
- Custom reason definitions per category
- LLM-powered classification via DeepSeek
- Fallback to rule-based classification if LLM fails

---

## 3. Key Files & Their Purpose

```
/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/
├── scripts/
│   ├── wbcon-task-to-card-v2.py    # Main analysis (~1400 lines)
│   │                                # Entry point, orchestrates all analysis
│   └── llm_analyzer.py              # DeepSeek LLM integration (~885 lines)
│                                    # classify_reasons, get_actions, get_reply,
│                                    # deep_analysis, analyze_communication
├── apps/reviews/
│   ├── templates/
│   │   └── report.html              # Jinja2 HTML template (~33KB)
│   │                                # Renders analysis results
│   ├── backend/
│   │   └── main.py                  # FastAPI server + custom Jinja filters
│   │                                # format_number (thousands separator)
│   └── .env                         # Credentials (WBCON, DeepSeek)
│                                    # DEEPSEEK_API_KEY, USE_LLM, WBCON_TOKEN
└── docs/
    ├── COMMUNICATION_LOSS_CALCULATION.md  # Methodology docs
    └── IMPLEMENTATION_STATUS.md           # This file
```

---

## 4. Critical Functions & Methods

### `fetch_wb_card_info(nm_id)`
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/scripts/wbcon-task-to-card-v2.py:48-95`

Fetches product card from WB public API (no auth).

**Returns**:
```python
{
    "imt_name": str,      # Product name
    "description": str,   # Full description
    "options": str,       # "name: value; ..." formatted
    "subj_name": str,     # Category
    "price": float,       # Price in rubles (from sizes[0].price.basic / 100)
}
```

**URL pattern**:
```
https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json

where:
  vol = nm_id // 100000
  part = nm_id // 1000
  basket = _wb_basket_num(nm_id)  # Range table lookup
```

**Error handling**: Returns `None` on any error (network, JSON parse, timeout).

---

### `calculate_money_loss(review_count, period_months, price_rub, quality_score)`
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/scripts/wbcon-task-to-card-v2.py:98-159`

Estimates revenue loss from poor communication quality.

**Inputs**:
- `review_count`: Total reviews received
- `period_months`: Period in months
- `price_rub`: Product price in rubles
- `quality_score`: LLM quality score (1-10)

**Returns**:
```python
{
    "purchases_per_month_min": int,
    "purchases_per_month_max": int,
    "revenue_per_month_min": int,
    "revenue_per_month_max": int,
    "loss_per_month_min": int,
    "loss_per_month_max": int,
}
```
or `None` if price not available.

**Methodology**:
```python
# Review rate assumptions
review_rate_min = 0.03  # 3% (functional products like flashlights, tools)
review_rate_max = 0.05  # 5%

# Calculate purchases
purchases = review_count / review_rate  # Conservative: /max, Optimistic: /min

# CR impact by quality score (updated 2026-02-07)
if quality_score >= 7:
    cr_impact = 1-2%
elif quality_score >= 4:
    cr_impact = 2-4%  # WAS 3-7%
else:
    cr_impact = 3-6%

# Loss = revenue * cr_impact
```

**Assumptions**:
- Functional products review rate: 3-5%
- Electronics/tech: 5-7%
- FMCG/clothing: 0.5-1%
- 30-50% of buyers read reviews
- Category coefficient: 0.8

**Disclaimer**: This is an estimate, not exact science. Requires real sales data for accuracy. Do not use for financial reporting, legal disputes, or guaranteed ROI.

---

### `llm_analyze_communication(feedbacks, product_name)`
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/scripts/llm_analyzer.py:701-778`

Analyzes seller responses to ALL reviews (1-5★) for communication quality.

**Inputs**:
- `feedbacks`: List of feedback dicts from WBCON API
- `product_name`: Product name for context

**Returns**:
```python
{
    "quality_score": int (1-10),
    "verdict": str,  # 1-2 sentences, main takeaway
    "total_analyzed": int,
    "negative_count": int,  # 1-3★
    "distribution": {
        "harmful": int,    # Hurt sales (blame, ignore, no_answer)
        "risky": int,      # Problems (template, amplify)
        "acceptable": int, # Normal (ok)
        "good": int,       # Good responses
    },
    "error_types": [
        {
            "label": str,        # "Перекладывает вину"
            "tooltip": str,      # Explanation
            "count": int,
            "severity": str,     # "critical" | "warning" | "ok"
            "risk_type": str,    # "blame" | "ignore" | "amplify" | "deny"
                                 # | "template" | "no_answer" | "ok" | "good"
        },
        # ...
    ],
    "worst_responses": [
        {
            "review_rating": int,
            "review_text": str,         # Up to 100 chars
            "response_text": str,       # Up to 150 chars
            "risk_type": str,
            "risk_label": str,
            "explanation": str,         # Why this hurts (1-2 sentences)
            "recommendation": str,      # How to reply (2-3 sentences)
        },
        # ... (up to 5)
    ],
    "hidden_risks": [
        {
            "review_rating": int,       # 4-5★
            "reviewer_name": str,
            "review_text": str,         # Quote of complaint
            "response_text": str,       # Up to 150 chars
            "issue": str,               # What was ignored
        },
        # ... (up to 5)
    ],
    "buyer_perception": [str],  # 3-5 points, what buyers see
    "action_plan": [
        {
            "priority": str,  # "critical" | "important"
            "action": str,    # Concrete step, starts with verb
        },
        # ... (3-5 items)
    ],
}
```
or `None` on failure.

**Response types**:
- `"blame"` → "Перекладывает вину" (blames customer)
- `"ignore"` → "Игнорирует жалобу" (ignores complaint)
- `"amplify"` → "Подтверждает проблему" (confirms problem publicly)
- `"deny"` → "Отрицает проблему" (denies real problem)
- `"template"` → "Копипаст-шаблон" (copy-paste template)
- `"no_answer"` → "Без ответа" (no response)
- `"ok"` → "Нормальный ответ" (normal, not harmful)
- `"good"` → "Хороший ответ" (empathy + solution)

**Guardrails** (enforced via `_apply_communication_guardrails()`):
- NEVER promise refunds, replacements, compensation, specific timelines
- Suggest return via WB ONLY if buyer asked for it in review
- NEVER mention AI/bot/GPT in recommendations or verdict
- NEVER blame the customer
- Ban phrases: "вернём деньги", "вы неправильно", "обратитесь в поддержку", "ИИ-ответ", etc.

**Uses**: DeepSeek API (requires `DEEPSEEK_API_KEY` env var).

---

### Response Speed Calculation
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/scripts/wbcon-task-to-card-v2.py:1280-1291`

Computed from data (no LLM).

**Returns**:
```python
{
    "all_median_hours": float,
    "all_avg_hours": float,
    "all_count": int,
    "neg_median_hours": float,  # 1-3★ only
    "neg_avg_hours": float,
    "neg_count": int,
    "max_hours": float,
    "same_day_count": int,      # <24h
    "slow_count": int,          # >=7 days
}
```

**Calculation**:
```python
# Extract timestamps
review_time = parse_date(fb["fb_created_at"])
answer_time = parse_date(fb["answer_created_at"])
hours = (answer_time - review_time).total_seconds() / 3600

# Sort all response times
sorted_all = sorted(all_hours)
sorted_neg = sorted(negative_hours)  # 1-3★ only

# Compute stats
median = sorted[len(sorted) // 2]
avg = sum(sorted) / len(sorted)
max = max(sorted)
```

---

### `llm_deep_analysis(...)`
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/scripts/llm_analyzer.py:356-470`

Deep analysis of problematic product variant: root cause + strategy + actions + reply in one LLM call.

**Key inputs**:
- `product_name`, `category`, `target_variant`
- `target_rating`, `target_count`, `other_variants`
- `reason_rows`, `review_samples`
- `card_description` (from WB Card API)
- `questions` (from WBCON QS API)

**Returns**:
```python
{
    "root_cause": {
        "type": str,  # "expectation_mismatch" | "defect" | "design_flaw" | "description_gap"
        "explanation": [str],  # 2-3 points, each: "Keyword: one sentence"
        "conclusion": str,     # 1 sentence
    },
    "strategy": {
        "title": str,          # 2-4 words, simple language
        "description": str,    # 1-2 sentences
    },
    "actions": [str],          # 3 concrete actions, each <100 chars
    "reply": str,              # 2-3 sentences to buyer
}
```

**Root cause types**:
- `expectation_mismatch`: Variant has special purpose, buyer didn't know (e.g., red flashlight for night vision)
- `defect`: Real quality issue, not variant-specific
- `design_flaw`: Inherent product design problem
- `description_gap`: Missing/unclear info in card description

**Guardrails**:
- NEVER promise refund/replacement/compensation
- NEVER blame buyer
- Each action: concrete, executable by seller on WB
- Reply: explain purpose/reason, don't just say "we'll check"

---

## 5. Important Constants & Patterns

### Harm Index Calculation (Updated 2026-02-07)

**Risky weight reduced from 2 to 1**:

```python
# Weights for response types
WEIGHTS = {
    "critical": 10,  # blame, ignore, no_answer
    "risky": 1,      # template, amplify (WAS 2)
    "normal": 0,     # ok
    "good": -1,      # good
}

# Harm Index
harm_index = (critical_count × 10 + risky_count × 1) / (total × 10)

# Example (quality 4/10):
# 8 critical × 10 + 66 risky × 1 = 146
# 146 / (145 × 10) = 146/1450 = 10.1%
# CR impact: ~2-4% (was ~3-7%)
# Money loss: 15-50k₽/month (was 20-85k₽)
```

**Rationale**: Templates are less harmful than critical errors (blame, ignore). More conservative harm calculation reflects that template responses, while not ideal, don't actively repel buyers like blaming or ignoring complaints.

---

### Review Rate Assumptions

```python
# By category
functional_products = 0.03-0.05  # 3-5% (flashlights, tools, appliances)
electronics_tech = 0.05-0.07     # 5-7%
fmcg_clothing = 0.005-0.01       # 0.5-1%

# Usage in calculate_money_loss()
review_rate_min = 0.03  # Conservative
review_rate_max = 0.05  # Optimistic
```

---

### CR Impact Ranges (Updated 2026-02-07)

```python
# Quality score → CR impact range
if quality_score >= 7:
    cr_impact_min, cr_impact_max = 0.01, 0.02  # 1-2%
elif quality_score >= 4:
    cr_impact_min, cr_impact_max = 0.02, 0.04  # 2-4% (WAS 3-7%)
else:
    cr_impact_min, cr_impact_max = 0.03, 0.06  # 3-6%
```

---

### Display Rules

**Product name in header**:
```python
# From WB Card API imt_name
product_name = wb_card["imt_name"]  # "Фонарь налобный WATTICO"
# NOT just "Артикул 282955222"
```

**No LLM branding in footer**:
```html
<!-- OLD (removed 2026-02-07) -->
<footer>Powered by DeepSeek LLM</footer>

<!-- NEW -->
<footer>AgentIQ Report</footer>
```

**Tooltip formulas**:
```html
<!-- Generic (no hardcoded numbers) -->
<span title="(критичные×10 + рискованные×1) / макс = harm%">Harm Index</span>

<!-- NOT (old, hardcoded) -->
<span title="8 критичных×10 + 66 рискованных×2 = ...">Harm Index</span>
```

---

## 6. Data Flow

```
┌─────────────────────────────────────────────────────┐
│ Input: WBCON feedbacks JSON                         │
│ (from WBCON API: /api/01-feedbacks-tasks)          │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ wbcon-task-to-card-v2.py (main script)             │
│                                                     │
│ 1. Parse feedbacks + metadata                      │
│ 2. Variant analysis (color normalization)          │
│    ├─ is_color_variant() regex filter             │
│    └─ Check BOTH recent (30d) AND all-time        │
│                                                     │
│ 3. Trend detection                                 │
│    ├─ 30-day window (if >=3 reviews)              │
│    └─ Split-half fallback (first 50% vs last 50%) │
│                                                     │
│ 4. Response speed (median, avg from timestamps)   │
│                                                     │
│ 5. WB Card API → price, name                       │
│    └─ fetch_wb_card_info(nm_id)                   │
│                                                     │
│ 6. LLM communication analysis (if USE_LLM=1)       │
│    └─ llm_analyze_communication(feedbacks, name)  │
│                                                     │
│ 7. Money loss calculation (if price + comm data)  │
│    └─ calculate_money_loss(...)                   │
│                                                     │
│ 8. (Optional) Deep analysis (if signal detected)  │
│    └─ llm_deep_analysis(...)                      │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ Output: JSON result (saved to output.json)         │
│ {                                                   │
│   "meta": {...},                                    │
│   "communication": {...},                           │
│   "money_loss": {...},                              │
│   "response_speed": {...},                          │
│   "variant_signal": {...},                          │
│   "deep_analysis": {...},                           │
│   ...                                               │
│ }                                                   │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ Jinja2 template (report.html)                       │
│                                                     │
│ 1. Custom filter: format_number                    │
│    └─ Thousands separator (12000 → "12,000")      │
│                                                     │
│ 2. Render sections:                                │
│    ├─ Product header (name from WB Card API)      │
│    ├─ Communication quality score + verdict        │
│    ├─ Error types (2 sections: good + errors)     │
│    ├─ Worst responses (top 3-5)                    │
│    ├─ Hidden risks (4-5★ ignored complaints)      │
│    ├─ Money loss estimation (min-max range)       │
│    ├─ Response speed stats                         │
│    ├─ Variant signal (if detected)                 │
│    └─ Action plan                                  │
└──────────────────┬──────────────────────────────────┘
                   ▼
┌─────────────────────────────────────────────────────┐
│ HTML Report                                         │
└─────────────────────────────────────────────────────┘
```

---

## 7. Environment Setup

### .env file
**Location**: `/Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq/apps/reviews/.env`

```bash
DEEPSEEK_API_KEY=sk-...
USE_LLM=1
WBCON_TOKEN=eyJ...
```

### Running the script

**python-dotenv not in system python** → pass env vars via CLI:

```bash
cd /Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq

# Option 1: Export vars (persist in session)
export DEEPSEEK_API_KEY=sk-...
export USE_LLM=1
python3 scripts/wbcon-task-to-card-v2.py input.json output.json

# Option 2: Inline vars (single command)
DEEPSEEK_API_KEY=sk-... USE_LLM=1 python3 scripts/wbcon-task-to-card-v2.py input.json output.json
```

### Dependencies

```bash
# Required
pip3 install openai  # For DeepSeek API (OpenAI-compatible)

# Optional (but recommended for dev)
pip3 install python-dotenv  # If available, loads apps/reviews/.env automatically
```

---

## 8. Known Issues & Limitations

### WBCON API

**Pagination broken (critical bug)**:
- `offset` parameter returns duplicates
- Only first 100 reviews fetched reliably (out of 407 total)
- Workaround: Accept partial data, note in report
- Status: Reported to WBCON, no fix yet

**Questions endpoint**:
- Docs: `https://qs.wbcon.su/docs`
- Pattern: Uses different prefix (not `01-` like feedbacks)
- Current status: Implemented, not critical for MVP

---

### Money Loss Estimation

**This is an estimate only, not exact science.**

**Limitations**:
- Requires real sales data for accuracy
- Review rate assumptions vary by category/product
- CR impact ranges are industry averages, not product-specific
- Doesn't account for: seasonality, promotions, competitor actions, market saturation

**Disclaimer** (always show in report):
> "Точные данные требуют доступа к статистике продаж. Эта оценка основана на предположениях о проценте отзывов и поведении покупателей."

**Don't use for**:
- Financial reporting
- Legal disputes
- Guaranteed ROI promises
- Business case justification (without real sales data)

**DO use for**:
- Directional guidance ("~10-50k₽/month range")
- Prioritization (which products need attention first)
- Demonstrating potential impact to stakeholders

---

### Color Normalization

**Problem**: WBCON `color` field may contain non-colors:
```
"color": "4 шт. · 120 м"
"color": "белый, черный"
"color": "120 см"
```

**Solution**: Filter via `is_color_variant()` regex:
```python
def is_color_variant(name: str) -> bool:
    """Returns True if name is likely a color, not a quantity/size."""
    if not name:
        return False
    name_lower = name.lower().strip()
    # Reject: numbers + units, multi-item quantities
    if re.search(r'\d+\s*(шт|м|см|мл|л|г|кг)', name_lower):
        return False
    if re.search(r'\d+\s*×', name_lower):
        return False
    # Accept: color words
    color_words = ['белый', 'черный', 'красный', 'синий', 'зеленый', ...]
    return any(c in name_lower for c in color_words)
```

**Important**: Check BOTH recent (30-day) window AND all-time data for real colors. A variant may have no reviews in recent window but be valid.

---

### Trend Fallback

**Problem**: 30-day window may have insufficient data (<3 reviews).

**Solution**: Fallback to split-half approach:
```python
if recent_window_reviews < 3:
    # Use split-half (first 50% vs last 50% of all feedbacks)
    mid = len(feedbacks) // 2
    first_half = feedbacks[:mid]
    last_half = feedbacks[mid:]
    # Compare ratings
```

**Advantages**:
- Always has enough data (if product has >=6 reviews total)
- Detects long-term trends (not just recent)
- More stable (less noise from single bad review)

**Disadvantages**:
- May miss recent trend reversals
- Less sensitive to seasonality

---

### LLM Deep Analysis

**"One rich call beats three poor calls"**:
- Deep analysis needs full context: reviews + variants + reasons + card description + questions
- Don't split into separate calls (classify → actions → reply)
- Pass all data in one prompt → better root cause detection

**Guardrails are critical**:
- System prompt rules alone are insufficient
- Post-processing validation mandatory (`_apply_guardrails()`)
- Banned phrases, length limits, type validation

---

### f-string gotcha

**Problem**: `!r` format spec can't be used inside f-strings in Python.

```python
# ❌ WRONG
f"Value: {my_var!r}"  # SyntaxError in some Python versions

# ✅ CORRECT
x = repr(my_var)
f"Value: {x}"
```

---

## 9. Testing

### Test on real data (article 282955222, flashlight)

```bash
cd /Users/ivanilin/Documents/ivanilin/customer-service-ai-product/agentiq

python3 scripts/wbcon-task-to-card-v2.py \
  card-data-282955222-llm.json \
  /tmp/test-output.json

# Expected output (quality 4/10):
# [Money loss] Est. loss: 14,400 - 48,000₽/мес
# [Communication] quality_score: 4/10
# [Response speed] all median: 12.5h, neg median: 8.0h, max: 168.0h
```

### Validate output JSON schema

```python
import json

with open("/tmp/test-output.json") as f:
    result = json.load(f)

# Check required fields
assert "meta" in result
assert "communication" in result
assert "money_loss" in result
assert "response_speed" in result

# Check communication structure
comm = result["communication"]
assert 1 <= comm["quality_score"] <= 10
assert isinstance(comm["verdict"], str)
assert isinstance(comm["error_types"], list)
assert isinstance(comm["worst_responses"], list)
assert isinstance(comm["action_plan"], list)

# Check money loss structure
loss = result["money_loss"]
assert loss["loss_per_month_min"] <= loss["loss_per_month_max"]
assert loss["purchases_per_month_min"] > 0
```

---

## 10. Recent Changes (2026-02-07)

### 1. Risky Weight Reduced: 2 → 1

**What changed**:
```python
# OLD
risky_weight = 2  # template, amplify
harm_index = (critical × 10 + risky × 2) / (total × 10)

# NEW
risky_weight = 1  # template, amplify
harm_index = (critical × 10 + risky × 1) / (total × 10)
```

**Why**:
- Templates are less harmful than critical errors (blame, ignore)
- More conservative harm calculation
- Reflects reality: template responses don't actively repel buyers like blaming/ignoring complaints

**Impact** (example: quality 4/10):
- Harm index: 10.1% (was ~14%)
- CR impact: ~2-4% (was ~3-7%)
- Money loss: 15-50k₽/month (was 20-85k₽/month)

**Files changed**:
- `llm_analyzer.py` (harm calculation logic)
- `wbcon-task-to-card-v2.py` (CR impact ranges)
- `docs/reviews/COMMUNICATION_LOSS_CALCULATION.md` (documentation)

---

### 2. CR Impact Ranges Updated

**What changed**:
```python
# Quality 4-6
# OLD: cr_impact = 3-7%
# NEW: cr_impact = 2-4%

# Quality 7-10
# Unchanged: 1-2%

# Quality 1-3
# Unchanged: 3-6%
```

**Why**: Aligned with risky weight reduction (more conservative estimates).

**Files changed**:
- `wbcon-task-to-card-v2.py:138-146`
- `docs/reviews/COMMUNICATION_LOSS_CALCULATION.md`

---

### 3. Product Name Added to Header

**What changed**:
```html
<!-- OLD -->
<h1>Артикул 282955222</h1>

<!-- NEW -->
<h1>Фонарь налобный WATTICO</h1>
<p>Артикул: 282955222</p>
```

**Why**: More user-friendly, easier to identify product at a glance.

**Source**: `wb_card["imt_name"]` from WB Card API.

**Files changed**:
- `apps/reviews/templates/report.html`
- `wbcon-task-to-card-v2.py` (pass product_name to template)

---

### 4. LLM Branding Removed from Footer

**What changed**:
```html
<!-- OLD -->
<footer>
  <p>Powered by DeepSeek LLM</p>
</footer>

<!-- NEW -->
<footer>
  <p>AgentIQ Report — {{ meta.generated_at }}</p>
</footer>
```

**Why**: Cleaner, more professional appearance. Users don't need to know which LLM is used.

**Files changed**:
- `apps/reviews/templates/report.html`

---

### 5. Tooltip Formulas Simplified

**What changed**:
```html
<!-- OLD (hardcoded example numbers) -->
<span title="8 критичных×10 + 66 рискованных×2 = 212, 212/1450 = 14.6%">
  Harm Index: 14.6%
</span>

<!-- NEW (generic formula) -->
<span title="(критичные×10 + рискованные×1) / макс = harm%">
  Harm Index: 10.1%
</span>
```

**Why**: Hardcoded examples confuse users, make tooltips feel "copy-pasted". Generic formulas are clearer and always accurate.

**Files changed**:
- `apps/reviews/templates/report.html`

---

## 11. Future Improvements (Not Implemented)

### Priority 1: Real Sales Data Integration
- Connect to WB seller API (requires seller credentials)
- Fetch actual sales, conversion rate, revenue
- Replace estimated CR impact with real data
- **Blocker**: Seller API access, legal/privacy considerations

### Priority 2: A/B Testing Framework
- Test different response strategies
- Measure real CR impact of communication quality
- Validate money loss estimation accuracy
- **Blocker**: Requires multiple sellers, control group, time

### Priority 3: WBCON Pagination Fix
- Workaround for offset duplicates bug
- Or migrate to WB official API (if available)
- **Blocker**: Depends on WBCON team or WB API access

### Priority 4: Multi-Language Support
- Analyze reviews in English, Kazakh, etc.
- LLM already supports (DeepSeek is multilingual)
- Need: language detection, translate guardrails
- **Blocker**: Low priority (WB is mostly Russian)

### Priority 5: Real-Time Dashboard
- WebSocket updates for live review monitoring
- Slack/Telegram notifications for critical errors
- **Blocker**: Requires infrastructure (server, DB, messaging service)

---

## 12. Appendix: File Line Counts

```bash
# As of 2026-02-07
wc -l scripts/wbcon-task-to-card-v2.py  # ~1400 lines
wc -l scripts/llm_analyzer.py           # ~885 lines
wc -l apps/reviews/templates/report.html         # ~1100 lines
wc -l apps/reviews/backend/main.py               # ~450 lines
wc -l docs/reviews/COMMUNICATION_LOSS_CALCULATION.md  # ~350 lines
wc -l docs/IMPLEMENTATION_STATUS.md     # (this file)
```

---

## 13. Appendix: WBCON API Reference

### Feedbacks Endpoint
```
POST https://qs.wbcon.su/api/01-feedbacks-tasks
Headers:
  Authorization: Bearer {WBCON_TOKEN}
  Content-Type: application/json
Body:
  {
    "article": 282955222,
    "limit": 100,
    "offset": 0
  }

Response:
  {
    "task_id": "uuid",
    "status": "pending" | "processing" | "completed" | "failed"
  }

# Then poll:
GET https://qs.wbcon.su/api/01-feedbacks-tasks/{task_id}
```

**Known issue**: `offset` returns duplicates (only first 100 reliable).

### Questions Endpoint
```
POST https://qs.wbcon.su/create_task_qs?email={email}&password={password}
Body:
  {"article": 282955222}

Response:
  {"task_id": "uuid"}

# Then poll:
GET https://qs.wbcon.su/task_status?task_id={task_id}&email={email}&password={password}
```

**Timeout**: 120 seconds max for polling.

---

## 14. Appendix: WB Card API Reference

### URL Pattern
```
https://basket-{N}.wbbasket.ru/vol{vol}/part{part}/{nmId}/info/ru/card.json

where:
  vol = nm_id // 100000
  part = nm_id // 1000
  N = _wb_basket_num(nm_id)  # See range table below
```

### Basket Number Range Table
```python
ranges = [
    (143, "01"), (287, "02"), (431, "03"), (719, "04"),
    (1007, "05"), (1061, "06"), (1115, "07"), (1169, "08"),
    (1313, "09"), (1601, "10"), (1655, "11"), (1919, "12"),
    (2045, "13"), (2189, "14"), (2405, "15"), (2621, "16"),
    (2837, "17"),
]
# If vol > 2837: basket = "18"
```

### Example
```python
nm_id = 282955222
vol = 282955222 // 100000 = 2829
part = 282955222 // 1000 = 282955
basket = "18" (vol 2829 > 2837)

URL = https://basket-18.wbbasket.ru/vol2829/part282955/282955222/info/ru/card.json
```

### Response Structure
```json
{
  "imt_name": "Фонарь налобный WATTICO",
  "description": "...",
  "subj_name": "Фонари",
  "options": [
    {"name": "Цвет", "value": "белый"},
    {"name": "Тип", "value": "налобный"}
  ],
  "sizes": [
    {
      "price": {
        "basic": 120000  // kopeks (1200₽)
      }
    }
  ]
}
```

---

**End of Implementation Status**
