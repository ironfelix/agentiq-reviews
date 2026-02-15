"""
Unit tests for AI Question Analyzer service (LLM intent fallback).

Tests the hybrid intent classification:
- Rule-based first (fast path) returns immediately for known intents
- LLM fallback called only for general_question
- LLM timeout -> falls back to general_question
- Invalid LLM response -> falls back to general_question
- Config flag ENABLE_LLM_INTENT controls LLM usage
- intent_detection_method stored in extra_data

Run with: pytest tests/test_ai_question_analyzer.py -v
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set required env vars BEFORE importing app modules (Settings needs ENCRYPTION_KEY)
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_ai_question.db")

from app.services.ai_question_analyzer import (
    VALID_INTENTS,
    classify_question_intent,
    classify_question_intent_llm,
)
from app.services.interaction_ingest import (
    _question_intent,
    _priority_for_question_with_intent,
)


# ---- Rule-based fast path ------------------------------------------------

class TestRuleBasedFastPath:
    """Rule-based detection should return immediately without LLM call."""

    @pytest.mark.asyncio
    async def test_sizing_fit_skips_llm(self):
        """'Какой размер подойдёт?' -> sizing_fit via rule-based, no LLM."""
        intent, method = await classify_question_intent(
            "Какой размер подойдёт при росте 170?",
            enable_llm=True,
        )
        assert intent == "sizing_fit"
        assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_availability_skips_llm(self):
        """'Когда будет в наличии?' -> availability_delivery via rule-based."""
        intent, method = await classify_question_intent(
            "Когда будет в наличии синий цвет?",
            enable_llm=True,
        )
        assert intent == "availability_delivery"
        assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_spec_compatibility_skips_llm(self):
        """'Из какого материала?' -> spec_compatibility via rule-based."""
        intent, method = await classify_question_intent(
            "Из какого материала сделан корпус?",
            enable_llm=True,
        )
        assert intent == "spec_compatibility"
        assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_compliance_safety_skips_llm(self):
        """'Есть сертификат?' -> compliance_safety via rule-based."""
        intent, method = await classify_question_intent(
            "Есть сертификат качества на этот товар?",
            enable_llm=True,
        )
        assert intent == "compliance_safety"
        assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_post_purchase_issue_skips_llm(self):
        """'Товар не работает' -> post_purchase_issue via rule-based."""
        intent, method = await classify_question_intent(
            "Товар не работает, что делать?",
            enable_llm=True,
        )
        assert intent == "post_purchase_issue"
        assert method == "rule_based"


# ---- LLM fallback behavior -----------------------------------------------

class TestLLMFallback:
    """LLM should be called only when rule-based returns general_question."""

    @pytest.mark.asyncio
    async def test_llm_called_for_general_question(self):
        """When rule-based returns general_question, LLM fallback is attempted."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            return_value="sizing_fit",
        ) as mock_llm:
            intent, method = await classify_question_intent(
                "Подскажите, на какую фигуру рассчитан этот фасон?",
                enable_llm=True,
            )
            mock_llm.assert_called_once()
            assert intent == "sizing_fit"
            assert method == "llm"

    @pytest.mark.asyncio
    async def test_llm_not_called_when_disabled(self):
        """When ENABLE_LLM_INTENT=false, LLM is never called."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
        ) as mock_llm:
            intent, method = await classify_question_intent(
                "Подскажите что-нибудь",
                enable_llm=False,
            )
            mock_llm.assert_not_called()
            assert intent == "general_question"
            assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_llm_returns_general_question(self):
        """When LLM also returns general_question, method is 'llm' because LLM was called."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            return_value="general_question",
        ):
            intent, method = await classify_question_intent(
                "Подскажите что-нибудь",
                enable_llm=True,
            )
            assert intent == "general_question"
            # LLM was called and returned general_question (a valid intent),
            # so method reflects that the LLM path was taken.
            assert method == "llm"


# ---- LLM failure resilience -----------------------------------------------

