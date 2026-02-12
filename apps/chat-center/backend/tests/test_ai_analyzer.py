"""
Unit tests for AI Analyzer service.

Tests pure functions and methods that don't require LLM or database:
- extract_first_name() — name extraction from Russian FIO
- _apply_guardrails() — banned phrases, greeting normalization, truncation
- _check_escalation_keywords() — escalation detection
- _calculate_sla_priority() — SLA priority calculation
- _fallback_analysis() — keyword-based fallback
- _format_messages() — message formatting for prompt

Run with: pytest tests/test_ai_analyzer.py -v
"""
import os
import pytest

# Set required env vars BEFORE importing app modules (Settings needs ENCRYPTION_KEY)
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ai_analyzer.db")

from app.services.ai_analyzer import (
    extract_first_name,
    AIAnalyzer,
    SLA_PRIORITIES,
    BANNED_PHRASES,
    ESCALATION_KEYWORDS,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def analyzer():
    """AIAnalyzer instance with dummy API key (no real LLM calls)."""
    return AIAnalyzer(api_key="test-key", base_url="http://test")


# ─── extract_first_name ─────────────────────────────────────────────────────

class TestExtractFirstName:
    """Tests for extract_first_name() — Russian FIO name extraction."""

    def test_fio_extracts_first_name(self):
        """'Исакович Анна Витальевна' → 'Анна'"""
        assert extract_first_name("Исакович Анна Витальевна") == "Анна"

    def test_surname_name_extracts_name(self):
        """'Иванов Олег' → 'Олег'"""
        assert extract_first_name("Иванов Олег") == "Олег"

    def test_single_first_name(self):
        """'Олег' → 'Олег' (doesn't look like a surname)"""
        assert extract_first_name("Олег") == "Олег"

    def test_single_surname_ov(self):
        """'Иванов' → None (surname suffix -ов)"""
        assert extract_first_name("Иванов") is None

    def test_single_surname_ova(self):
        """'Иванова' → None (surname suffix -ова)"""
        assert extract_first_name("Иванова") is None

    def test_single_surname_ko(self):
        """'Курченко' → None (surname suffix -ко)"""
        assert extract_first_name("Курченко") is None

    def test_single_surname_enko(self):
        """'Тимошенко' → None (surname suffix -енко)"""
        assert extract_first_name("Тимошенко") is None

    def test_single_surname_ich(self):
        """'Петрович' → None (surname suffix -ич)"""
        assert extract_first_name("Петрович") is None

    def test_single_surname_skiy(self):
        """'Маяковский' → None (surname suffix -ский)"""
        assert extract_first_name("Маяковский") is None

    def test_single_surname_skaya(self):
        """'Маяковская' → None (surname suffix -ская)"""
        assert extract_first_name("Маяковская") is None

    def test_single_surname_chuk(self):
        """'Кравчук' → None (surname suffix -чук)"""
        assert extract_first_name("Кравчук") is None

    def test_none_input(self):
        """None → None"""
        assert extract_first_name(None) is None

    def test_empty_string(self):
        """'' → None"""
        assert extract_first_name("") is None

    def test_whitespace_only(self):
        """'   ' → None"""
        assert extract_first_name("   ") is None

    def test_short_word_not_surname(self):
        """'Ян' — too short to be a surname (suffix 'ин' but len <= suffix+1)"""
        assert extract_first_name("Ян") == "Ян"

    def test_latin_name(self):
        """'John' → 'John' (no Russian surname suffixes)"""
        assert extract_first_name("John") == "John"


# ─── _apply_guardrails ──────────────────────────────────────────────────────

class TestApplyGuardrails:
    """Tests for AIAnalyzer._apply_guardrails() — banned phrases + greeting normalization."""

    def test_adds_greeting_with_first_name(self, analyzer):
        """Adds personalized greeting when customer name has first name."""
        result = analyzer._apply_guardrails("Проверили заказ.", "Иванов Олег")
        assert result.startswith("Олег, здравствуйте!")
        assert "Проверили заказ." in result

    def test_adds_generic_greeting_for_surname_only(self, analyzer):
        """Adds generic greeting when only surname is given."""
        result = analyzer._apply_guardrails("Проверили заказ.", "Курченко")
        assert result.startswith("Здравствуйте!")
        assert "Проверили заказ." in result

    def test_adds_generic_greeting_when_no_name(self, analyzer):
        """Adds generic greeting when no customer name."""
        result = analyzer._apply_guardrails("Проверили заказ.", None)
        assert result.startswith("Здравствуйте!")

    def test_strips_existing_greeting_and_re_adds(self, analyzer):
        """Strips LLM-generated greeting and re-adds with correct name."""
        result = analyzer._apply_guardrails(
            "Курченко, здравствуйте! Проверили заказ.",
            "Курченко Анна"
        )
        assert result.startswith("Анна, здравствуйте!")
        # Should NOT have double greeting
        assert result.count("здравствуйте") == 1

    def test_strips_dobryj_den(self, analyzer):
        """Strips 'Добрый день!' greeting and re-adds standardized."""
        result = analyzer._apply_guardrails(
            "Добрый день! Проверили заказ.",
            "Сидоров Пётр"
        )
        assert result.startswith("Пётр, здравствуйте!")
        assert "Добрый день" not in result

    def test_replaces_banned_phrase_vernyom_dengi(self, analyzer):
        """'вернём деньги' replaced with 'Оформите возврат через ЛК WB'."""
        result = analyzer._apply_guardrails(
            "Мы вернём деньги в течение 3 дней.", None
        )
        assert "вернём деньги" not in result.lower()
        assert "Оформите возврат через ЛК WB" in result

    def test_replaces_banned_phrase_garantiruem(self, analyzer):
        """'гарантируем замену' replaced."""
        result = analyzer._apply_guardrails(
            "Мы гарантируем замену товара.", None
        )
        assert "гарантируем замену" not in result.lower()

    def test_removes_blame_phrases(self, analyzer):
        """Blame phrases like 'вы неправильно' are removed (no replacement)."""
        result = analyzer._apply_guardrails(
            "Вы неправильно установили прибор. Проверьте инструкцию.", None
        )
        assert "неправильно" not in result.lower()

    def test_removes_bot_mentions(self, analyzer):
        """AI/bot mentions are removed."""
        result = analyzer._apply_guardrails(
            "Наш ИИ проанализировал проблему. Вот решение.", None
        )
        assert "ИИ" not in result

    def test_truncates_long_text(self, analyzer):
        """Text over 300 chars is truncated."""
        long_text = "Текст. " * 100  # ~700 chars
        result = analyzer._apply_guardrails(long_text, None)
        assert len(result) <= 300

    def test_truncates_at_sentence_boundary(self, analyzer):
        """Long text truncates at sentence boundary when possible."""
        # Create text with clear sentence boundaries
        text = "Первое предложение. " * 10 + "Конец предложения."  # ~220 chars
        text += " Ещё текст который должен быть обрезан. " * 5
        result = analyzer._apply_guardrails(text, None)
        if len(result) > 10:  # Sanity check
            # Should end with period or "..."
            assert result.endswith(".") or result.endswith("...")

    def test_empty_text_returns_greeting(self, analyzer):
        """Empty text returns just the greeting."""
        result = analyzer._apply_guardrails("", "Иванов Олег")
        # Empty text with guardrails returns None or greeting
        # Actually _apply_guardrails checks `if not text: return text`
        assert result == ""

    def test_replaces_internal_jargon(self, analyzer):
        """Internal jargon like 'FBO' replaced with 'склад WB'."""
        result = analyzer._apply_guardrails(
            "Товар на FBO складе.", None
        )
        assert "FBO" not in result
        assert "склад WB" in result


# ─── _check_escalation_keywords ─────────────────────────────────────────────

class TestCheckEscalation:
    """Tests for AIAnalyzer._check_escalation_keywords()."""

    def test_medical_keyword_detected(self, analyzer):
        """'аллергия' triggers escalation."""
        messages = [
            {"text": "У ребёнка началась аллергия после использования!", "author_type": "buyer"}
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is not None
        assert "аллергия" in result
        assert "medical" in result

    def test_legal_keyword_detected(self, analyzer):
        """'суд' triggers escalation."""
        messages = [
            {"text": "Буду обращаться в суд!", "author_type": "buyer"}
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is not None
        assert "суд" in result

    def test_counterfeit_keyword_detected(self, analyzer):
        """'подделка' triggers escalation."""
        messages = [
            {"text": "Это явная подделка, не оригинал!", "author_type": "buyer"}
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is not None
        assert "подделка" in result

    def test_no_escalation_for_normal_messages(self, analyzer):
        """Normal messages don't trigger escalation."""
        messages = [
            {"text": "Когда доставят мой заказ?", "author_type": "buyer"}
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is None

    def test_ignores_seller_messages(self, analyzer):
        """Only buyer messages are checked for escalation."""
        messages = [
            {"text": "аллергия может быть вызвана", "author_type": "seller"},
            {"text": "Спасибо за ответ", "author_type": "buyer"}
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is None

    def test_multiple_messages_combined(self, analyzer):
        """Keywords can be in any buyer message."""
        messages = [
            {"text": "Товар пришёл странный", "author_type": "buyer"},
            {"text": "Думаю это подделка", "author_type": "buyer"},
        ]
        result = analyzer._check_escalation_keywords(messages)
        assert result is not None


# ─── _calculate_sla_priority ─────────────────────────────────────────────────

class TestCalculateSLAPriority:
    """Tests for AIAnalyzer._calculate_sla_priority()."""

    def test_defect_is_urgent(self, analyzer):
        """defect_not_working → urgent priority."""
        result = analyzer._calculate_sla_priority(
            "defect_not_working", "normal",
            [{"text": "Сломалось", "author_type": "buyer"}]
        )
        assert result == "urgent"

    def test_wrong_item_is_urgent(self, analyzer):
        """wrong_item → urgent priority."""
        result = analyzer._calculate_sla_priority(
            "wrong_item", "normal",
            [{"text": "Не тот товар", "author_type": "buyer"}]
        )
        assert result == "urgent"

    def test_pre_purchase_is_high(self, analyzer):
        """sizing_fit → high priority (potential sale)."""
        result = analyzer._calculate_sla_priority(
            "sizing_fit", "normal",
            [{"text": "Какой размер?", "author_type": "buyer"}]
        )
        assert result == "high"

    def test_thanks_is_low(self, analyzer):
        """thanks → low priority."""
        result = analyzer._calculate_sla_priority(
            "thanks", "normal",
            [{"text": "Спасибо!", "author_type": "buyer"}]
        )
        assert result == "low"

    def test_escalation_with_3_buyer_messages(self, analyzer):
        """3+ buyer messages escalates normal → high."""
        messages = [
            {"text": "Где заказ?", "author_type": "buyer"},
            {"text": "Ответьте!", "author_type": "buyer"},
            {"text": "Ну когда уже?", "author_type": "buyer"},
        ]
        result = analyzer._calculate_sla_priority("delivery_status", "normal", messages)
        assert result == "high"

    def test_escalation_with_3_messages_high_to_urgent(self, analyzer):
        """3+ buyer messages escalates high → urgent."""
        messages = [
            {"text": "Прислали не то", "author_type": "buyer"},
            {"text": "Это безобразие", "author_type": "buyer"},
            {"text": "Жду замену!!!", "author_type": "buyer"},
        ]
        result = analyzer._calculate_sla_priority("cancel_request", "normal", messages)
        assert result == "urgent"  # high (base) → urgent (3 msgs)

    def test_caps_escalation(self, analyzer):
        """Messages with >50% caps escalate priority."""
        messages = [
            {"text": "ГДЕ МОЙ ЗАКАЗ ВЕРНИТЕ ДЕНЬГИ", "author_type": "buyer"},
        ]
        result = analyzer._calculate_sla_priority("delivery_status", "normal", messages)
        assert result == "high"

    def test_exclamation_escalation(self, analyzer):
        """Messages with 3+ exclamation marks escalate priority."""
        messages = [
            {"text": "Это ужас!!! Верните деньги!!!", "author_type": "buyer"},
        ]
        result = analyzer._calculate_sla_priority("delivery_status", "normal", messages)
        assert result == "high"

    def test_critical_urgency_override(self, analyzer):
        """Critical urgency from LLM overrides to urgent."""
        result = analyzer._calculate_sla_priority(
            "usage_howto", "critical",
            [{"text": "Как включить?", "author_type": "buyer"}]
        )
        assert result == "urgent"

    def test_seller_messages_not_counted_for_escalation(self, analyzer):
        """Seller messages don't count toward 3-message escalation."""
        messages = [
            {"text": "Вопрос", "author_type": "buyer"},
            {"text": "Ответ продавца", "author_type": "seller"},
            {"text": "Ответ продавца 2", "author_type": "seller"},
            {"text": "Ещё вопрос", "author_type": "buyer"},
        ]
        result = analyzer._calculate_sla_priority("usage_howto", "normal", messages)
        # Only 2 buyer messages — no escalation
        assert result == "low"

    def test_all_intents_have_sla_priority(self):
        """Every intent in SLA_PRIORITIES has a valid priority."""
        valid_priorities = {"urgent", "high", "normal", "low"}
        for intent, priority in SLA_PRIORITIES.items():
            assert priority in valid_priorities, f"{intent} has invalid priority: {priority}"


# ─── _fallback_analysis ──────────────────────────────────────────────────────

class TestFallbackAnalysis:
    """Tests for AIAnalyzer._fallback_analysis() — keyword-based fallback."""

    def test_delivery_keywords(self, analyzer):
        """'где заказ' → intent delivery_status."""
        messages = [{"text": "Где заказ? Когда придёт?", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, "Олег")
        assert result["intent"] == "delivery_status"

    def test_defect_keywords(self, analyzer):
        """'не работает' → intent defect_not_working."""
        messages = [{"text": "Кран не работает, брак!", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "defect_not_working"

    def test_wrong_item_keywords(self, analyzer):
        """'прислали не то' → intent wrong_item."""
        messages = [{"text": "Прислали не то что заказывал", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "wrong_item"

    def test_return_keywords(self, analyzer):
        """'возврат' → intent refund_exchange."""
        messages = [{"text": "Хочу оформить возврат", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "refund_exchange"

    def test_cancel_keywords(self, analyzer):
        """'отменить' → intent cancel_request."""
        messages = [{"text": "Хочу отменить заказ", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "cancel_request"

    def test_thanks_keywords(self, analyzer):
        """'спасибо' → intent thanks."""
        messages = [{"text": "Спасибо за помощь!", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "thanks"

    def test_sizing_keywords(self, analyzer):
        """'какой размер' → intent sizing_fit (pre-purchase, HIGH priority)."""
        messages = [{"text": "Подскажите, какой размер выбрать?", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "sizing_fit"
        assert result["sla_priority"] == "high"

    def test_availability_keywords(self, analyzer):
        """'есть в наличии' → intent availability."""
        messages = [{"text": "Есть в наличии чёрного цвета?", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "availability"

    def test_negative_sentiment(self, analyzer):
        """'ужас' → negative sentiment."""
        messages = [{"text": "Ужас, товар сломался!", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["sentiment"] == "negative"

    def test_positive_sentiment(self, analyzer):
        """'отлично' → positive sentiment."""
        messages = [{"text": "Отлично, всё работает!", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["sentiment"] == "positive"

    def test_fallback_has_recommendation(self, analyzer):
        """Fallback always returns a recommendation string."""
        messages = [{"text": "Вопрос", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert result["recommendation"] is not None
        assert len(result["recommendation"]) > 0

    def test_fallback_recommendation_uses_first_name(self, analyzer):
        """Fallback recommendation includes first name greeting."""
        messages = [{"text": "Где заказ?", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, "Иванов Олег")
        assert "Олег, здравствуйте!" in result["recommendation"]

    def test_fallback_recommendation_generic_for_surname(self, analyzer):
        """Fallback recommendation uses generic greeting for surname-only."""
        messages = [{"text": "Где заказ?", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, "Курченко")
        assert result["recommendation"].startswith("Здравствуйте!")

    def test_fallback_has_all_required_fields(self, analyzer):
        """Fallback response has all required analysis fields."""
        messages = [{"text": "Вопрос", "author_type": "buyer"}]
        result = analyzer._fallback_analysis(messages, None)
        assert "intent" in result
        assert "sentiment" in result
        assert "urgency" in result
        assert "categories" in result
        assert "recommendation" in result
        assert "needs_escalation" in result
        assert "sla_priority" in result
        assert "analyzed_at" in result

    def test_fallback_ignores_seller_messages(self, analyzer):
        """Fallback intent detection only looks at buyer messages."""
        messages = [
            {"text": "Товар не работает, брак!", "author_type": "seller"},
            {"text": "Спасибо за информацию", "author_type": "buyer"},
        ]
        result = analyzer._fallback_analysis(messages, None)
        assert result["intent"] == "thanks"


# ─── _format_messages ────────────────────────────────────────────────────────

class TestFormatMessages:
    """Tests for AIAnalyzer._format_messages()."""

    def test_basic_formatting(self, analyzer):
        """Messages formatted as '[time] Author: text'."""
        messages = [
            {"text": "Привет", "author_type": "buyer", "created_at": "2026-02-10 10:00"},
            {"text": "Здравствуйте!", "author_type": "seller", "created_at": "2026-02-10 10:05"},
        ]
        result = analyzer._format_messages(messages, "Олег")
        assert "Олег: Привет" in result
        assert "Продавец: Здравствуйте!" in result

    def test_buyer_name_used(self, analyzer):
        """Customer name used instead of 'Покупатель'."""
        messages = [
            {"text": "Вопрос", "author_type": "buyer", "created_at": "2026-02-10 10:00"},
        ]
        result = analyzer._format_messages(messages, "Анна")
        assert "Анна: Вопрос" in result

    def test_buyer_default_name(self, analyzer):
        """'Покупатель' used when no customer name."""
        messages = [
            {"text": "Вопрос", "author_type": "buyer", "created_at": "2026-02-10 10:00"},
        ]
        result = analyzer._format_messages(messages, None)
        assert "Покупатель: Вопрос" in result

    def test_limits_to_10_messages(self, analyzer):
        """Only last 10 messages are included."""
        messages = [
            {"text": f"Сообщение {i}", "author_type": "buyer", "created_at": f"2026-02-{10+i} 10:00"}
            for i in range(15)
        ]
        result = analyzer._format_messages(messages, None)
        # Should NOT contain first 5 messages
        assert "Сообщение 0" not in result
        assert "Сообщение 4" not in result
        # Should contain last 10
        assert "Сообщение 5" in result
        assert "Сообщение 14" in result

    def test_skips_empty_messages(self, analyzer):
        """Empty messages are skipped."""
        messages = [
            {"text": "", "author_type": "buyer", "created_at": "2026-02-10 10:00"},
            {"text": "   ", "author_type": "buyer", "created_at": "2026-02-10 10:01"},
            {"text": "Реальное сообщение", "author_type": "buyer", "created_at": "2026-02-10 10:02"},
        ]
        result = analyzer._format_messages(messages, None)
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) == 1
        assert "Реальное сообщение" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
