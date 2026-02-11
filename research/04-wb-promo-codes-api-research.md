# Wildberries Promo Codes API -- Research Report

> Date: 2026-02-11
> Author: AgentIQ Research
> Status: Research Complete
> Relevance: Chat Center integration planning

---

## Executive Summary

Wildberries launched **seller promo codes** (promokody prodavca) in **January 2026** as a new marketing tool. Sellers can create promo codes in their seller portal, set discount percentages (3-50%), choose products, and distribute codes through any channel -- including WB Media, social media, messengers, and email.

**Key finding for AgentIQ:** There is currently **no dedicated public API endpoint** for creating/managing promo codes programmatically. Promo codes are created through the seller portal UI. However, the existing Promotion API (`/api/v1/calendar/promotions/*`) provides endpoints for managing promotions and adding products, which may be extended to cover promo codes as the feature matures. The Chat API allows sending text messages to buyers, so promo codes can be **sent as text** in chat messages.

---

## 1. WB Seller Promo Codes -- Feature Overview

### 1.1 Launch Details

- **Launch date:** January 27, 2026 (test group of Russian sellers)
- **Status:** Rolling out to all Russian sellers
- **Cost to seller:** Free tool (no platform commission for promo code feature itself)
- **Discount is fully funded by the seller** (not subsidized by WB)

