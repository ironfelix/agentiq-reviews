"""Unit tests for LLM analyzer module."""
import pytest
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))

from llm_analyzer import (
    sanitize_reply,
    _trunc,
    _apply_guardrails,
    _apply_communication_guardrails,
    GUARDRAILS,
)


@pytest.mark.unit
class TestGuardrails:
    """Tests for LLM output guardrails."""

    def test_sanitize_reply_banned_phrases(self):
        """Test banned phrase replacement in replies."""
        text = "Мы вернём деньги в течение 3 дней."
        result = sanitize_reply(text)
        assert "вернём деньги" not in result.lower()
        assert "рассмотрим ваш вопрос" in result.lower()

    def test_sanitize_reply_multiple_banned_phrases(self):
        """Test multiple banned phrases."""
        text = "Вернём деньги и гарантируем замену. Обратитесь в поддержку."
        result = sanitize_reply(text)
        assert "вернём деньги" not in result.lower()
        assert "гарантируем замену" not in result.lower()
        assert "обратитесь в поддержку" not in result.lower()

    def test_sanitize_reply_blame_customer(self):
        """Test customer blame detection."""
        text = "Вы неправильно используете товар. Ваша вина."
        result = sanitize_reply(text)
        assert "вы неправильно" not in result.lower()
        assert "ваша вина" not in result.lower()

    def test_sanitize_reply_length_limit(self):
        """Test reply length limiting."""
        long_text = "Очень длинный текст. " * 50  # Much longer than 300 chars
        result = sanitize_reply(long_text)
        assert len(result) <= GUARDRAILS["reply_max_length"]

    def test_sanitize_reply_empty_input(self):
        """Test with empty input."""
        assert sanitize_reply("") == ""
        assert sanitize_reply("   ") == "   "

    def test_trunc_short_text(self):
        """Test truncation with short text."""
        text = "Short text"
        result = _trunc(text, 100)
        assert result == text

    def test_trunc_long_text(self):
        """Test truncation with long text."""
        text = "This is a very long text that needs to be truncated at word boundary"
        result = _trunc(text, 30)
        assert len(result) <= 32  # 30 + "…"
        assert result.endswith("…")
        assert not result.endswith(" …")

    def test_apply_guardrails_root_cause_type(self):
        """Test root cause type validation."""
        result = {
            "root_cause": {
                "type": "invalid_type",
                "explanation": ["Test"],
                "conclusion": "Test conclusion",
            },
            "strategy": {"title": "Test"},
            "actions": ["Action 1"],
            "reply": "Test reply",
        }
        sanitized = _apply_guardrails(result)
        assert sanitized["root_cause"]["type"] == GUARDRAILS["root_cause_default_type"]

    def test_apply_guardrails_valid_type(self):
        """Test with valid root cause type."""
        result = {
            "root_cause": {
                "type": "expectation_mismatch",
                "explanation": ["Test"],
                "conclusion": "Test",
            },
            "strategy": {"title": "Test"},
            "actions": ["Action 1"],
            "reply": "Test",
        }
        sanitized = _apply_guardrails(result)
        assert sanitized["root_cause"]["type"] == "expectation_mismatch"

    def test_apply_guardrails_explanation_limit(self):
        """Test explanation items limiting."""
        result = {
            "root_cause": {
                "type": "defect",
                "explanation": ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"],
                "conclusion": "Test",
            },
            "strategy": {"title": "Test"},
            "actions": [],
            "reply": "Test",
        }
        sanitized = _apply_guardrails(result)
        assert len(sanitized["root_cause"]["explanation"]) <= GUARDRAILS["explanation_max_items"]

    def test_apply_guardrails_actions_limit(self):
        """Test actions limiting."""
        result = {
            "root_cause": {"type": "defect", "explanation": [], "conclusion": "Test"},
            "strategy": {"title": "Test"},
            "actions": ["A1", "A2", "A3", "A4", "A5", "A6"],
            "reply": "Test",
        }
        sanitized = _apply_guardrails(result)
        assert len(sanitized["actions"]) <= GUARDRAILS["actions_max_count"]

    def test_apply_communication_guardrails_quality_score_clamp(self):
        """Test quality score clamping."""
        # Test too high
        result = {"quality_score": 15, "worst_responses": []}
        sanitized = _apply_communication_guardrails(result)
        assert sanitized["quality_score"] == 10

        # Test too low
        result = {"quality_score": -5, "worst_responses": []}
        sanitized = _apply_communication_guardrails(result)
        assert sanitized["quality_score"] == 1

        # Test valid
        result = {"quality_score": 7, "worst_responses": []}
        sanitized = _apply_communication_guardrails(result)
        assert sanitized["quality_score"] == 7

    def test_apply_communication_guardrails_ai_mentions(self):
        """Test AI/bot mention removal."""
        result = {
            "quality_score": 7,
            "verdict": "Продавец использует ИИ-ответы на все отзывы.",
            "buyer_perception": [
                "Видны ChatGPT ответы",
                "Нейросеть не понимает проблему",
            ],
            "worst_responses": [],
        }
        sanitized = _apply_communication_guardrails(result)

        assert "ии" not in sanitized["verdict"].lower()
        assert "chatgpt" not in str(sanitized["buyer_perception"]).lower()
        assert "нейросет" not in str(sanitized["buyer_perception"]).lower()

    def test_apply_communication_guardrails_return_without_request(self):
        """Test return suggestion without buyer request."""
        result = {
            "quality_score": 5,
            "worst_responses": [
                {
                    "review_text": "Товар не понравился",  # No return keywords
                    "recommendation": "Оформите возврат через ЛК WB.",
                }
            ],
        }
        sanitized = _apply_communication_guardrails(result)
        rec = sanitized["worst_responses"][0]["recommendation"]
        assert "возврат" not in rec.lower()

    def test_apply_communication_guardrails_return_with_request(self):
        """Test return suggestion when buyer requested it."""
        result = {
            "quality_score": 5,
            "worst_responses": [
                {
                    "review_text": "Хочу вернуть товар, не подошёл",
                    "recommendation": "Оформите возврат через ЛК WB.",
                }
            ],
        }
        sanitized = _apply_communication_guardrails(result)
        rec = sanitized["worst_responses"][0]["recommendation"]
        # Return suggestion is allowed because buyer asked
        assert rec  # Should not be empty

    def test_apply_communication_guardrails_array_limits(self):
        """Test array size limiting."""
        result = {
            "quality_score": 5,
            "worst_responses": [{"id": i} for i in range(10)],
            "hidden_risks": [{"id": i} for i in range(10)],
        }
        sanitized = _apply_communication_guardrails(result)
        assert len(sanitized["worst_responses"]) <= 5
        assert len(sanitized["hidden_risks"]) <= 5

    def test_apply_communication_guardrails_distribution_gap(self):
        """Test distribution gap filling."""
        result = {
            "quality_score": 7,
            "total_analyzed": 100,
            "distribution": {
                "harmful": 10,
                "risky": 20,
                "acceptable": 30,
                "good": 30,
                # Sum = 90, missing 10
            },
            "worst_responses": [],
        }
        sanitized = _apply_communication_guardrails(result)
        dist = sanitized["distribution"]
        total = dist["harmful"] + dist["risky"] + dist["acceptable"] + dist["good"]
        assert total == 100


