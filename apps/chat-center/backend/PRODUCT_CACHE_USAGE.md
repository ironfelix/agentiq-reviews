# Product Cache — Quick Reference Guide

## What is Product Cache?

Database-backed cache of WB product metadata (name, brand, category, characteristics) fetched from CDN. Used to enrich AI drafts with product context.

**TTL:** 24 hours
**Source:** WB CDN `card.json` (no auth required)
**Fallback:** Stale cache if CDN unavailable

---

## Quick Start

### 1. Apply Migration

```bash
cd apps/chat-center/backend
source venv/bin/activate
alembic upgrade head
```

### 2. Verify Database

```sql
-- Check migration applied
SELECT * FROM alembic_version;
-- Should show: 0003

-- Check table exists
\d product_cache

-- Sample query
SELECT nm_id, name, brand, fetched_at
FROM product_cache
LIMIT 10;
```

### 3. Run Tests

```bash
pytest tests/test_product_cache.py -v
```

Expected: 26 passed

---

## Usage Examples

### Fetch Product from Cache/CDN

```python
from app.services.product_cache_service import get_or_fetch_product

async def example(db: AsyncSession, nm_id: str):
    product = await get_or_fetch_product(db, nm_id)

    if product:
        print(f"Product: {product.name}")
        print(f"Brand: {product.brand}")
        print(f"Category: {product.category}")
        print(f"Options: {product.options}")
    else:
        print("Product not available (CDN down or invalid nm_id)")
```

### Get Formatted Context for AI

```python
from app.services.product_cache_service import (
    get_or_fetch_product,
    get_product_context_for_draft,
)

async def generate_ai_draft(db: AsyncSession, interaction: Interaction):
    # Fetch product
    product = await get_or_fetch_product(db, interaction.nm_id)

    # Format for AI prompt
    product_context = get_product_context_for_draft(product)

    if product_context:
        # Output example:
        # "Товар: Nike Air Max 90. Бренд: Nike. Категория: Кроссовки.
        #  Характеристики: Размер: 42, Цвет: Черный."

        # Use in prompt
        prompt = f"""
        Product: {product_context}

        Customer message: {interaction.text}
        Draft a response...
        """
    else:
        # No product context available, use generic prompt
        prompt = f"Customer message: {interaction.text}"
```

### Check Cache Freshness

```python
from datetime import datetime, timedelta, timezone
from app.services.product_cache_service import CACHE_TTL_HOURS

async def is_cache_fresh(product: ProductCache) -> bool:
    if not product.fetched_at:
        return False

    age = datetime.now(timezone.utc) - product.fetched_at
    return age < timedelta(hours=CACHE_TTL_HOURS)
```

### Manual Cache Refresh

```python
from app.services.product_cache_service import fetch_product_from_cdn

async def force_refresh(db: AsyncSession, nm_id: str):
    """Force CDN refresh bypassing cache."""
    nm_id_int = int(nm_id)

    # Fetch from CDN
    card_data = await fetch_product_from_cdn(nm_id_int)

    if card_data:
        # Update or insert
        from app.models.product_cache import ProductCache
        from sqlalchemy import select

        result = await db.execute(
            select(ProductCache).where(ProductCache.nm_id == nm_id)
        )
        cached = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if cached:
            cached.name = card_data["name"]
            cached.brand = card_data["brand"]
            cached.fetched_at = now
        else:
            cached = ProductCache(nm_id=nm_id, **card_data, fetched_at=now)
            db.add(cached)

        await db.commit()
```

---

## API Reference

### Functions

#### `get_basket_number(nm_id: int) -> str`

Get WB CDN basket number.

**Args:**
- `nm_id`: Wildberries article number

**Returns:**
- Basket number: `"01"` to `"26"`

**Example:**
```python
basket = get_basket_number(12345678)  # "03"
```

---

#### `build_card_url(nm_id: int) -> str`

Build full CDN URL for card.json.

**Args:**
- `nm_id`: Wildberries article number

**Returns:**
- Full URL: `https://basket-{N}.wbbasket.ru/vol{V}/part{P}/{nmId}/info/ru/card.json`

**Example:**
```python
url = build_card_url(12345678)
# "https://basket-03.wbbasket.ru/vol123/part12345/12345678/info/ru/card.json"
```

---

#### `fetch_product_from_cdn(nm_id: int) -> Optional[Dict]`

