"""Product cache service for WB CDN card.json synchronization.

Provides database-backed product cache with 24h TTL. Gracefully handles
CDN failures and provides formatted context strings for AI prompts.
"""

from __future__ import annotations

import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_cache import ProductCache

logger = logging.getLogger(__name__)

# Cache TTL: 24 hours (product data changes infrequently)
CACHE_TTL_HOURS = 24

# HTTP timeout for CDN requests (fast fail on unreachable CDN)
CDN_TIMEOUT_SECONDS = 5.0


def get_basket_number(nm_id: int) -> str:
    """Get WB CDN basket number by nmID.

    Basket ranges as of Feb 2026 (vol = nm_id // 100000):
    ≤143→01 ≤287→02 ≤431→03 ≤719→04 ≤1007→05 ≤1061→06 ≤1115→07
    ≤1169→08 ≤1313→09 ≤1601→10 ≤1655→11 ≤1919→12 ≤2045→13
    ≤2189→14 ≤2405→15 ≤2621→16 ≤2837→17 ≤3053→18 ≤3269→19
    ≤3485→20 ≤3701→21 ≤3917→22 ≤4133→23 ≤4349→24 ≤4565→25 else→26

    Args:
        nm_id: Wildberries article number

    Returns:
        Basket number as zero-padded string (e.g., "01", "26")
    """
    vol = nm_id // 100000
    ranges = [
        (143, "01"), (287, "02"), (431, "03"), (719, "04"), (1007, "05"),
        (1061, "06"), (1115, "07"), (1169, "08"), (1313, "09"), (1601, "10"),
        (1655, "11"), (1919, "12"), (2045, "13"), (2189, "14"), (2405, "15"),
        (2621, "16"), (2837, "17"), (3053, "18"), (3269, "19"), (3485, "20"),
        (3701, "21"), (3917, "22"), (4133, "23"), (4349, "24"), (4565, "25"),
    ]
    for threshold, basket in ranges:
        if vol <= threshold:
            return basket
    return "26"


def build_card_url(nm_id: int) -> str:
    """Build full URL to WB CDN card.json.

    Args:
        nm_id: Wildberries article number

    Returns:
        Full CDN URL for card.json
    """
    basket = get_basket_number(nm_id)
    vol = nm_id // 100000
    part = nm_id // 1000
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"


async def fetch_product_from_cdn(nm_id: int) -> Optional[Dict]:
    """Fetch product card from WB CDN and extract fields.

    Makes HTTP GET request to card.json, parses JSON, extracts:
    - name (imt_name)
    - description
    - brand
    - category (subj_name)
    - options (array of {name, value})

    Args:
        nm_id: Wildberries article number

    Returns:
        Dict with extracted fields or None if CDN unavailable/failed
    """
    url = build_card_url(nm_id)

    try:
        async with httpx.AsyncClient(timeout=CDN_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

            # Extract options
            options = []
            for opt in data.get("options", []):
                name = (opt.get("name") or "").strip()
                value = (opt.get("value") or "").strip()
                if name and value:
                    options.append({"name": name, "value": value})

            # Extract first image URL if available
            image_url = None
            media = data.get("media", {})
            if isinstance(media, dict):
                photo_360 = media.get("photo360", [])
                if photo_360 and isinstance(photo_360, list):
                    image_url = photo_360[0] if photo_360[0] else None

            return {
                "name": (data.get("imt_name") or "").strip(),
                "description": (data.get("description") or "").strip(),
                "brand": (data.get("brand") or "").strip(),
                "category": (data.get("subj_name") or "").strip(),
                "options": options,
                "image_url": image_url,
            }

    except httpx.HTTPStatusError as e:
        logger.debug("CDN HTTP error for nm_id=%s: %s", nm_id, e.response.status_code)
        return None
    except httpx.TimeoutException:
        logger.debug("CDN timeout for nm_id=%s", nm_id)
        return None
    except Exception as e:
        logger.debug("CDN fetch failed for nm_id=%s: %s", nm_id, e)
        return None


async def get_or_fetch_product(db: AsyncSession, nm_id: str) -> Optional[ProductCache]:
    """Get product from DB cache or fetch from CDN if stale/missing.

    Cache logic:
    - If in DB and fetched_at < 24h ago → return from cache
    - Else fetch from CDN, upsert to DB, return

    Args:
        db: Async database session
        nm_id: Article number as string (from Interaction.nm_id)

    Returns:
        ProductCache instance or None if CDN unavailable
    """
    if not nm_id:
        return None

    try:
        nm_id_int = int(nm_id)
    except (ValueError, TypeError):
        logger.debug("Invalid nm_id format: %s", nm_id)
        return None

    # Check DB cache
    result = await db.execute(
        select(ProductCache).where(ProductCache.nm_id == nm_id)
    )
    cached = result.scalar_one_or_none()

    # Cache hit: check if fresh
    if cached and cached.fetched_at:
        age = datetime.now(timezone.utc) - cached.fetched_at
        if age < timedelta(hours=CACHE_TTL_HOURS):
            logger.debug("Cache hit for nm_id=%s (age=%s)", nm_id, age)
            return cached

    # Cache miss or stale: fetch from CDN
    logger.debug("Cache miss/stale for nm_id=%s, fetching from CDN", nm_id)
    card_data = await fetch_product_from_cdn(nm_id_int)

    if not card_data:
        # CDN unavailable: return stale cache if exists, else None
        if cached:
            logger.debug("CDN unavailable, returning stale cache for nm_id=%s", nm_id)
            return cached
        return None

    # Upsert to DB
    now = datetime.now(timezone.utc)
    if cached:
        # Update existing
        cached.name = card_data["name"]
        cached.description = card_data["description"]
        cached.brand = card_data["brand"]
        cached.category = card_data["category"]
        cached.options = card_data["options"]
        cached.image_url = card_data["image_url"]
        cached.fetched_at = now
        cached.updated_at = now
    else:
        # Insert new
        cached = ProductCache(
            nm_id=nm_id,
            marketplace="wb",
            name=card_data["name"],
            description=card_data["description"],
            brand=card_data["brand"],
            category=card_data["category"],
            options=card_data["options"],
            image_url=card_data["image_url"],
            fetched_at=now,
        )
        db.add(cached)

    await db.commit()
    await db.refresh(cached)
    logger.debug("Upserted product cache for nm_id=%s", nm_id)

    return cached


def get_product_context_for_draft(db_product: Optional[ProductCache]) -> str:
    """Format product cache into concise text context for AI prompt.

    Returns formatted string like:
    "Товар: Nike Air Max 90. Бренд: Nike. Категория: Кроссовки. Характеристики: Размер: 42, Цвет: Черный."

    Args:
        db_product: ProductCache instance or None

    Returns:
        Formatted context string or empty string if no product
    """
    if not db_product or not db_product.name:
        return ""

    parts = []

    # Product name
    parts.append(f"Товар: {db_product.name}")

    # Brand
    if db_product.brand:
        parts.append(f"Бренд: {db_product.brand}")

    # Category
    if db_product.category:
        parts.append(f"Категория: {db_product.category}")

    # Key characteristics from options (limit to first 5)
    if db_product.options:
        options_list = db_product.options if isinstance(db_product.options, list) else []
        if options_list:
            key_options = []
            for opt in options_list[:5]:
                if isinstance(opt, dict) and opt.get("name") and opt.get("value"):
                    key_options.append(f"{opt['name']}: {opt['value']}")
            if key_options:
                parts.append(f"Характеристики: {', '.join(key_options)}")

    return ". ".join(parts) + "."