@pytest.mark.unit
class TestGuardrailsEdgeCases:
    """Edge case tests for guardrails."""

    def test_sanitize_reply_case_insensitive(self):
        """Test case-insensitive banned phrase matching."""
        text = "ВЕРНЁМ ДЕНЬГИ В ТЕЧЕНИЕ 3 ДНЕЙ"
        result = sanitize_reply(text)
        assert "вернём деньги" not in result.lower()

    def test_sanitize_reply_partial_match(self):
        """Test that partial matches work."""
        text = "Мы вернем деньги быстро"  # No ё
        result = sanitize_reply(text)
        # Should still catch "вернем деньги" (variant without ё)
        assert "вернем деньги" not in result.lower() or "рассмотрим" in result.lower()

    def test_trunc_no_spaces(self):
        """Test truncation with text without spaces."""
        text = "a" * 100
        result = _trunc(text, 50)
        assert len(result) <= 51  # 50 + "…"

    def test_apply_guardrails_empty_lists(self):
        """Test with empty lists."""
        result = {
            "root_cause": {
                "type": "defect",
                "explanation": [],
                "conclusion": "",
            },
            "strategy": {"title": ""},
            "actions": [],
            "reply": "",
        }
        sanitized = _apply_guardrails(result)
        assert sanitized["root_cause"]["explanation"] == []
        assert sanitized["actions"] == []

    def test_apply_communication_guardrails_missing_fields(self):
        """Test with missing optional fields."""
        result = {
            "quality_score": 5,
        }
        sanitized = _apply_communication_guardrails(result)
        assert sanitized["quality_score"] == 5
        assert "worst_responses" in sanitized
        assert "hidden_risks" in sanitized
