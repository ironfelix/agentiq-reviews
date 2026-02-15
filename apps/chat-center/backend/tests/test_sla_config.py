"""Tests for SLA config service and AI analyzer integration.

MVP-014: Configurable Priority Thresholds.

Tests:
- Default config returns expected values
- Custom config overrides defaults
- Partial update (only change some intents)
- Reset to defaults
- AI analyzer uses custom config when available
- API endpoints (schema validation)

Run with: pytest tests/test_sla_config.py -v
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set required env vars BEFORE importing app modules
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_sla_config.db")

from app.database import Base
from app.services.sla_config import (
    DEFAULT_SLA_CONFIG,
    get_default_sla_config,
    get_sla_config,
    update_sla_config,
    reset_sla_config,
    get_intent_priority,
)
from app.services.ai_analyzer import AIAnalyzer, SLA_PRIORITIES
from app.schemas.settings import (
    IntentSLAConfig,
    SLAConfig,
    SLAConfigResponse,
    SLAConfigUpdateRequest,
)


TEST_DB_PATH = Path("./test_sla_config.db")
SELLER_ID = 999


@pytest.fixture
async def db():
    """Async SQLite session for isolated testing."""
    db_url = "sqlite+aiosqlite:///./test_sla_config.db"
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
def analyzer():
    """AIAnalyzer instance with dummy API key (no real LLM calls)."""
    return AIAnalyzer(api_key="test-key", base_url="http://test")


# ---------------------------------------------------------------------------
# get_default_sla_config
# ---------------------------------------------------------------------------


class TestDefaultSLAConfig:
    """Test default SLA config values."""

    def test_returns_deep_copy(self):
        """get_default_sla_config returns a new dict each time."""
        a = get_default_sla_config()
        b = get_default_sla_config()
        assert a == b
        assert a is not b

    def test_default_intents_match_module_constant(self):
        """Default config intent priorities match SLA_PRIORITIES from ai_analyzer."""
        defaults = get_default_sla_config()
        for intent, priority in SLA_PRIORITIES.items():
            assert intent in defaults["intents"], f"Missing intent: {intent}"
            assert defaults["intents"][intent]["priority"] == priority

    def test_urgent_intents(self):
        """defect_not_working and wrong_item should be urgent with 30-min SLA."""
        defaults = get_default_sla_config()
        for intent in ("defect_not_working", "wrong_item"):
            cfg = defaults["intents"][intent]
            assert cfg["priority"] == "urgent"
            assert cfg["sla_minutes"] == 30

    def test_pre_purchase_intents(self):
        """Pre-purchase intents should be high priority with 5-min SLA."""
        defaults = get_default_sla_config()
        for intent in ("pre_purchase", "sizing_fit", "availability", "compatibility"):
            cfg = defaults["intents"][intent]
            assert cfg["priority"] == "high"
            assert cfg["sla_minutes"] == 5

    def test_low_priority_intents(self):
        """Low-priority intents get 1440-min SLA (24 hours)."""
        defaults = get_default_sla_config()
        for intent in ("usage_howto", "product_spec", "thanks"):
            cfg = defaults["intents"][intent]
            assert cfg["priority"] == "low"
            assert cfg["sla_minutes"] == 1440

    def test_auto_response_defaults(self):
        """Auto-response should be disabled by default with 'thanks' in allowed list."""
        defaults = get_default_sla_config()
        assert defaults["auto_response_enabled"] is False
        assert "thanks" in defaults["auto_response_intents"]


# ---------------------------------------------------------------------------
# get_sla_config (DB reads)
# ---------------------------------------------------------------------------


class TestGetSLAConfig:
    """Test reading SLA config from DB."""

    @pytest.mark.asyncio
    async def test_returns_defaults_when_no_record(self, db):
        """With no record in DB, returns full default config."""
        config = await get_sla_config(db, SELLER_ID)
        assert config == get_default_sla_config()

    @pytest.mark.asyncio
    async def test_returns_defaults_with_correct_structure(self, db):
        """Returned config has expected top-level keys."""
        config = await get_sla_config(db, SELLER_ID)
        assert "intents" in config
        assert "auto_response_enabled" in config
        assert "auto_response_intents" in config
        assert isinstance(config["intents"], dict)


# ---------------------------------------------------------------------------
# update_sla_config
# ---------------------------------------------------------------------------


class TestUpdateSLAConfig:
    """Test writing/updating SLA config in DB."""

    @pytest.mark.asyncio
    async def test_full_override(self, db):
        """Full config update persists and reads back correctly."""
        custom = {
            "intents": {
                "defect_not_working": {"priority": "high", "sla_minutes": 60},
            },
            "auto_response_enabled": True,
            "auto_response_intents": ["thanks", "usage_howto"],
        }
        merged = await update_sla_config(db, SELLER_ID, custom)

        # The overridden intent should reflect the custom value
        assert merged["intents"]["defect_not_working"]["priority"] == "high"
        assert merged["intents"]["defect_not_working"]["sla_minutes"] == 60
        assert merged["auto_response_enabled"] is True
        assert "usage_howto" in merged["auto_response_intents"]

    @pytest.mark.asyncio
    async def test_partial_update_preserves_defaults(self, db):
        """Updating one intent preserves defaults for all others."""
        custom = {
            "intents": {
                "thanks": {"priority": "normal", "sla_minutes": 120},
            },
            "auto_response_enabled": False,
            "auto_response_intents": [],
        }
        merged = await update_sla_config(db, SELLER_ID, custom)

        # Custom intent changed
        assert merged["intents"]["thanks"]["priority"] == "normal"
        assert merged["intents"]["thanks"]["sla_minutes"] == 120

        # Other intents remain at defaults
        assert merged["intents"]["defect_not_working"]["priority"] == "urgent"
        assert merged["intents"]["defect_not_working"]["sla_minutes"] == 30
        assert merged["intents"]["pre_purchase"]["priority"] == "high"
        assert merged["intents"]["pre_purchase"]["sla_minutes"] == 5

    @pytest.mark.asyncio
    async def test_update_idempotent(self, db):
        """Updating the same config twice produces the same result."""
        custom = {
            "intents": {
                "wrong_item": {"priority": "normal", "sla_minutes": 120},
            },
            "auto_response_enabled": False,
            "auto_response_intents": [],
        }
        result1 = await update_sla_config(db, SELLER_ID, custom)
        result2 = await update_sla_config(db, SELLER_ID, custom)
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_successive_updates_overwrite(self, db):
        """A second update replaces the first."""
        await update_sla_config(db, SELLER_ID, {
            "intents": {"thanks": {"priority": "high", "sla_minutes": 10}},
            "auto_response_enabled": False,
            "auto_response_intents": [],
        })
        merged = await update_sla_config(db, SELLER_ID, {
            "intents": {"thanks": {"priority": "low", "sla_minutes": 2880}},
            "auto_response_enabled": True,
            "auto_response_intents": ["thanks"],
        })
        assert merged["intents"]["thanks"]["priority"] == "low"
        assert merged["intents"]["thanks"]["sla_minutes"] == 2880
        assert merged["auto_response_enabled"] is True


# ---------------------------------------------------------------------------
# reset_sla_config
# ---------------------------------------------------------------------------


class TestResetSLAConfig:
    """Test resetting SLA config to defaults."""

    @pytest.mark.asyncio
    async def test_reset_returns_defaults(self, db):
        """After reset, config matches defaults."""
        # First set a custom config
        await update_sla_config(db, SELLER_ID, {
            "intents": {"defect_not_working": {"priority": "low", "sla_minutes": 9999}},
            "auto_response_enabled": True,
            "auto_response_intents": ["defect_not_working"],
        })
        # Verify it was changed
        config = await get_sla_config(db, SELLER_ID)
        assert config["intents"]["defect_not_working"]["priority"] == "low"

        # Reset
        result = await reset_sla_config(db, SELLER_ID)
        assert result == get_default_sla_config()

        # Read again to verify DB state
        config_after = await get_sla_config(db, SELLER_ID)
        assert config_after == get_default_sla_config()

    @pytest.mark.asyncio
    async def test_reset_without_custom_config(self, db):
        """Resetting when no custom config exists is a no-op returning defaults."""
        result = await reset_sla_config(db, SELLER_ID)
        assert result == get_default_sla_config()


# ---------------------------------------------------------------------------
# get_intent_priority
# ---------------------------------------------------------------------------


class TestGetIntentPriority:
    """Test getting priority for a specific intent."""

    @pytest.mark.asyncio
    async def test_default_intent_priority(self, db):
        """Without custom config, returns default priority."""
        priority, sla_minutes = await get_intent_priority(db, SELLER_ID, "defect_not_working")
        assert priority == "urgent"
        assert sla_minutes == 30

    @pytest.mark.asyncio
    async def test_custom_intent_priority(self, db):
        """With custom config, returns overridden priority."""
        await update_sla_config(db, SELLER_ID, {
            "intents": {"defect_not_working": {"priority": "normal", "sla_minutes": 120}},
            "auto_response_enabled": False,
            "auto_response_intents": [],
        })
        priority, sla_minutes = await get_intent_priority(db, SELLER_ID, "defect_not_working")
        assert priority == "normal"
        assert sla_minutes == 120

    @pytest.mark.asyncio
    async def test_unknown_intent_returns_normal(self, db):
        """Unknown intent returns ('normal', 240) defaults."""
        priority, sla_minutes = await get_intent_priority(db, SELLER_ID, "totally_unknown")
        assert priority == "normal"
        assert sla_minutes == 240


# ---------------------------------------------------------------------------
# AIAnalyzer integration (uses sla_config parameter)
# ---------------------------------------------------------------------------


class TestAIAnalyzerSLAConfigIntegration:
    """Test that AIAnalyzer respects sla_config when calculating priorities."""

    def test_calculate_sla_priority_default(self, analyzer):
        """Without sla_config, uses module-level SLA_PRIORITIES."""
        result = analyzer._calculate_sla_priority(
            intent="defect_not_working",
            urgency="normal",
            messages=[],
        )
        assert result == "urgent"

    def test_calculate_sla_priority_with_config_override(self, analyzer):
        """With sla_config, uses the config's priority."""
        custom_config = {
            "intents": {
                "defect_not_working": {"priority": "normal", "sla_minutes": 120},
            },
        }
        result = analyzer._calculate_sla_priority(
            intent="defect_not_working",
            urgency="normal",
            messages=[],
            sla_config=custom_config,
        )
        assert result == "normal"

    def test_calculate_sla_priority_config_missing_intent(self, analyzer):
        """If intent not in sla_config, falls back to SLA_PRIORITIES."""
        custom_config = {
            "intents": {
                "thanks": {"priority": "high", "sla_minutes": 10},
            },
        }
        result = analyzer._calculate_sla_priority(
            intent="defect_not_working",
            urgency="normal",
            messages=[],
            sla_config=custom_config,
        )
        # defect_not_working not in custom config => falls back to SLA_PRIORITIES
        assert result == "urgent"

    def test_calculate_sla_priority_escalation_with_config(self, analyzer):
        """Multiple buyer messages still trigger escalation even with custom config."""
        custom_config = {
            "intents": {
                "delivery_status": {"priority": "normal", "sla_minutes": 240},
            },
        }
        messages = [
            {"author_type": "buyer", "text": "test1"},
            {"author_type": "buyer", "text": "test2"},
            {"author_type": "buyer", "text": "test3"},
        ]
        result = analyzer._calculate_sla_priority(
            intent="delivery_status",
            urgency="normal",
            messages=messages,
            sla_config=custom_config,
        )
        # 3 buyer messages: normal -> high
        assert result == "high"

    def test_resolve_intent_priority_with_config(self, analyzer):
        """_resolve_intent_priority uses config if available."""
        custom_config = {
            "intents": {
                "thanks": {"priority": "high", "sla_minutes": 10},
            },
        }
        assert AIAnalyzer._resolve_intent_priority("thanks", custom_config) == "high"

    def test_resolve_intent_priority_without_config(self, analyzer):
        """_resolve_intent_priority falls back to SLA_PRIORITIES."""
        assert AIAnalyzer._resolve_intent_priority("thanks", None) == "low"
        assert AIAnalyzer._resolve_intent_priority("thanks") == "low"

    def test_fallback_analysis_uses_sla_config(self, analyzer):
        """_fallback_analysis uses sla_config for priority."""
        custom_config = {
            "intents": {
                "thanks": {"priority": "high", "sla_minutes": 10},
            },
        }
        messages = [{"author_type": "buyer", "text": "Спасибо за помощь!"}]
        result = analyzer._fallback_analysis(messages, "Олег", sla_config=custom_config)
        assert result["intent"] == "thanks"
        assert result["sla_priority"] == "high"

    def test_fallback_analysis_without_sla_config(self, analyzer):
        """_fallback_analysis uses default SLA_PRIORITIES when no config."""
        messages = [{"author_type": "buyer", "text": "Спасибо за помощь!"}]
        result = analyzer._fallback_analysis(messages, "Олег")
        assert result["intent"] == "thanks"
        assert result["sla_priority"] == "low"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


