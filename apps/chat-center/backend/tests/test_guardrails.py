"""Tests for channel-specific guardrails service."""

import pytest

from app.services.guardrails import (
    BANNED_PHRASES_BLAME,
    BANNED_PHRASES_COMMON,
    BANNED_PHRASES_DISMISSIVE,
    BANNED_PHRASES_PROMISES,
    RETURN_TRIGGER_WORDS,
    apply_chat_guardrails,
    apply_guardrails,
    apply_question_guardrails,
    apply_review_guardrails,
    check_banned_phrases,
    check_return_mention_without_trigger,
    has_return_trigger,
    validate_reply_text,
)


# ---- check_banned_phrases ----

class TestCheckBannedPhrases:
    def test_empty_text_returns_empty(self):
        assert check_banned_phrases("") == []
        assert check_banned_phrases(None) == []

    def test_clean_text_no_violations(self):
        result = check_banned_phrases("Здравствуйте! Спасибо за отзыв.")
        assert result == []

    def test_ai_mention_detected(self):
        for phrase in BANNED_PHRASES_COMMON:
            text = f"Этот ответ сгенерирован {phrase} для вас"
            result = check_banned_phrases(text)
            categories = [v["category"] for v in result]
            assert "ai_mention" in categories, f"Failed to detect: {phrase}"

    def test_promise_detected(self):
        for phrase in BANNED_PHRASES_PROMISES:
            text = f"Мы {phrase} в ближайшее время"
            result = check_banned_phrases(text)
            categories = [v["category"] for v in result]
            assert "promise" in categories, f"Failed to detect: {phrase}"

    def test_blame_detected(self):
        for phrase in BANNED_PHRASES_BLAME:
            text = f"К сожалению, {phrase} использовали товар"
            result = check_banned_phrases(text)
            categories = [v["category"] for v in result]
            assert "blame" in categories, f"Failed to detect: {phrase}"

    def test_dismissive_detected(self):
        for phrase in BANNED_PHRASES_DISMISSIVE:
            text = f"Пожалуйста, {phrase} маркетплейса"
            result = check_banned_phrases(text)
            categories = [v["category"] for v in result]
            assert "dismissive" in categories, f"Failed to detect: {phrase}"

    def test_case_insensitive(self):
        result = check_banned_phrases("Это GPT ответ")
        assert len(result) >= 1
        result2 = check_banned_phrases("Это gpt ответ")
        assert len(result2) >= 1

    def test_custom_phrase_lists(self):
        result = check_banned_phrases(
            "Мы гарантируем возврат",
            phrase_lists={"promise": ["гарантируем возврат"]},
        )
        assert len(result) == 1
        assert result[0]["category"] == "promise"

    def test_partial_word_no_false_positive_bot(self):
        """'бот' should not match inside 'работа' or 'суббота'."""
        result = check_banned_phrases("Отличная работа над товаром")
        bot_violations = [v for v in result if v["phrase"] == "бот"]
        assert bot_violations == [], "False positive: 'бот' matched inside 'работа'"

    def test_partial_word_no_false_positive_ii(self):
        """'ИИ' should not match inside regular words."""
        result = check_banned_phrases("Принимаем меры")
        ii_violations = [v for v in result if v["phrase"] == "ИИ"]
        assert ii_violations == [], "False positive: 'ИИ' matched inside a word"

    def test_multiple_violations(self):
        text = "Этот бот гарантируем возврат, вы неправильно использовали"
        result = check_banned_phrases(text)
        assert len(result) >= 3
        categories = {v["category"] for v in result}
        assert "ai_mention" in categories
        assert "promise" in categories
        assert "blame" in categories


# ---- has_return_trigger ----

class TestHasReturnTrigger:
    def test_empty_text(self):
        assert has_return_trigger("") is False
        assert has_return_trigger(None) is False

    def test_all_triggers(self):
        for word in RETURN_TRIGGER_WORDS:
            assert has_return_trigger(f"Хочу {word} товара") is True, f"Missed: {word}"

    def test_no_trigger(self):
        assert has_return_trigger("Товар не работает") is False

    def test_case_insensitive(self):
        assert has_return_trigger("Хочу ВОЗВРАТ") is True
        assert has_return_trigger("Хочу Вернуть") is True


