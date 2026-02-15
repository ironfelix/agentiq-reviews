"""Tests for response_cache service.

Validates that:
- Cache returns template for positive_feedback 5-star reviews
- Cache returns template for 4-star reviews
- Cache returns None for non-positive intents (defect, refund, etc.)
- Cache returns None for questions (always need LLM)
- Cache returns None for complex text with complaints
- Templates are valid (non-empty, pass guardrails)
- Random selection works (not always the same response)
- get_fast_positive_response returns valid template
"""

from __future__ import annotations

import asyncio
import pytest
from typing import Optional

from app.services.response_cache import (
    POSITIVE_REVIEW_TEMPLATES,
    THANKS_CHAT_TEMPLATES,
    get_cached_response,
    get_fast_positive_response,
    _has_complex_content,
    _SIMPLE_TEXT_MAX_LEN,
)


# ---------------------------------------------------------------------------
# Helper: run async functions in sync tests
# ---------------------------------------------------------------------------

def _run(coro):
    """Run async coroutine in sync test."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Test: cache hit for positive reviews
# ---------------------------------------------------------------------------

class TestCacheHitPositive:
    """Cache should return template for simple positive reviews."""

    def test_positive_review_5_star(self):
        """5-star review with 'thanks' intent should hit cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=5,
            channel="review",
            text="Отличный товар!",
        ))
        assert result is not None
        assert isinstance(result, str)
        assert len(result) > 10
        assert result in POSITIVE_REVIEW_TEMPLATES

    def test_positive_review_4_star(self):
        """4-star review with 'thanks' intent should hit cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=4,
            channel="review",
            text="Хороший товар, рекомендую",
        ))
        assert result is not None
        assert result in POSITIVE_REVIEW_TEMPLATES

    def test_positive_review_empty_text(self):
        """Empty text review should still hit cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=5,
            channel="review",
            text="",
        ))
        assert result is not None
        assert result in POSITIVE_REVIEW_TEMPLATES

    def test_thanks_chat_intent(self):
        """Chat thanks intent should hit cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=None,
            channel="chat",
            text="Спасибо!",
        ))
        assert result is not None
        assert result in THANKS_CHAT_TEMPLATES


# ---------------------------------------------------------------------------
# Test: cache miss for non-positive intents
# ---------------------------------------------------------------------------

class TestCacheMissNonPositive:
    """Cache should return None for intents that need LLM analysis."""

    def test_defect_intent(self):
        """Defect reviews must go to LLM."""
        result = _run(get_cached_response(
            intent="defect_not_working",
            rating=1,
            channel="review",
            text="Сломался через день",
        ))
        assert result is None

    def test_wrong_item_intent(self):
        """Wrong item reviews must go to LLM."""
        result = _run(get_cached_response(
            intent="wrong_item",
            rating=2,
            channel="review",
            text="Прислали не тот товар",
        ))
        assert result is None

    def test_refund_intent(self):
        """Refund requests must go to LLM."""
        result = _run(get_cached_response(
            intent="refund_exchange",
            rating=2,
            channel="review",
            text="Хочу вернуть",
        ))
        assert result is None

    def test_low_rating_thanks(self):
        """Thanks intent with 1-3 star rating should NOT hit cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=2,
            channel="review",
            text="Спасибо",
        ))
        assert result is None

    def test_question_channel_always_misses(self):
        """Questions always need LLM regardless of intent."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=5,
            channel="question",
            text="Спасибо за ответ!",
        ))
        assert result is None

    def test_other_intent(self):
        """Unknown/other intent should not hit cache."""
        result = _run(get_cached_response(
            intent="other",
            rating=5,
            channel="review",
            text="",
        ))
        assert result is None


# ---------------------------------------------------------------------------
# Test: complex text bypasses cache
# ---------------------------------------------------------------------------

class TestCacheMissComplexText:
    """Reviews with complex content should fall through to LLM."""

    def test_text_with_complaint_keyword(self):
        """Text containing complaint keyword should miss cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=5,
            channel="review",
            text="Хороший товар, но размер маломерит немного",
        ))
        assert result is None

    def test_text_with_defect_keyword(self):
        """Text mentioning defect should miss cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=4,
            channel="review",
            text="Всё хорошо, однако есть небольшой дефект на ткани",
        ))
        assert result is None

    def test_long_text_bypasses_cache(self):
        """Text longer than threshold should miss cache."""
        long_text = "Отличный товар! " * 20  # well over 100 chars
        assert len(long_text) > _SIMPLE_TEXT_MAX_LEN
        result = _run(get_cached_response(
            intent="thanks",
            rating=5,
            channel="review",
            text=long_text,
        ))
        assert result is None

    def test_text_with_return_keyword(self):
        """Text mentioning return should miss cache."""
        result = _run(get_cached_response(
            intent="thanks",
            rating=4,
            channel="review",
            text="Хороший, но пришлось оформить возврат из-за размера",
        ))
        assert result is None


# ---------------------------------------------------------------------------
# Test: template quality
# ---------------------------------------------------------------------------

class TestTemplateQuality:
    """Templates should be valid, non-empty, and pass guardrails."""

    def test_positive_templates_not_empty(self):
        """All positive templates should be non-empty strings."""
        for t in POSITIVE_REVIEW_TEMPLATES:
            assert isinstance(t, str)
            assert len(t) >= 20, f"Template too short: {t!r}"

    def test_thanks_chat_templates_not_empty(self):
        """All chat thanks templates should be non-empty strings."""
        for t in THANKS_CHAT_TEMPLATES:
            assert isinstance(t, str)
            assert len(t) >= 10, f"Template too short: {t!r}"

    def test_templates_no_banned_phrases(self):
        """Templates should not contain any banned phrases."""
        from app.services.guardrails import check_banned_phrases

        for t in POSITIVE_REVIEW_TEMPLATES + THANKS_CHAT_TEMPLATES:
            violations = check_banned_phrases(t)
            assert violations == [], (
                f"Template contains banned phrase: {violations} in {t!r}"
            )

    def test_templates_within_length_limit(self):
        """Templates should not exceed the review reply max length."""
        from app.services.guardrails import REPLY_MAX_LENGTH_REVIEW

        for t in POSITIVE_REVIEW_TEMPLATES:
            assert len(t) <= REPLY_MAX_LENGTH_REVIEW, (
                f"Template too long ({len(t)} > {REPLY_MAX_LENGTH_REVIEW}): {t!r}"
            )

    def test_templates_no_ai_mentions(self):
        """Templates must never mention AI/bot/GPT."""
        ai_keywords = ["ИИ", "бот", "GPT", "нейросеть", "автоматический"]
        for t in POSITIVE_REVIEW_TEMPLATES + THANKS_CHAT_TEMPLATES:
            lower = t.lower()
            for kw in ai_keywords:
                assert kw.lower() not in lower, (
                    f"Template mentions AI ({kw!r}): {t!r}"
                )


# ---------------------------------------------------------------------------
# Test: random selection variety
# ---------------------------------------------------------------------------

class TestRandomSelection:
    """Random selection should produce variety, not always the same response."""

    def test_variety_over_multiple_calls(self):
        """Multiple cache hits should return different templates."""
        results = set()
        for _ in range(50):
            result = _run(get_cached_response(
                intent="thanks",
                rating=5,
                channel="review",
                text="Супер!",
            ))
            assert result is not None
            results.add(result)

        # With 10 templates and 50 draws, we should get at least 3 different ones
        assert len(results) >= 3, (
            f"Expected variety but got only {len(results)} unique templates in 50 draws"
        )

    def test_fast_positive_response_variety(self):
        """get_fast_positive_response should return variety."""
        results = set()
        for _ in range(50):
            result = _run(get_fast_positive_response())
            assert result is not None
            assert isinstance(result, str)
            results.add(result)

        assert len(results) >= 3


# ---------------------------------------------------------------------------
# Test: internal helper _has_complex_content
# ---------------------------------------------------------------------------

class TestComplexContentDetection:
    """Test the _has_complex_content helper."""

    def test_empty_text(self):
        assert _has_complex_content("") is False

    def test_simple_positive(self):
        assert _has_complex_content("Отличный товар!") is False

    def test_complaint_keyword(self):
        assert _has_complex_content("Хороший, но маломерит") is True

    def test_defect_keyword(self):
        assert _has_complex_content("Есть дефект") is True

    def test_return_keyword(self):
        assert _has_complex_content("Оформил возврат") is True

    def test_problem_keyword(self):
        assert _has_complex_content("Есть проблема с застёжкой") is True

    def test_case_insensitive(self):
        assert _has_complex_content("БРАК!!!") is True
