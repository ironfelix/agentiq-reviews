"""SLA Config service — configurable priority thresholds per seller.

Stores SLA configuration as JSON in RuntimeSetting table.
Falls back to DEFAULT_SLA_CONFIG when no custom config exists.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.runtime_setting import RuntimeSetting

logger = logging.getLogger(__name__)

# Default SLA config matching current hardcoded values in ai_analyzer.py
DEFAULT_SLA_CONFIG: Dict[str, Any] = {
    "intents": {
        # Post-purchase: urgent
        "defect_not_working": {"priority": "urgent", "sla_minutes": 30},
        "wrong_item": {"priority": "urgent", "sla_minutes": 30},
        # Post-purchase: high
        "delivery_delay": {"priority": "high", "sla_minutes": 60},
        "cancel_request": {"priority": "high", "sla_minutes": 60},
        # Post-purchase: normal
        "refund_exchange": {"priority": "normal", "sla_minutes": 240},
        "delivery_status": {"priority": "normal", "sla_minutes": 240},
        # Post-purchase: low
        "usage_howto": {"priority": "low", "sla_minutes": 1440},
        "product_spec": {"priority": "low", "sla_minutes": 1440},
        "thanks": {"priority": "low", "sla_minutes": 1440},
        "quality_complaint": {"priority": "normal", "sla_minutes": 240},
        "other": {"priority": "normal", "sla_minutes": 240},
        # Pre-purchase: high
        "pre_purchase": {"priority": "high", "sla_minutes": 5},
        "sizing_fit": {"priority": "high", "sla_minutes": 5},
        "availability": {"priority": "high", "sla_minutes": 5},
        "compatibility": {"priority": "high", "sla_minutes": 5},
    },
    "auto_response_enabled": False,
    "auto_response_intents": ["thanks"],  # legacy, kept for backward compat
    "auto_response_channels": ["review"],
    "auto_response_nm_ids": [],
    "auto_response_scenarios": {
        "thanks": {"action": "auto", "channels": ["review"], "enabled": True},
        "delivery_status": {"action": "auto", "channels": ["review", "question", "chat"], "enabled": False},
        "pre_purchase": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
        "sizing_fit": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
        "availability": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
        "compatibility": {"action": "auto", "channels": ["question", "chat"], "enabled": False},
        "refund_exchange": {"action": "draft", "channels": ["review", "question", "chat"], "enabled": False},
        "defect_not_working": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
        "wrong_item": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
        "quality_complaint": {"action": "block", "channels": ["review", "question", "chat"], "enabled": True},
    },
    "auto_response_promo_on_5star": False,
    "auto_response_delay": {
        "min_seconds": 3,
        "max_seconds": 8,
        "word_count_factor": 0.025,
    },
}


def _sla_key(seller_id: int) -> str:
    """RuntimeSetting key for a seller's SLA config."""
    return f"sla_config_v1:seller:{seller_id}"


def get_default_sla_config() -> Dict[str, Any]:
    """Return a deep copy of the default SLA config."""
    return json.loads(json.dumps(DEFAULT_SLA_CONFIG))