Fetch and parse product card from WB CDN.

**Args:**
- `nm_id`: Wildberries article number

**Returns:**
- `Dict` with keys: `name`, `description`, `brand`, `category`, `options`, `image_url`
- `None` if CDN unavailable or error

**Example:**
```python
card = await fetch_product_from_cdn(12345678)

if card:
    print(card["name"])        # "Nike Air Max 90"
    print(card["brand"])       # "Nike"
    print(card["options"])     # [{"name": "Размер", "value": "42"}, ...]
```

**Error handling:**
- HTTP 404 → `None`
- Timeout (5s) → `None`
- Invalid JSON → `None`
- Logs debug messages, never crashes

---

#### `get_or_fetch_product(db: AsyncSession, nm_id: str) -> Optional[ProductCache]`

Get product from DB cache or fetch from CDN if stale/missing.

**Args:**
- `db`: Async database session
- `nm_id`: Article number as string (from `Interaction.nm_id`)

**Returns:**
- `ProductCache` instance
- `None` if invalid nm_id or CDN unavailable with no cache

**Cache logic:**
1. Check DB: if fresh (< 24h) → return
2. If stale: fetch CDN → upsert → return
3. If CDN down: return stale cache (fallback)
4. If no cache + CDN down: return `None`

**Example:**
```python
product = await get_or_fetch_product(db, "12345678")

if product:
    print(f"Name: {product.name}")
    print(f"Fetched: {product.fetched_at}")

    # Check if fresh
    age = datetime.now(timezone.utc) - product.fetched_at
    is_fresh = age < timedelta(hours=24)
```

---

#### `get_product_context_for_draft(db_product: Optional[ProductCache]) -> str`

Format product into concise text for AI prompt.

**Args:**
- `db_product`: `ProductCache` instance or `None`

**Returns:**
- Formatted string (example: `"Товар: Nike Air Max 90. Бренд: Nike. Категория: Кроссовки. Характеристики: Размер: 42, Цвет: Черный."`)
- Empty string if `None` or no name

**Rules:**
- Includes brand only if present
- Includes category only if present
- Limits to first 5 options
- Ends with period

**Example:**
```python
context = get_product_context_for_draft(product)

if context:
    # Use in AI prompt
    prompt = f"Product: {context}\n\nCustomer: {message}"
else:
    # Generic prompt without product context
    prompt = f"Customer: {message}"
```

---

## Database Schema

```sql
CREATE TABLE product_cache (
    id INTEGER PRIMARY KEY,
    nm_id VARCHAR(50) NOT NULL UNIQUE,
    marketplace VARCHAR(50) DEFAULT 'wb' NOT NULL,

    -- Product metadata
    name VARCHAR(500),
    description TEXT,
    brand VARCHAR(200),
    category VARCHAR(300),
    options JSON,
    image_url VARCHAR(500),

    -- Cache metadata
    fetched_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE UNIQUE INDEX ix_product_cache_nm_id ON product_cache(nm_id);
CREATE INDEX ix_product_cache_id ON product_cache(id);
```

**Sample row:**
```json
{
  "id": 1,
  "nm_id": "12345678",
  "marketplace": "wb",
  "name": "Nike Air Max 90",
  "description": "Классические кроссовки...",
  "brand": "Nike",
  "category": "Кроссовки",
  "options": [
    {"name": "Размер", "value": "42"},
    {"name": "Цвет", "value": "Черный"}
  ],
  "image_url": "https://basket-03.wbbasket.ru/.../1.jpg",
  "fetched_at": "2026-02-15T10:30:00Z",
  "created_at": "2026-02-15T10:30:00Z",
  "updated_at": null
}
```

---

## Troubleshooting

### Product not found in cache

```python
# Check if nm_id is valid
product = await get_or_fetch_product(db, "invalid")
# Returns: None

# Check CDN directly
card = await fetch_product_from_cdn(12345678)
if not card:
    print("CDN unavailable or product doesn't exist")
```

### Stale cache not refreshing

```python
# Check fetched_at timestamp
product = await get_or_fetch_product(db, "12345678")
print(f"Last fetched: {product.fetched_at}")

# Force refresh (see "Manual Cache Refresh" example above)
```

### CDN timeout

