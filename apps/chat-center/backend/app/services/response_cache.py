"""Fast response cache for common auto-response patterns.

Avoids LLM call entirely for simple, predictable cases such as
positive feedback on 5-star reviews. Templates are pre-approved and
rotate randomly to avoid repetition.

Cache key: (intent, rating, channel).
"""

from __future__ import annotations

import logging
import random
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template banks
# ---------------------------------------------------------------------------

# Positive review templates (rating 4-5, channel=review)
POSITIVE_REVIEW_TEMPLATES: List[str] = [
    "Спасибо за отзыв! Рады, что товар оправдал ожидания. Приятных покупок!",
    "Благодарим за тёплые слова! Мы рады, что товар понравился. Ждём вас снова!",
    "Спасибо за отличный отзыв! Ваша обратная связь очень важна для нас.",
    "Благодарим за высокую оценку! Мы стараемся для наших покупателей.",
    "Спасибо, что нашли время оставить отзыв! Рады, что вы довольны покупкой.",
    "Благодарим за доверие! Будем рады видеть вас среди наших покупателей снова.",
    "Спасибо за добрые слова! Ваш отзыв мотивирует нас становиться лучше.",
    "Рады, что товар понравился! Спасибо за обратную связь.",
    "Благодарим за покупку и высокую оценку! Рады, что всё понравилось.",
    "Спасибо за отзыв! Мы ценим каждого покупателя. Приятного использования!",
]

# Thanks intent templates (channel=chat, buyer says thank you)
THANKS_CHAT_TEMPLATES: List[str] = [
    "Рады помочь! Если возникнут вопросы — обращайтесь.",
    "Спасибо за обратную связь! Рады, что всё решилось.",
    "Рады, что смогли помочь! Хорошего дня!",
    "Спасибо за тёплые слова! Обращайтесь, если понадобится помощь.",
    "Рады, что всё получилось! Будем рады помочь снова.",
]

# ---------------------------------------------------------------------------
# Cache lookup configuration
# ---------------------------------------------------------------------------

# Maps (channel, intent, rating_range) to template list.
# Rating range: (min_rating, max_rating) inclusive, or None for any rating.
_CACHE_RULES: List[Tuple[str, str, Optional[Tuple[int, int]], List[str]]] = [
    # Positive reviews (4-5 stars) with short/empty text
    ("review", "thanks", (4, 5), POSITIVE_REVIEW_TEMPLATES),
    # Chat thanks intent
    ("chat", "thanks", None, THANKS_CHAT_TEMPLATES),
]

# Maximum text length for a "simple" review eligible for caching.
# Longer reviews likely contain specific details that need LLM attention.
_SIMPLE_TEXT_MAX_LEN = 100

# Keywords that indicate the review has substance beyond simple praise.
# If any of these appear, fall through to LLM for a tailored response.
_COMPLEX_KEYWORDS: List[str] = [
    "но",
    "однако",
    "правда",
    "жаль",
    "минус",
    "недостат",
    "проблем",
    "брак",
    "дефект",
    "возврат",
    "замен",
    "размер",
    "не подош",
    "маломер",
    "большемер",
    "запах",
    "сломал",
    "не работа",
    "обман",
]


def _has_complex_content(text: str) -> bool:
    """Return True if text contains substance requiring LLM analysis."""
    if not text:
        return False
    lower = text.lower()
    return any(kw in lower for kw in _COMPLEX_KEYWORDS)


def _match_rating(
    rating: Optional[int],
    rating_range: Optional[Tuple[int, int]],
) -> bool:
    """Check if rating falls within the specified range."""
    if rating_range is None:
        return True
    if rating is None:
        return False
    return rating_range[0] <= rating <= rating_range[1]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_cached_response(
    *,
    intent: str,
    rating: Optional[int],
    channel: str,
    text: str = "",
) -> Optional[str]:
    """Get cached response template if available.

    Returns ``None`` if the interaction requires a full LLM call (complex
    content, unknown intent, or no matching template).

    Args:
        intent: Classified intent (e.g. 'thanks').
        rating: Review rating 1-5, or None for non-review channels.
        channel: One of 'review', 'question', 'chat'.
        text: Customer text (used to check for complex content).
    """
    # Questions always need LLM (answer depends on specific question content)
    if channel == "question":
        return None

    # Check text complexity -- if too long or contains substance, use LLM
    if text and len(text) > _SIMPLE_TEXT_MAX_LEN:
        return None
    if _has_complex_content(text):
        return None

    # Search for matching cache rule
    for rule_channel, rule_intent, rule_rating_range, templates in _CACHE_RULES:
        if channel == rule_channel and intent == rule_intent:
            if _match_rating(rating, rule_rating_range):
                chosen = random.choice(templates)
                logger.info(
                    "Cache hit: channel=%s intent=%s rating=%s -> template response",
                    channel,
                    intent,
                    rating,
                )
                return chosen

    return None


async def get_fast_positive_response() -> str:
    """Get random positive response template (no LLM call needed).

    Convenience function for the most common case: positive review, 4-5 stars.
    """
    return random.choice(POSITIVE_REVIEW_TEMPLATES)