# ---- check_return_mention_without_trigger ----

class TestCheckReturnMentionWithoutTrigger:
    def test_no_mention_no_trigger(self):
        assert check_return_mention_without_trigger(
            "Спасибо за отзыв!", "Товар плохой"
        ) is False

    def test_mention_with_trigger(self):
        """If customer asked for return, seller can mention it."""
        assert check_return_mention_without_trigger(
            "Оформите возврат через ЛК WB", "Хочу вернуть товар"
        ) is False

    def test_mention_without_trigger(self):
        """Seller mentions return but customer did not ask."""
        assert check_return_mention_without_trigger(
            "Вы можете оформить возврат", "Товар не работает"
        ) is True

    def test_empty_reply(self):
        assert check_return_mention_without_trigger("", "Товар плохой") is False

    def test_empty_customer_text(self):
        assert check_return_mention_without_trigger(
            "Оформите возврат", ""
        ) is True


# ---- apply_review_guardrails ----

class TestApplyReviewGuardrails:
    def test_clean_draft(self):
        text, warnings = apply_review_guardrails(
            "Здравствуйте! Спасибо за отзыв. Рады помочь!",
            customer_text="Отличный товар",
        )
        error_warnings = [w for w in warnings if w["severity"] == "error"]
        assert error_warnings == []

    def test_detects_ai_mention(self):
        text, warnings = apply_review_guardrails("Это ответ нейросеть генерирует")
        assert any(w["type"] == "banned_phrase" for w in warnings)

    def test_detects_promise(self):
        text, warnings = apply_review_guardrails("Мы гарантируем возврат товара")
        assert any(w["type"] == "banned_phrase" and w["category"] == "promise" for w in warnings)

    def test_detects_unsolicited_return(self):
        text, warnings = apply_review_guardrails(
            "Оформите возврат через ЛК WB",
            customer_text="Товар не понравился",
        )
        assert any(w["type"] == "unsolicited_return" for w in warnings)

    def test_return_allowed_when_triggered(self):
        text, warnings = apply_review_guardrails(
            "Оформите возврат через ЛК WB",
            customer_text="Хочу вернуть товар",
        )
        unsolicited = [w for w in warnings if w["type"] == "unsolicited_return"]
        assert unsolicited == []

    def test_too_long(self):
        long_text = "А" * 501  # REPLY_MAX_LENGTH_REVIEW = 500
        text, warnings = apply_review_guardrails(long_text)
        assert any(w["type"] == "too_long" for w in warnings)

    def test_too_short(self):
        text, warnings = apply_review_guardrails("Ок")
        assert any(w["type"] == "too_short" for w in warnings)

    def test_empty_text(self):
        text, warnings = apply_review_guardrails("")
        assert warnings == []
        assert text == ""

    def test_none_text(self):
        text, warnings = apply_review_guardrails(None)
        assert warnings == []

    def test_text_unchanged(self):
        """Guardrails should NOT modify the text at draft stage."""
        original = "Мы гарантируем возврат, бот сгенерировал ответ"
        text, warnings = apply_review_guardrails(original)
        assert text == original
        assert len(warnings) > 0


# ---- apply_question_guardrails ----

class TestApplyQuestionGuardrails:
    def test_same_as_review(self):
        """Questions are public, same strictness as reviews."""
        text_r, warnings_r = apply_review_guardrails("Мы бот и гарантируем возврат")
        text_q, warnings_q = apply_question_guardrails("Мы бот и гарантируем возврат")
        assert len(warnings_r) == len(warnings_q)


# ---- apply_chat_guardrails ----