async def get_sla_config(db: AsyncSession, seller_id: int) -> Dict[str, Any]:
    """Get seller's SLA config, falling back to defaults for missing intents.

    Returns a merged config: seller overrides on top of defaults.
    """
    defaults = get_default_sla_config()

    try:
        result = await db.execute(
            select(RuntimeSetting).where(
                RuntimeSetting.key == _sla_key(seller_id)
            )
        )
        record = result.scalar_one_or_none()
        if not record or not record.value:
            return defaults

        stored = json.loads(record.value)
        if not isinstance(stored, dict):
            return defaults

        config = stored.get("config", stored)
        if not isinstance(config, dict):
            return defaults

        # Merge: start with defaults, overlay seller-specific intents
        merged_intents = dict(defaults["intents"])
        seller_intents = config.get("intents", {})
        if isinstance(seller_intents, dict):
            for intent_key, intent_val in seller_intents.items():
                if isinstance(intent_val, dict):
                    merged_intents[intent_key] = {
                        "priority": intent_val.get("priority", "normal"),
                        "sla_minutes": intent_val.get("sla_minutes", 240),
                    }

        # Merge scenario config: defaults + seller overrides
        merged_scenarios = dict(defaults.get("auto_response_scenarios", {}))
        seller_scenarios = config.get("auto_response_scenarios", {})
        if isinstance(seller_scenarios, dict):
            for intent_key, scenario_val in seller_scenarios.items():
                if isinstance(scenario_val, dict):
                    merged_scenarios[intent_key] = {
                        "action": scenario_val.get("action", "block"),
                        "channels": scenario_val.get("channels", []),
                        "enabled": scenario_val.get("enabled", False),
                    }

        # Backward compat: if seller has auto_response_intents but no scenarios,
        # generate scenarios from legacy intents list
        if not seller_scenarios and config.get("auto_response_intents"):
            legacy_intents = config["auto_response_intents"]
            for intent_key in legacy_intents:
                if intent_key in merged_scenarios:
                    merged_scenarios[intent_key]["enabled"] = True

        return {
            "intents": merged_intents,
            "auto_response_enabled": config.get(
                "auto_response_enabled",
                defaults["auto_response_enabled"],
            ),
            "auto_response_intents": config.get(
                "auto_response_intents",
                defaults["auto_response_intents"],
            ),
            "auto_response_channels": config.get(
                "auto_response_channels",
                defaults["auto_response_channels"],
            ),
            "auto_response_nm_ids": config.get(
                "auto_response_nm_ids",
                defaults["auto_response_nm_ids"],
            ),
            "auto_response_scenarios": merged_scenarios,
            "auto_response_promo_on_5star": config.get(
                "auto_response_promo_on_5star",
                defaults.get("auto_response_promo_on_5star", False),
            ),
            "auto_response_delay": config.get(
                "auto_response_delay",
                defaults.get("auto_response_delay", {}),
            ),
        }

    except Exception as exc:
        logger.warning("Failed to read SLA config for seller=%s: %s", seller_id, exc)
        return defaults


async def update_sla_config(
    db: AsyncSession,
    seller_id: int,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Update (partial merge) seller's SLA config and return the merged result.

    Only the intents explicitly provided are overwritten; others keep defaults.
    """
    key = _sla_key(seller_id)

    # Build the stored payload (we store the raw seller overrides, not merged)
    payload = json.dumps({"config": config}, ensure_ascii=False)

    result = await db.execute(
        select(RuntimeSetting).where(RuntimeSetting.key == key)
    )
    record = result.scalar_one_or_none()
    if record is None:
        db.add(RuntimeSetting(key=key, value=payload))
    else:
        record.value = payload
    await db.commit()

    # Return the merged config (defaults + overrides)
    return await get_sla_config(db, seller_id)


async def reset_sla_config(db: AsyncSession, seller_id: int) -> Dict[str, Any]:
    """Delete seller's custom SLA config, reverting to defaults."""
    key = _sla_key(seller_id)

    result = await db.execute(
        select(RuntimeSetting).where(RuntimeSetting.key == key)
    )
    record = result.scalar_one_or_none()
    if record is not None:
        await db.delete(record)
        await db.commit()

    return get_default_sla_config()


async def get_intent_priority(
    db: AsyncSession,
    seller_id: int,
    intent: str,
) -> Tuple[str, int]:
    """Get (priority, sla_minutes) for a specific intent.

    Returns defaults if the seller has no custom config or the intent is
    not in their config.
    """
    config = await get_sla_config(db, seller_id)
    intents = config.get("intents", {})
    intent_cfg = intents.get(intent, {"priority": "normal", "sla_minutes": 240})
    return intent_cfg["priority"], intent_cfg["sla_minutes"]