```python
# Default timeout is 5 seconds (CDN_TIMEOUT_SECONDS)
# If CDN is slow, increase in product_cache_service.py:
CDN_TIMEOUT_SECONDS = 10.0  # 10 seconds
```

### Context string too long

```python
# Limit options to fewer than 5
# Edit get_product_context_for_draft() in product_cache_service.py:
for opt in options_list[:3]:  # Change from 5 to 3
```

---

## Integration Points (Wave 2)

### interaction_drafts.py

```python
# Add to generate_interaction_draft()
from app.services.product_cache_service import (
    get_or_fetch_product,
    get_product_context_for_draft,
)

product = await get_or_fetch_product(db, interaction.nm_id)
product_context = get_product_context_for_draft(product)

# Pass to AI analyzer
analysis = await analyzer.analyze_chat(
    messages=messages,
    product_context=product_context,  # NEW
    ...
)
```

### ai_analyzer.py

```python
# Update CHAT_ANALYSIS_USER prompt template
CHAT_ANALYSIS_USER = """Проанализируй чат и предложи ответ.

Товар: {product_name}
{product_context_block}  # NEW: formatted product metadata
...
"""
```

---

## Performance Notes

**Cache hit (product < 24h old):**
- 1 DB query: ~1-5ms
- Total: <10ms ✅ Fast

**Cache miss (fetch from CDN):**
- 1 DB query: ~1-5ms
- 1 HTTP GET: ~50-200ms
- 1 DB upsert: ~5-10ms
- Total: ~60-220ms (one-time cost)

**Recommendation:**
- Cache hit rate should be >95% after initial warm-up
- Monitor CDN latency (should be <200ms)
- If CDN is slow, increase `CDN_TIMEOUT_SECONDS`

---

## Constants

```python
from app.services.product_cache_service import (
    CACHE_TTL_HOURS,        # 24 (hours)
    CDN_TIMEOUT_SECONDS,    # 5.0 (seconds)
)
```

---

## Testing

Run all tests:
```bash
pytest tests/test_product_cache.py -v
```

Run specific test class:
```bash
pytest tests/test_product_cache.py::TestGetOrFetchProduct -v
```

Run with coverage:
```bash
pytest tests/test_product_cache.py --cov=app.services.product_cache_service --cov-report=html
```

---

## Maintenance

### Clear old cache (>30 days)

```sql
DELETE FROM product_cache
WHERE fetched_at < NOW() - INTERVAL '30 days';
```

### View cache stats

```sql
-- Total cached products
SELECT COUNT(*) FROM product_cache;

-- Fresh cache (< 24h)
SELECT COUNT(*)
FROM product_cache
WHERE fetched_at > NOW() - INTERVAL '24 hours';

-- Stale cache (>= 24h)
SELECT COUNT(*)
FROM product_cache
WHERE fetched_at <= NOW() - INTERVAL '24 hours';

-- Top brands
SELECT brand, COUNT(*)
FROM product_cache
WHERE brand IS NOT NULL
GROUP BY brand
ORDER BY COUNT(*) DESC
LIMIT 10;
```

### Bulk refresh

```python
from sqlalchemy import select
from app.models.product_cache import ProductCache
from app.services.product_cache_service import get_or_fetch_product

async def refresh_all_products(db: AsyncSession):
    """Refresh all stale products (>= 24h old)."""
    result = await db.execute(
        select(ProductCache).where(
            ProductCache.fetched_at <= datetime.now(timezone.utc) - timedelta(hours=24)
        )
    )
    stale_products = result.scalars().all()

    for product in stale_products:
        await get_or_fetch_product(db, product.nm_id)
        await asyncio.sleep(0.1)  # Rate limit: 10 req/sec
```

---

## FAQ

**Q: Why database cache instead of in-memory?**
A: Persistence across restarts, shared across workers, easier debugging.

**Q: Why 24h TTL?**
A: Product metadata changes infrequently (price/stock not cached). Balances freshness vs CDN load.

**Q: What if CDN is down?**
A: Stale cache is used as fallback. If no cache, returns `None` (graceful degradation).

**Q: Does it cache price?**
A: No, only metadata. For price, use `price-history.json` (separate endpoint).

**Q: Can I prefetch products?**
A: Yes, call `get_or_fetch_product()` for top 100 nm_ids on startup.

**Q: Does it work with Ozon?**
A: No, WB only. For Ozon, add separate connector (different CDN structure).