class TestApplyChatGuardrails:
    def test_ai_mention_still_banned(self):
        text, warnings = apply_chat_guardrails("Это автоматический ответ от ИИ")
        error_warnings = [w for w in warnings if w["severity"] == "error"]
        assert len(error_warnings) >= 1

    def test_promises_allowed_in_chat(self):
        """Private chat: promises are not checked."""
        text, warnings = apply_chat_guardrails("Мы гарантируем возврат")
        error_warnings = [w for w in warnings if w["severity"] == "error"]
        assert error_warnings == []

    def test_dismissive_allowed_in_chat(self):
        text, warnings = apply_chat_guardrails("Обратитесь в поддержку маркетплейса")
        error_warnings = [w for w in warnings if w["severity"] == "error"]
        assert error_warnings == []

    def test_blame_is_soft_warning(self):
        text, warnings = apply_chat_guardrails("Вы неправильно собрали товар")
        blame_warnings = [w for w in warnings if w["category"] == "blame"]
        assert len(blame_warnings) >= 1
        assert all(w["severity"] == "warning" for w in blame_warnings)

    def test_clean_chat(self):
        text, warnings = apply_chat_guardrails("Здравствуйте! Чем могу помочь?")
        assert warnings == []


# ---- apply_guardrails (unified) ----

class TestApplyGuardrails:
    def test_routes_to_review(self):
        _, w1 = apply_guardrails("бот", "review")
        _, w2 = apply_review_guardrails("бот")
        assert len(w1) == len(w2)

    def test_routes_to_question(self):
        _, w1 = apply_guardrails("бот", "question")
        _, w2 = apply_question_guardrails("бот")
        assert len(w1) == len(w2)

    def test_routes_to_chat(self):
        _, w1 = apply_guardrails("бот", "chat")
        _, w2 = apply_chat_guardrails("бот")
        assert len(w1) == len(w2)

    def test_unknown_channel_uses_review(self):
        _, w1 = apply_guardrails("бот", "unknown_channel")
        _, w2 = apply_review_guardrails("бот")
        assert len(w1) == len(w2)


# ---- validate_reply_text (blocking) ----

class TestValidateReplyText:
    def test_valid_text(self):
        result = validate_reply_text(
            "Здравствуйте! Спасибо за отзыв и обратную связь.",
            "review",
        )
        assert result["valid"] is True
        assert result["violations"] == []

    def test_empty_text_blocked(self):
        result = validate_reply_text("", "review")
        assert result["valid"] is False
        assert any(v["type"] == "empty_text" for v in result["violations"])

    def test_none_text_blocked(self):
        result = validate_reply_text(None, "review")
        assert result["valid"] is False

    def test_whitespace_only_blocked(self):
        result = validate_reply_text("   ", "review")
        assert result["valid"] is False

    def test_ai_mention_blocked_review(self):
        result = validate_reply_text("Этот ChatGPT ответ для вас", "review")
        assert result["valid"] is False
        assert any(v["type"] == "banned_phrase" for v in result["violations"])

    def test_ai_mention_blocked_chat(self):
        """Even in chat, AI mentions are blocked."""
        result = validate_reply_text("Этот ChatGPT ответ для вас", "chat")
        assert result["valid"] is False

    def test_promise_blocked_review(self):
        result = validate_reply_text("Мы гарантируем возврат", "review")
        assert result["valid"] is False

    def test_promise_ok_in_chat(self):
        """Promises are not blocked in private chat."""
        result = validate_reply_text("Мы гарантируем возврат товара", "chat")
        assert result["valid"] is True

    def test_unsolicited_return_blocked(self):
        result = validate_reply_text(
            "Оформите возврат через ЛК WB",
            "review",
            customer_text="Товар бракованный",
        )
        assert result["valid"] is False
        assert any(v["type"] == "unsolicited_return" for v in result["violations"])

    def test_return_with_trigger_ok(self):
        result = validate_reply_text(
            "Оформите возврат через ЛК WB как не соответствует описанию",
            "review",
            customer_text="Хочу вернуть товар",
        )
        assert result["valid"] is True

    def test_warnings_in_result(self):
        """Short text should produce a warning (not blocking)."""
        result = validate_reply_text("Ок", "review")
        assert any(w["type"] == "too_short" for w in result["warnings"])

    def test_length_warning_not_blocking(self):
        """Length issues produce warnings, not blocking violations."""
        short_text = "Спасибо!"
        result = validate_reply_text(short_text, "review")
        # Short text is a warning, not a violation
        length_violations = [v for v in result["violations"] if v.get("type") == "too_short"]
        assert length_violations == []