class TestSLAConfigSchemas:
    """Test Pydantic schemas for SLA config."""

    def test_intent_sla_config_defaults(self):
        """IntentSLAConfig has sensible defaults."""
        cfg = IntentSLAConfig()
        assert cfg.priority == "normal"
        assert cfg.sla_minutes == 240

    def test_intent_sla_config_valid(self):
        """IntentSLAConfig accepts valid values."""
        cfg = IntentSLAConfig(priority="urgent", sla_minutes=5)
        assert cfg.priority == "urgent"
        assert cfg.sla_minutes == 5

    def test_intent_sla_config_min_boundary(self):
        """sla_minutes must be >= 1."""
        with pytest.raises(Exception):
            IntentSLAConfig(priority="normal", sla_minutes=0)

    def test_intent_sla_config_max_boundary(self):
        """sla_minutes must be <= 10080 (7 days)."""
        with pytest.raises(Exception):
            IntentSLAConfig(priority="normal", sla_minutes=99999)

    def test_intent_sla_config_invalid_priority(self):
        """Priority must be one of urgent/high/normal/low."""
        with pytest.raises(Exception):
            IntentSLAConfig(priority="critical", sla_minutes=30)

    def test_sla_config_defaults(self):
        """SLAConfig defaults to empty intents and disabled auto-response."""
        cfg = SLAConfig()
        assert cfg.intents == {}
        assert cfg.auto_response_enabled is False
        assert cfg.auto_response_intents == []

    def test_sla_config_response_wrapper(self):
        """SLAConfigResponse wraps config correctly."""
        resp = SLAConfigResponse()
        assert isinstance(resp.config, SLAConfig)

    def test_sla_config_update_request(self):
        """SLAConfigUpdateRequest requires config field."""
        req = SLAConfigUpdateRequest(config=SLAConfig(
            intents={"thanks": IntentSLAConfig(priority="high", sla_minutes=10)},
            auto_response_enabled=True,
            auto_response_intents=["thanks"],
        ))
        assert req.config.intents["thanks"].priority == "high"
        assert req.config.auto_response_enabled is True