Sources:
- [Retail.ru -- WB promo codes announcement](https://www.retail.ru/news/wildberries-pozvolit-selleram-sozdavat-promokody-dlya-pokupateley-27-yanvarya-2026-273815/)
- [Forbes.ru -- WB promo codes](https://www.forbes.ru/novosti-kompaniy/554273-na-wildberries-poavilis-promokody-ot-prodavcov)
- [ixbt.com -- WB promo codes](https://www.ixbt.com/news/2026/01/27/v-wildberries-pojavilis-promokody-ot-prodavcov.html)

### 1.2 How Promo Codes Work

**Creation flow (seller portal only):**

1. Go to seller portal: **Tovary i ceny -> Kalendar' akcij** (Products and Prices -> Promotions Calendar)
2. Open the **"Po promokodам"** (By Promo Codes) tab
3. Click **"Sozdat' akciyu"** (Create Promotion)
4. Configure parameters:
   - **Promotion name** (internal only, buyers don't see it)
   - **Discount percentage**: 3% to 50%
   - **Duration**: 1 to 31 days
   - **Start date**: minimum tomorrow, maximum 3 months ahead
   - **Products**: entire assortment or specific SKUs
5. System **auto-generates** the promo code, or seller sets a custom code
6. Launch the promotion

**Buyer application flow:**
1. Buyer adds product to cart on WB
2. Enters promo code in the special field
3. Gets the discounted price

### 1.3 Key Limitations

| Parameter | Limit |
|-----------|-------|
| Max active promo campaigns simultaneously | **10** per seller |
| Promo code reusability | **Unlimited uses** until promotion ends |
| Discount range | **3% to 50%** |
| Duration | **1 to 31 days** |
| Start date range | Tomorrow to +3 months |
| Products | All or selected SKUs |
| Code format | Auto-generated or custom |

### 1.4 Discount Stacking Rules

Discounts are applied **sequentially** to the original price:

```
Original Price
  -> Seller's base discount
    -> Seller's own promotion discount
      -> Promo code discount
```

**Critical rules:**
- Promo code discount **does NOT stack** with discounts above 45% (before personal discounts)
- Only **one promo code** can be applied per product unit at a time
- If buyer has both a promo code and a loyalty discount, the system applies **whichever gives the buyer the bigger discount** (not both)
- Promo code discount is **entirely at the seller's expense** (WB does not subsidize it)

### 1.5 Distribution Channels

Sellers can distribute promo codes through:
- **WB Media** (internal advertising tools on Wildberries)
- **Social media** (VK, Telegram, etc.)
- **Messengers** (WhatsApp, Telegram)
- **Email newsletters**
- **Any external channel** -- seller has full freedom

**Important for AgentIQ:** There is no prohibition on sharing promo codes in WB buyer chats. The code is just text that can be sent in any message.

Source: [WB Partners -- Seller Promo Codes](https://seller.wildberries.ru/instructions/ru/ru/material/seller-promocodes)

---

## 2. WB API for Promotions -- Technical Details

### 2.1 API Documentation Links

| Resource | URL |
|----------|-----|
| **Promotions Overview** | https://dev.wildberries.ru/en/openapi/promotion |
| **Promotions Swagger** | https://dev.wildberries.ru/en/swagger/promotion |
| **Promotions OpenAPI YAML** | https://openapi.wildberries.ru/promotion/swagger/api/ru/ |
| **Promotion API (old portal)** | https://openapi.wildberries.ru/promotion/api/en/ |
| **Release Notes** | https://dev.wildberries.ru/en/release-notes |

### 2.2 Authentication

```http
Authorization: Bearer <PROMOTION_TOKEN>
```

- Token category: **"Marketing i prodvizhenie"** (Marketing and Promotion)
- Token validity: **180 days** after creation
- Token is created in seller portal: Settings -> API keys -> Promotion category
- One-time display -- must be saved immediately

### 2.3 Known Promotion Calendar Endpoints

These are the confirmed public endpoints for managing promotions (calendar-based):

#### GET /api/v1/calendar/promotions
**Description:** Get a list of available promotions in the calendar.

#### GET /api/v1/calendar/promotions/nomenclatures
**Description:** Get a list of products eligible for participating in a specific promotion.

#### POST /api/v1/calendar/promotions/upload
**Description:** Add products to a promotion. When setting discounts via the promo calendar, uploads are processed asynchronously, and the discount activates at promo start.

#### Upload Status Tracking
- **Unprocessed upload state** method -- check if upload is still processing (status = 1)
- **Unprocessed upload details** method -- get details of pending uploads

### 2.4 Promo Code-Specific API -- Status: NOT YET PUBLIC

As of February 2026, there are **no publicly documented API endpoints** specifically for:
- Creating promo code promotions programmatically
- Listing active promo codes
- Activating/deactivating promo codes
- Getting promo code usage statistics

**Evidence:**
- The feature launched January 27, 2026, only 2 weeks ago
- Still in test group rollout phase
- The Promotion API Swagger documentation does not yet list promo-code-specific endpoints
- WB API release notes mention "promo code discount info added to realization reports" but no creation endpoints

**Prediction:** WB will likely add promo code management endpoints to the Promotion API within 2-6 months, following their pattern of:
1. Launch UI feature
2. Collect feedback
3. Open API access

### 2.5 Realization Reports -- Promo Code Data

The realization reports API **does** include promo code discount information:
- `promoCodeDiscount` field added to report details
- Shows promo code discount amounts applied to sold items
- Allows tracking ROI of promo code campaigns

---

## 3. WB Chat API -- Sending Promo Codes to Buyers

### 3.1 Chat API Overview

Based on our existing research (see `WB_CHAT_API_RESEARCH.md`):

| Parameter | Value |
|-----------|-------|
| Base URL | `https://buyer-chat-api.wildberries.ru` |
| Auth | `Authorization: Bearer <CHAT_TOKEN>` |
| Token category | "Chat s pokupatelyami" (Buyers Chat) |
| Response time limit | 10 days |

### 3.2 Sending Messages Endpoint

```http
POST /api/v1/seller/chats/{chatID}/messages
Authorization: Bearer <TOKEN>
Content-Type: application/json

{
  "message": "Spasibo za pokupku! Vot vash promo code SALE15 na skidku 15% na sleduyuschiy zakaz!"
}
```

**Key points:**
- Messages are **plain text** -- no special promo code attachment mechanism
- Promo codes are sent as **text within the message body**
- No special API for "attaching" a promo code to a chat message
- The buyer must manually copy and apply the code at checkout
- **There is no deep link** that auto-applies a promo code to buyer's cart

### 3.3 Chat + Promo Code Integration -- Current Possibilities

| Capability | Status |
|------------|--------|
| Send promo code as text in chat | YES -- works now |
| Auto-attach promo code to chat message | NO -- not supported |
| Generate unique per-buyer promo codes via API | NO -- not supported yet |
| Track if buyer used the promo code from chat | NO -- no attribution |
| Deep link to product with promo code applied | NO -- not supported |

### 3.4 Workaround for AgentIQ

Since promo codes are **reusable** and **not buyer-specific**, the integration approach is:

1. Seller creates promo code campaigns in WB seller portal (1-10 active at a time)
2. AgentIQ stores the active promo codes in its database (code + discount % + products + expiry)
3. AI suggests including the promo code in chat responses when appropriate
4. Operator sends the message with the promo code text
5. Buyer copies the code and applies it at checkout

**Limitation:** No way to create unique per-buyer codes. All promo codes are **shared/public** and reusable by anyone.

---

## 4. Competitor Landscape -- Promo Code Automation on Marketplaces

### 4.1 Ozon (for comparison)

Ozon has a more mature promo code system called **"Kupony"** (Coupons):
- Created in seller portal: Ceny i akcii -> Kupony -> Sozdat' akciyu
- Coupon mechanics: "Kupon na skidku po promokodu"
- Discount in **percentage or fixed rubles**
- Duration: up to **6 months** (vs WB's 31 days max)
- **Sellers CAN send promo codes to buyers in Ozon chats** -- buyers receive messages both on site and in app
- Ozon has **chat API with premium subscription** for sending messages

Source: [Ozon Seller -- How to create coupons](https://seller.ozon.ru/media/boost/kak-sozdat-svoj-promokod-na-ozon/)

### 4.2 Existing Automation Services

| Service | What it does | Promo code support |
|---------|-------------|-------------------|
| **IntellectDialog** | Unifies WB/Ozon/YM chats in amoCRM, AI auto-responses | No specific promo code automation |
| **Marpla** | AI auto-responses to WB reviews via Telegram bot | No promo code features |
| **Otveto** | AI auto-responses to WB reviews | No promo code features |
| **MPSTATS** | Analytics, repricing, auto-replies to reviews | Price management, no promo code creation |
| **Moneyplace** | Analytics, SEO, AI descriptions, auto-replies | No promo code automation |
| **WBot (official WB)** | Analytics chatbot for sellers (Dzhем subscription) | Analytics only, no promo code management |
| **Repricing tools** | Auto price management (MPSTATS, MPManager) | Price/discount management, not promo codes |

**Key finding:** As of February 2026, **no existing service** automates promo code creation or distribution on Wildberries. This is a greenfield opportunity.

### 4.3 CRM Integrations

- **IntellectDialog + amoCRM/Kommo:** Aggregates all marketplace chats into CRM, AI-assisted responses, but no promo code integration
- **Chat2Desk:** Chat center automation with WB integration, but focused on message routing, not promo codes

---

## 5. Integration Architecture for AgentIQ Chat Center

### 5.1 Use Cases

#### UC1: Satisfied Customer -- Loyalty Promo
```
Trigger: AI detects positive feedback / thank-you message in chat
Action: Suggest operator includes promo code in response
Message: "Spasibo za otzyv! Vot vash personal'nyy promokod THANKS10
         na skidku 10% na lyuboy nash tovar. Dejstvuet do [date]!"
Goal: Increase repeat purchases, build loyalty
```

#### UC2: Dissatisfied Customer -- Retention Promo
```
Trigger: AI detects complaint / negative sentiment (quality_complaint, defect)
Action: Suggest operator offers promo code as goodwill gesture
Message: "Nam ochen' zhal', chto vy stolknulis' s etim!
         V kachestve izvineniya -- promokod SORRY15 na skidku 15%
         na vash sleduyuschiy zakaz. Dejstvuet 14 dney."
Goal: Retain customer, prevent negative review, turn negative into positive
```

#### UC3: Pre-Purchase Question -- Conversion Promo
```
Trigger: AI detects pre-purchase intent (sizing_fit, availability, compatibility)
Action: Suggest promo code to incentivize purchase decision
Message: "Etot razmer vam otlichno podojdyot!
         A vot promokod FIRST5 na skidku 5% dlya bystogo resheniya!"
Goal: Convert inquiry into purchase, reduce cart abandonment
```

### 5.2 Technical Architecture

```
+------------------+     +-------------------+     +------------------+
|  WB Seller       |     |  AgentIQ          |     |  WB Chat API     |
|  Portal (manual) |     |  Chat Center      |     |  (automated)     |
+--------+---------+     +--------+----------+     +--------+---------+
         |                        |                          |
         |  1. Create promo      |                          |
         |  code campaigns       |                          |
         |  (3-50%, 1-31 days)   |                          |
         |                       |                          |
         +--------> 2. Store active promo codes             |
         |          in AgentIQ DB                           |
         |          (code, %, products, expiry)             |
         |                       |                          |
         |               3. AI analyzes chat                |
         |               (sentiment, intent)                |
         |                       |                          |
         |               4. AI suggests promo               |
         |               code in response draft             |
         |                       |                          |
         |               5. Operator approves               |
         |               (or auto-sends)                    |
         |                       |                          |
         |                       +---> 6. POST message      |
         |                       |     with promo code text |
         |                       |          +               |
         |                       |          |               |
         |                       |  7. Track sent promos    |
         |                       |  (internal analytics)    |
         +                       +                          +
```

### 5.3 Database Schema (AgentIQ)

```sql
-- New table for managing seller promo codes
CREATE TABLE promo_codes (
    id SERIAL PRIMARY KEY,
    seller_id INTEGER REFERENCES sellers(id),
    code VARCHAR(50) NOT NULL,
    discount_percent DECIMAL(5,2) NOT NULL, -- 3.00 to 50.00
    description TEXT,
    -- Targeting
    applies_to VARCHAR(20) DEFAULT 'all', -- 'all' | 'selected'
    product_nms INTEGER[],  -- array of nmIds if applies_to='selected'
    -- Lifecycle
    starts_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true,
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    -- Usage context rules
    use_for_positive BOOLEAN DEFAULT true,   -- UC1: loyalty
    use_for_negative BOOLEAN DEFAULT true,   -- UC2: retention
    use_for_pre_purchase BOOLEAN DEFAULT true -- UC3: conversion
);

-- Track promo codes sent in chats
CREATE TABLE promo_code_sends (
    id SERIAL PRIMARY KEY,
    promo_code_id INTEGER REFERENCES promo_codes(id),
    chat_id VARCHAR(100) REFERENCES chats(wb_chat_id),
    message_id VARCHAR(100),
    sent_at TIMESTAMP DEFAULT NOW(),
    -- Context
    trigger_intent VARCHAR(50),  -- e.g., 'positive_feedback', 'quality_complaint'
    trigger_sentiment VARCHAR(20), -- 'positive', 'negative', 'neutral'
    auto_suggested BOOLEAN DEFAULT true,
    operator_approved BOOLEAN DEFAULT true
);

-- Index for analytics
CREATE INDEX idx_promo_sends_code ON promo_code_sends(promo_code_id);
CREATE INDEX idx_promo_sends_chat ON promo_code_sends(chat_id);
CREATE INDEX idx_promo_sends_date ON promo_code_sends(sent_at);
```

### 5.4 AI Analyzer Integration

Extend `ai_analyzer.py` to include promo code suggestions:

```python
# In analyze_chat() function, add promo code suggestion logic

def suggest_promo_code(intent: str, sentiment: str, seller_id: int) -> dict | None:
    """
    Suggest appropriate promo code based on chat context.

    Returns:
        {
            "code": "THANKS10",
            "discount_percent": 10,
            "message_template": "...",
            "reason": "positive_feedback_loyalty"
        }
    """
    # Priority mapping
    promo_rules = {
        # UC2: Retention -- highest priority
        ("defect_not_working", "negative"): {"use_for_negative": True, "min_discount": 10},
        ("wrong_item", "negative"): {"use_for_negative": True, "min_discount": 10},
        ("quality_complaint", "negative"): {"use_for_negative": True, "min_discount": 10},
        ("return_refund", "negative"): {"use_for_negative": True, "min_discount": 15},

        # UC3: Conversion -- medium priority
        ("pre_purchase", "neutral"): {"use_for_pre_purchase": True, "min_discount": 5},
        ("sizing_fit", "neutral"): {"use_for_pre_purchase": True, "min_discount": 5},
        ("availability", "neutral"): {"use_for_pre_purchase": True, "min_discount": 5},

        # UC1: Loyalty -- standard
        ("positive_feedback", "positive"): {"use_for_positive": True, "min_discount": 5},
    }

    rule = promo_rules.get((intent, sentiment))
    if not rule:
        return None

    # Find matching active promo code for this seller
    # ... query promo_codes table ...
    return promo_suggestion
```

### 5.5 API Endpoint for AgentIQ

```python
# New endpoints in AgentIQ backend

# CRUD for promo codes
POST   /api/promo-codes          -- Create/register promo code
GET    /api/promo-codes          -- List seller's active promo codes
PATCH  /api/promo-codes/{id}     -- Update promo code settings
DELETE /api/promo-codes/{id}     -- Deactivate promo code

# AI suggestion
GET    /api/chats/{id}/promo-suggestion  -- Get AI-suggested promo code for chat

# Analytics
GET    /api/promo-codes/analytics        -- Usage stats, conversion tracking
```

### 5.6 Frontend Integration (Chat Center)

In the AI suggestion panel (`.ai-suggestion` inside `.chat-window`):

```
+--------------------------------------------------+
|  AI Suggestion                                    |
|                                                   |
|  Recommended response:                            |
|  "Spasibo za otzyv! Vot vash promokod..."        |
|                                                   |
|  [THANKS10] 10% discount  Expires: Feb 28        |
|                                                   |
|  [Use this promo]  [Edit]  [Skip]                |
+--------------------------------------------------+
```

---

## 6. Risks and Limitations

### 6.1 Current Blockers

| Risk | Impact | Mitigation |
|------|--------|------------|
| **No API for creating promo codes** | Must create codes manually in WB portal | Store pre-created codes in AgentIQ DB, manual sync |
| **Promo codes are NOT per-buyer** | Same code works for everyone, no exclusivity | Use time-limited codes, rotate frequently |
| **Max 10 active promotions** | Limited pool of codes to distribute | Strategic use: 3 for retention, 3 for loyalty, 3 for conversion, 1 reserve |
| **No attribution tracking** | Can't know if buyer used code from chat vs. other channel | Track sends internally, correlate with realization reports |
| **31-day max duration** | Codes expire, need renewal | Auto-remind seller to create new codes |
| **Feature still in testing** | May change rules/limits | Monitor WB announcements |

### 6.2 API Cost Considerations

WB transitioned to **Pay-as-you-go API pricing** in January 2026:
- Cloud services pay per API operation
- This affects third-party integrations like AgentIQ
- Pricing details TBD for specific endpoints

Source: [Avoshop -- Paid API access](https://avoshop.ru/blog/wildberries/platnyy_dostup_k_api_wildberries_dlya_oblachnykh_servisov_s_2026_goda/)

### 6.3 Compliance Risks

- Promo code discount **does not stack** with discounts > 45% -- seller must verify product pricing
- Seller bears full discount cost -- must calculate margin impact
- AgentIQ should include a **margin calculator** to prevent sellers from offering unprofitable discounts

---

## 7. Roadmap Recommendation

### Phase 1 (Now -- February 2026): Manual Integration
- Add promo code storage in AgentIQ DB (manual entry by seller)
- AI suggests promo code text in chat responses
- Operator copies promo code into message
- Internal tracking of promo code sends

### Phase 2 (March-April 2026): Semi-Automated
- AI auto-inserts promo code into draft response
- One-click send with promo code
- Dashboard: promo codes sent per day, by intent type
- Alerts when promo code is about to expire

### Phase 3 (When WB API adds promo code endpoints): Full Automation
- Auto-create promo code campaigns via WB API
- Dynamic promo code assignment based on chat context
- Full attribution: track code creation -> distribution -> usage -> realization
- ROI dashboard: revenue from promo code campaigns

### Phase 4 (Future): Smart Promo Optimization
- AI learns which discount % converts best for each intent
- A/B testing: 5% vs. 10% vs. 15% for retention
- Predictive: auto-adjust discount based on customer value (order history)
- Cross-sell: suggest promo on complementary products

---

## 8. Comparison with Ozon

| Feature | Wildberries (Jan 2026) | Ozon |
|---------|----------------------|------|
| Promo code creation | Seller portal only | Seller portal |
| API for promo codes | Not yet | Limited (premium) |
| Discount type | % only | % or fixed RUB |
| Max duration | 31 days | 6 months |
| Active campaigns limit | 10 | Higher |
| Send in chat | Text message only | Native integration |
| Per-buyer codes | No | No |
| Attribution tracking | Realization reports only | Better tracking |

---

## 9. Key Takeaways for AgentIQ Product

1. **First-mover advantage:** No competitor automates promo code distribution in WB chats. AgentIQ can be first.

2. **Manual sync is fine for MVP:** Sellers create 5-10 promo codes in WB portal, input them into AgentIQ. AI handles distribution logic.

3. **High value for retention use case:** Dissatisfied customer + promo code in chat = chance to prevent negative review. This directly ties to WB's 3-day window for saving negative reviews.

4. **Chat API is sufficient:** We can send promo codes as plain text in chat messages using the existing Chat API. No new API integration needed.

5. **ROI story for sellers:** Promo code costs seller 5-15% discount, but saves a negative review that could cost much more in lost sales (negative review impact >> 15% discount on one order).

6. **Watch WB API updates:** Monitor https://dev.wildberries.ru/en/release-notes for promo code API endpoints. They will come -- WB has a pattern of UI-first, then API.

---

## Sources

- [WB Partners -- Seller Promo Codes (official instructions)](https://seller.wildberries.ru/instructions/ru/ru/material/seller-promocodes)
- [Forbes.ru -- WB promo codes launch](https://www.forbes.ru/novosti-kompaniy/554273-na-wildberries-poavilis-promokody-ot-prodavcov)
- [Retail.ru -- WB promo codes for sellers](https://www.retail.ru/news/wildberries-pozvolit-selleram-sozdavat-promokody-dlya-pokupateley-27-yanvarya-2026-273815/)
- [logistics.ru -- WB promo codes economics](https://logistics.ru/internet-torgovlya-i-fulfilment/promokody-ot-prodavcov-na-wildberries-kak-novyy-instrument-menyaet)
- [Sellermate.io -- WB 2026 updates](https://sellermate.io/blog/tpost/mxepvd4801-wildberries-2026-promokodi-prodavtsov-no)
- [ixbt.com -- WB promo codes](https://www.ixbt.com/news/2026/01/27/v-wildberries-pojavilis-promokody-ot-prodavcov.html)
- [WB API Documentation (Promotions)](https://dev.wildberries.ru/en/openapi/promotion)
- [WB API Swagger (Promotions)](https://dev.wildberries.ru/en/swagger/promotion)
- [WB API Swagger (Communications/Chat)](https://dev.wildberries.ru/en/swagger/communications)
- [WB API Release Notes](https://dev.wildberries.ru/en/release-notes)
- [WB API (old portal)](https://openapi.wildberries.ru/promotion/api/en/)
- [Ozon -- How to create coupons](https://seller.ozon.ru/media/boost/kak-sozdat-svoj-promokod-na-ozon/)
- [IntellectDialog -- Marketplace automation](https://intellectdialog.com/tpost/wildberries-ozon-yandex-market-amocrm-automation)
- [Wildbox -- Discount/promo code instructions](https://wildbox.ru/blog/instructions-for-installing-discounts/)
- [Avoshop -- Paid API access 2026](https://avoshop.ru/blog/wildberries/platnyy_dostup_k_api_wildberries_dlya_oblachnykh_servisov_s_2026_goda/)
- [Dakword/WBSeller -- GitHub library](https://github.com/Dakword/WBSeller)
- [Moneyplace -- Set discounts and promo codes](https://moneyplace.io/wildberries/stat-wb/kak-ustanovit-skidki-i-promokody-na-t/)
