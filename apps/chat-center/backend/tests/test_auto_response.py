"""Tests for auto-response service.

MVP auto-response: positive feedback (4-5 star reviews) only.

Test cases:
- Auto-response sent for 5-star thanks intent when enabled
- Auto-response NOT sent when disabled
- Auto-response NOT sent for rating <= 3
- Auto-response NOT sent for non-allowed intents
- Auto-response NOT sent when guardrails fail
- Auto-response NOT sent when WB connector fails (graceful)
- is_auto_response flag is set correctly

Run with: pytest tests/test_auto_response.py -v
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set required env vars BEFORE importing app modules
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_auto_response.db")

from app.database import Base
from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent
from app.models.seller import Seller
from app.services.auto_response import process_auto_response
from app.services.interaction_drafts import DraftResult


TEST_DB_PATH = Path("./test_auto_response.db")
SELLER_ID = 777


@pytest.fixture
async def db():
    """Async SQLite session for isolated testing."""
    db_url = "sqlite+aiosqlite:///./test_auto_response.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
async def seller(db: AsyncSession) -> Seller:
    """Create a test seller."""
    seller = Seller(
        id=SELLER_ID,
        name="Test Seller",
        email="test_auto@pytest.com",
        marketplace="wildberries",
        api_key_encrypted="encrypted_test_key",
        is_active=True,
    )
    db.add(seller)
    await db.commit()
    await db.refresh(seller)
    return seller


def _make_interaction(
    seller_id: int = SELLER_ID,
    channel: str = "review",
    rating: Optional[int] = 5,
    text: str = "Отличный товар! Спасибо!",
    status: str = "open",
    needs_response: bool = True,
    external_id: str = "fb-test-123",
) -> Interaction:
    """Build a test interaction (NOT added to DB -- caller manages that)."""
    return Interaction(
        seller_id=seller_id,
        marketplace="wb",
        channel=channel,
        external_id=external_id,
        text=text,
        rating=rating,
        status=status,
        needs_response=needs_response,
        is_auto_response=False,
        occurred_at=datetime.now(timezone.utc),
        subject="Тестовый товар",
        extra_data={"user_name": "Тест"},
    )


def _make_ai_result(intent: str = "thanks") -> Dict:
    """Minimal AI analysis result."""
    return {
        "intent": intent,
        "sentiment": "positive",
        "urgency": "low",
        "categories": ["praise"],
        "recommendation": "Спасибо за отзыв! Рады, что товар понравился.",
        "recommendation_reason": "Positive feedback response",
        "needs_escalation": False,
        "escalation_reason": None,
        "sla_priority": "low",
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


def _make_draft(text: str = "Здравствуйте! Спасибо за отзыв! Рады, что товар понравился.") -> DraftResult:
    """Minimal draft result."""
    return DraftResult(
        text=text,
        intent="thanks",
        sentiment="positive",
        sla_priority="low",
        recommendation_reason="Positive feedback response",
        source="llm",
    )


def _sla_config_enabled() -> Dict:
    """SLA config with auto-response enabled."""
    return {
        "intents": {
            "thanks": {"priority": "low", "sla_minutes": 1440},
        },
        "auto_response_enabled": True,
        "auto_response_intents": ["thanks"],
    }


def _sla_config_disabled() -> Dict:
    """SLA config with auto-response disabled."""
    return {
        "intents": {
            "thanks": {"priority": "low", "sla_minutes": 1440},
        },
        "auto_response_enabled": False,
        "auto_response_intents": ["thanks"],
    }


# ---------------------------------------------------------------------------
# Test: auto-response sent for 5-star thanks when enabled
# ---------------------------------------------------------------------------


class TestAutoResponseSent:
    """Test that auto-response is sent for eligible interactions."""

    @pytest.mark.asyncio
    async def test_sent_for_5star_thanks_enabled(self, db, seller):
        """5-star review with thanks intent and auto-response enabled -> sent."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is True
        assert interaction.is_auto_response is True
        assert interaction.status == "responded"
        assert interaction.needs_response is False

    @pytest.mark.asyncio
    async def test_sent_for_4star_thanks_enabled(self, db, seller):
        """4-star review with thanks intent -> also sent (4+ is allowed)."""
        interaction = _make_interaction(rating=4)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is True
        assert interaction.is_auto_response is True

    @pytest.mark.asyncio
    async def test_extra_data_updated_on_success(self, db, seller):
        """On success, extra_data should contain auto_response metadata."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await process_auto_response(db, interaction, ai_result, seller)

        assert isinstance(interaction.extra_data, dict)
        assert interaction.extra_data.get("last_reply_source") == "auto_response"
        assert interaction.extra_data.get("auto_response_intent") == "thanks"
        assert "last_reply_text" in interaction.extra_data


# ---------------------------------------------------------------------------
# Test: auto-response NOT sent when disabled
# ---------------------------------------------------------------------------


class TestAutoResponseDisabled:
    """Test that auto-response is NOT sent when disabled."""

    @pytest.mark.asyncio
    async def test_not_sent_when_disabled(self, db, seller):
        """Auto-response disabled in config -> NOT sent."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_disabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
        assert interaction.is_auto_response is False
        assert interaction.status == "open"


# ---------------------------------------------------------------------------
# Test: auto-response NOT sent for rating <= 3
# ---------------------------------------------------------------------------