class TestLLMFailureResilience:
    """LLM failures must never block ingestion or crash."""

    @pytest.mark.asyncio
    async def test_llm_timeout_falls_back(self):
        """LLM timeout -> graceful fallback to general_question."""
        import httpx

        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timeout"),
        ):
            intent, method = await classify_question_intent(
                "Непонятный вопрос без ключевых слов",
                enable_llm=True,
            )
            assert intent == "general_question"
            assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_llm_returns_none_falls_back(self):
        """LLM returns None (e.g. invalid response) -> general_question."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            return_value=None,
        ):
            intent, method = await classify_question_intent(
                "Непонятный вопрос без ключевых слов",
                enable_llm=True,
            )
            assert intent == "general_question"
            assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_llm_invalid_intent_falls_back(self):
        """LLM returns invalid intent string -> general_question."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            return_value="totally_invalid_intent",
        ):
            intent, method = await classify_question_intent(
                "Непонятный вопрос без ключевых слов",
                enable_llm=True,
            )
            assert intent == "general_question"
            assert method == "rule_based"

    @pytest.mark.asyncio
    async def test_llm_exception_falls_back(self):
        """Any exception in LLM path -> graceful fallback."""
        with patch(
            "app.services.ai_question_analyzer.classify_question_intent_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("unexpected error"),
        ):
            intent, method = await classify_question_intent(
                "Какой-то вопрос",
                enable_llm=True,
            )
            assert intent == "general_question"
            assert method == "rule_based"


# ---- Priority recalculation with intent_override --------------------------

class TestPriorityWithIntentOverride:
    """_priority_for_question_with_intent should use intent_override when provided."""

    def test_override_changes_priority(self):
        """intent_override=compliance_safety -> urgent priority."""
        priority, intent, sla = _priority_for_question_with_intent(
            needs_response=True,
            question_text="Какой-то вопрос без ключевых слов",
            occurred_at=None,
            intent_override="compliance_safety",
        )
        assert intent == "compliance_safety"
        assert priority == "urgent"
        assert sla == 60

    def test_override_sizing_fit(self):
        """intent_override=sizing_fit -> high priority, 4h SLA."""
        priority, intent, sla = _priority_for_question_with_intent(
            needs_response=True,
            question_text="Какой-то непонятный вопрос",
            occurred_at=None,
            intent_override="sizing_fit",
        )
        assert intent == "sizing_fit"
        assert priority == "high"
        assert sla == 4 * 60

    def test_no_override_uses_rule_based(self):
        """Without intent_override, uses rule-based detection."""
        priority, intent, sla = _priority_for_question_with_intent(
            needs_response=True,
            question_text="Какой размер подойдёт?",
            occurred_at=None,
        )
        assert intent == "sizing_fit"

    def test_answered_ignores_override(self):
        """When needs_response=False, intent_override is ignored."""
        priority, intent, sla = _priority_for_question_with_intent(
            needs_response=False,
            question_text="Любой текст",
            occurred_at=None,
            intent_override="compliance_safety",
        )
        assert priority == "low"
        assert intent == "answered"


# ---- VALID_INTENTS consistency -------------------------------------------

class TestValidIntents:
    """VALID_INTENTS should match rule-based _question_intent outputs."""

    def test_all_rule_intents_in_valid(self):
        """Every intent returned by _question_intent must be in VALID_INTENTS."""
        test_cases = {
            "размер": "sizing_fit",
            "в наличии": "availability_delivery",
            "материал": "spec_compatibility",
            "сертификат": "compliance_safety",
            "брак": "post_purchase_issue",
            "случайный текст": "general_question",
        }
        for text, expected in test_cases.items():
            result = _question_intent(text)
            assert result == expected, f"_question_intent({text!r}) = {result!r}, expected {expected!r}"
            assert result in VALID_INTENTS, f"{result!r} not in VALID_INTENTS"


# ---- classify_question_intent_llm unit tests ------------------------------

class TestClassifyQuestionIntentLLM:
    """Direct tests for the LLM classification function."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        """Without API key, returns None immediately."""
        with patch("app.services.ai_question_analyzer.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                DEEPSEEK_API_KEY=None,
                DEEPSEEK_BASE_URL="https://api.deepseek.com/v1",
            )
            result = await classify_question_intent_llm("Любой вопрос")
            assert result is None

    @pytest.mark.asyncio
    async def test_valid_llm_response_parsed(self):
        """Valid LLM response is correctly parsed to intent string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "sizing_fit",
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.ai_question_analyzer.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                DEEPSEEK_API_KEY="test-key",
                DEEPSEEK_BASE_URL="https://api.deepseek.com/v1",
            )
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await classify_question_intent_llm("На какой рост рассчитан?")
                assert result == "sizing_fit"

    @pytest.mark.asyncio
    async def test_invalid_intent_from_llm_returns_none(self):
        """LLM returning unknown intent string returns None."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": "some_random_intent_not_in_list",
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.ai_question_analyzer.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                DEEPSEEK_API_KEY="test-key",
                DEEPSEEK_BASE_URL="https://api.deepseek.com/v1",
            )
            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await classify_question_intent_llm("Любой вопрос")
                assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
