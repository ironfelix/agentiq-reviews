"""Product context enrichment for AI draft generation.

Fetches product card data from WB CDN and formats it into a concise
text block for injection into the LLM prompt. Includes in-memory
cache with TTL to avoid redundant CDN requests (same product gets
multiple reviews/questions).
"""

from __future__ import annotations

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory cache: nm_id -> (card_dict, timestamp)
# TTL = 3600 seconds (1 hour). Empty dict = negative cache entry.
# ---------------------------------------------------------------------------
_CARD_CACHE: Dict[int, tuple[Dict, float]] = {}
_CACHE_TTL = 3600  # 1 hour
_CACHE_MAX_SIZE = 500  # Prevent unbounded growth


def get_cached_product_card(nm_id: int) -> Optional[Dict]:
    """Return cached card or None if not cached / expired."""
    entry = _CARD_CACHE.get(nm_id)
    if entry is None:
        return None
    card, ts = entry
    if time.time() - ts > _CACHE_TTL:
        _CARD_CACHE.pop(nm_id, None)
        return None
    return card


def set_cached_product_card(nm_id: int, card: Dict) -> None:
    """Store card in cache. Evicts oldest entries if cache is full."""
    if len(_CARD_CACHE) >= _CACHE_MAX_SIZE:
        # Evict oldest 20% of entries
        items = sorted(_CARD_CACHE.items(), key=lambda x: x[1][1])
        for key, _ in items[: _CACHE_MAX_SIZE // 5]:
            _CARD_CACHE.pop(key, None)
    _CARD_CACHE[nm_id] = (card, time.time())


# ---------------------------------------------------------------------------
# Product context builder
# ---------------------------------------------------------------------------

_MAX_CONTEXT_LENGTH = 500  # characters


def build_product_context(card: Dict) -> str:
    """Format product card data into a text block for the LLM prompt.

    Output is capped at ~500 characters to avoid bloating the prompt.

    Args:
        card: Parsed product card dict from fetch_product_card()

    Returns:
        Formatted text block or empty string if card is empty/unusable
    """
    if not card or not card.get("name"):
        return ""

    parts: list[str] = []

    # Product name
    parts.append(f"Название: {card['name']}")

    # Category
    category = card.get("category", "")
    subcategory = card.get("subcategory", "")
    if category and subcategory:
        parts.append(f"Категория: {category} > {subcategory}")
    elif category:
        parts.append(f"Категория: {category}")

    # Description (truncated)
    description = card.get("description", "")
    if description:
        if len(description) > 150:
            description = description[:147] + "..."
        parts.append(f"Описание: {description}")

    # Options (key specs)
    options = card.get("options", [])
    if options:
        specs = ". ".join(f"{opt['name']}: {opt['value']}" for opt in options[:8])
        parts.append(f"Характеристики: {specs}")

    # Compositions (material breakdown)
    compositions = card.get("compositions", [])
    if compositions and not any(opt.get("name", "").lower() == "состав" for opt in options):
        comp_str = ", ".join(f"{c['name']} {c['value']}%" for c in compositions)
        parts.append(f"Состав: {comp_str}")

    result = "\n".join(parts)

    # Truncate to max length
    if len(result) > _MAX_CONTEXT_LENGTH:
        result = result[:_MAX_CONTEXT_LENGTH - 3] + "..."

    return result


async def get_product_context_for_nm_id(nm_id_str: Optional[str]) -> str:
    """High-level helper: fetch card and build context string.

    Args:
        nm_id_str: nm_id as string (from Interaction.nm_id) or None

    Returns:
        Formatted product context string, or empty string if unavailable
    """
    if not nm_id_str:
        return ""

    try:
        nm_id = int(nm_id_str)
    except (ValueError, TypeError):
        return ""

    from app.services.wb_connector import fetch_product_card

    card = await fetch_product_card(nm_id)
    if not card:
        return ""

    return build_product_context(card)


def build_rating_context(rating: Optional[int], channel: str) -> str:
    """Build rating-aware prompt instruction for the LLM.

    Args:
        rating: Star rating (1-5) or None
        channel: Interaction channel (review, question, chat)

    Returns:
        Rating-aware instruction string for injection into user prompt
    """
    if channel == "chat" or rating is None:
        return ""

    if channel == "review":
        if rating <= 2:
            return (
                f"Рейтинг отзыва: {'*' * rating} ({rating}/5) - НЕГАТИВНЫЙ.\n"
                "Тон ответа: эмпатичный. Признай проблему, вырази сожаление. "
                "Если проблема очевидна (брак, не тот товар) - сразу дай инструкцию по возврату через ЛК WB. "
                "НЕ оправдывайся и НЕ обвиняй покупателя."
            )
        elif rating == 3:
            return (
                f"Рейтинг отзыва: {'*' * rating} ({rating}/5) - НЕЙТРАЛЬНЫЙ.\n"
                "Тон ответа: сбалансированный. Поблагодари за обратную связь, "
                "обрати внимание на замечания покупателя и предложи решение."
            )
        else:  # 4-5
            return (
                f"Рейтинг отзыва: {'*' * rating} ({rating}/5) - ПОЗИТИВНЫЙ.\n"
                "Тон ответа: благодарный. Поблагодари за отзыв, "
                "подчеркни, что рады положительному опыту. Будь кратким."
            )

    if channel == "question":
        return (
            "Это ВОПРОС покупателя (не отзыв). "
            "Дай конкретный, полезный ответ на основе информации о товаре. "
            "Ответ публичный — помогает другим покупателям. "
            "Можно и нужно давать технические детали из характеристик товара."
        )

    return ""