class TestAutoResponseRatingGuard:
    """Test rating safety guard: never auto-respond to negatives."""

    @pytest.mark.asyncio
    async def test_not_sent_for_rating_3(self, db, seller):
        """Rating 3 -> BLOCKED by safety guard."""
        interaction = _make_interaction(rating=3)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
        assert interaction.is_auto_response is False

    @pytest.mark.asyncio
    async def test_not_sent_for_rating_1(self, db, seller):
        """Rating 1 -> BLOCKED by safety guard."""
        interaction = _make_interaction(rating=1)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False

    @pytest.mark.asyncio
    async def test_not_sent_for_rating_none(self, db, seller):
        """Rating None (no rating) -> BLOCKED by safety guard."""
        interaction = _make_interaction(rating=None)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False


# ---------------------------------------------------------------------------
# Test: auto-response NOT sent for non-allowed intents
# ---------------------------------------------------------------------------


class TestAutoResponseIntentGuard:
    """Test intent guard: only allowed intents trigger auto-response."""

    @pytest.mark.asyncio
    async def test_not_sent_for_defect_intent(self, db, seller):
        """defect_not_working intent -> NOT in auto_response_intents -> skip."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="defect_not_working")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False

    @pytest.mark.asyncio
    async def test_not_sent_for_refund_intent(self, db, seller):
        """refund_exchange intent -> NOT in auto_response_intents -> skip."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="refund_exchange")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False

    @pytest.mark.asyncio
    async def test_not_sent_for_other_intent(self, db, seller):
        """'other' intent -> NOT in auto_response_intents -> skip."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="other")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False


# ---------------------------------------------------------------------------
# Test: auto-response NOT sent when guardrails fail
# ---------------------------------------------------------------------------


class TestAutoResponseGuardrails:
    """Test guardrail enforcement: auto-response blocked on error-severity violations."""

    @pytest.mark.asyncio
    async def test_not_sent_when_guardrails_have_error(self, db, seller):
        """Guardrails return error-severity warning -> BLOCKED."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        # Draft text that contains a banned phrase
        draft = _make_draft(text="Здравствуйте! Мы гарантируем возврат, спасибо за отзыв!")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response.apply_guardrails",
            return_value=(
                draft.text,
                [{"type": "banned_phrase", "severity": "error", "message": "Banned: гарантируем возврат"}],
            ),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
        assert interaction.is_auto_response is False

    @pytest.mark.asyncio
    async def test_sent_when_guardrails_only_warning(self, db, seller):
        """Guardrails return only warning-severity (no errors) -> allowed."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response.apply_guardrails",
            return_value=(
                draft.text,
                [{"type": "too_long", "severity": "warning", "message": "Text slightly long"}],
            ),
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is True
        assert interaction.is_auto_response is True


# ---------------------------------------------------------------------------
# Test: auto-response NOT sent when WB connector fails (graceful)
# ---------------------------------------------------------------------------


class TestAutoResponseConnectorFailure:
    """Test graceful handling of connector failures."""

    @pytest.mark.asyncio
    async def test_not_sent_when_connector_returns_false(self, db, seller):
        """WB connector returns False -> auto-response NOT marked as sent."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
        assert interaction.is_auto_response is False

    @pytest.mark.asyncio
    async def test_not_sent_when_connector_raises(self, db, seller):
        """WB connector raises exception -> graceful failure."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            side_effect=Exception("WB API timeout"),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
        assert interaction.is_auto_response is False

    @pytest.mark.asyncio
    async def test_not_sent_when_draft_generation_fails(self, db, seller):
        """Draft generation raises exception -> graceful failure."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            side_effect=Exception("LLM unavailable"),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False

    @pytest.mark.asyncio
    async def test_not_sent_when_draft_empty(self, db, seller):
        """Draft text is empty -> NOT sent."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft(text="")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False


# ---------------------------------------------------------------------------
# Test: is_auto_response flag correctness
# ---------------------------------------------------------------------------


class TestIsAutoResponseFlag:
    """Test that is_auto_response field is set correctly."""

    @pytest.mark.asyncio
    async def test_flag_false_by_default(self, db, seller):
        """New interaction has is_auto_response=False by default."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        assert interaction.is_auto_response is False

    @pytest.mark.asyncio
    async def test_flag_true_after_auto_response(self, db, seller):
        """After successful auto-response, flag is True."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=True,
        ):
            await process_auto_response(db, interaction, ai_result, seller)

        assert interaction.is_auto_response is True

    @pytest.mark.asyncio
    async def test_flag_unchanged_on_failure(self, db, seller):
        """On failure, is_auto_response remains False."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        draft = _make_draft()

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=_sla_config_enabled(),
        ), patch(
            "app.services.auto_response.generate_interaction_draft",
            new_callable=AsyncMock,
            return_value=draft,
        ), patch(
            "app.services.auto_response._send_reply",
            new_callable=AsyncMock,
            return_value=False,
        ):
            await process_auto_response(db, interaction, ai_result, seller)

        assert interaction.is_auto_response is False
        assert interaction.status == "open"  # unchanged


# ---------------------------------------------------------------------------
# Test: SLA config error handling
# ---------------------------------------------------------------------------


class TestAutoResponseConfigErrors:
    """Test graceful handling of SLA config errors."""

    @pytest.mark.asyncio
    async def test_sla_config_read_failure(self, db, seller):
        """If SLA config read fails, auto-response is skipped gracefully."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection error"),
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False

    @pytest.mark.asyncio
    async def test_empty_auto_response_intents(self, db, seller):
        """Empty auto_response_intents list -> no intents match -> skip."""
        interaction = _make_interaction(rating=5)
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

        ai_result = _make_ai_result(intent="thanks")
        config = _sla_config_enabled()
        config["auto_response_intents"] = []

        with patch(
            "app.services.auto_response.get_sla_config",
            new_callable=AsyncMock,
            return_value=config,
        ):
            result = await process_auto_response(db, interaction, ai_result, seller)

        assert result is False
