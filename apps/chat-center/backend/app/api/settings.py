"""Settings API endpoints (promo codes, AI settings, SLA config, sandbox, preview)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_seller
from app.models.runtime_setting import RuntimeSetting
from app.models.seller import Seller
from app.schemas.settings import (
    AISettings,
    AISettingsResponse,
    AISettingsUpdateRequest,
    GeneralSettings,
    GeneralSettingsResponse,
    GeneralSettingsUpdateRequest,
    PromoConfig,
    PromoSettingsResponse,
    PromoSettingsUpdateRequest,
    ScenarioConfig,
    SLAConfig,
    SLAConfigResponse,
    SLAConfigUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


def _promo_key(seller_id: int) -> str:
    # RuntimeSetting.key is unique: we namespace by seller.
    return f"promo_settings_v1:seller:{seller_id}"


def _ai_key(seller_id: int) -> str:
    return f"ai_settings_v1:seller:{seller_id}"


def _general_key(seller_id: int) -> str:
    return f"general_settings_v1:seller:{seller_id}"


def _safe_json_load(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


async def _get_runtime_setting(db: AsyncSession, key: str) -> RuntimeSetting | None:
    result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
    return result.scalar_one_or_none()


async def _set_runtime_setting(db: AsyncSession, key: str, value: str) -> None:
    record = await _get_runtime_setting(db, key)
    if record is None:
        db.add(RuntimeSetting(key=key, value=value))
    else:
        record.value = value
    await db.commit()


async def get_seller_setting(db: AsyncSession, seller_id: int, key: str, default: Any = None) -> Any:
    """Read a single field from a seller's general settings.

    This is the public helper intended for use by services (e.g. interaction_ingest)
    that need to read seller-specific configuration without going through an HTTP call.
    """
    record = await _get_runtime_setting(db, _general_key(seller_id))
    payload = _safe_json_load(record.value if record else None)
    if not isinstance(payload, dict):
        return default
    settings_obj = payload.get("settings")
    if not isinstance(settings_obj, dict):
        return default
    return settings_obj.get(key, default)


@router.get("/promo", response_model=PromoSettingsResponse)
async def get_promo_settings(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_runtime_setting(db, _promo_key(seller.id))
    payload = _safe_json_load(record.value if record else None) or {}

    promo_codes = payload.get("promo_codes") if isinstance(payload, dict) else None
    config = payload.get("config") if isinstance(payload, dict) else None

    try:
        return PromoSettingsResponse.model_validate(
            {
                "promo_codes": promo_codes or [],
                "config": config or PromoConfig().model_dump(),
            }
        )
    except Exception as exc:
        logger.warning("Invalid promo settings for seller=%s: %s", seller.id, exc)
        return PromoSettingsResponse()


@router.put("/promo", response_model=PromoSettingsResponse)
async def update_promo_settings(
    payload: PromoSettingsUpdateRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    current = await get_promo_settings(seller=seller, db=db)
    next_codes = payload.promo_codes if payload.promo_codes is not None else current.promo_codes
    next_config = payload.config if payload.config is not None else current.config

    # Keep the v3 constraint from prototype: max 10 simultaneously.
    if len(next_codes) > 10:
        next_codes = next_codes[:10]

    next_state = PromoSettingsResponse(promo_codes=next_codes, config=next_config)
    await _set_runtime_setting(db, _promo_key(seller.id), json.dumps(next_state.model_dump(mode="json")))
    return next_state


@router.get("/ai", response_model=AISettingsResponse)
async def get_ai_settings(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_runtime_setting(db, _ai_key(seller.id))
    payload = _safe_json_load(record.value if record else None) or {}

    settings_obj = payload.get("settings") if isinstance(payload, dict) else None
    try:
        settings = AISettings.model_validate(settings_obj or {})
    except Exception as exc:
        logger.warning("Invalid ai settings for seller=%s: %s", seller.id, exc)
        settings = AISettings()

    # Sync: read actual auto_response fields from SLA config
    try:
        from app.services.sla_config import get_sla_config

        sla = await get_sla_config(db, seller.id)
        settings.auto_replies_positive = sla.get("auto_response_enabled", False)
        settings.auto_response_channels = sla.get("auto_response_channels", ["review"])
        settings.auto_response_nm_ids = sla.get("auto_response_nm_ids", [])
        settings.auto_response_promo_on_5star = sla.get("auto_response_promo_on_5star", False)

        # Sync scenarios
        raw_scenarios = sla.get("auto_response_scenarios", {})
        if raw_scenarios:
            settings.auto_response_scenarios = {
                k: ScenarioConfig.model_validate(v)
                for k, v in raw_scenarios.items()
                if isinstance(v, dict)
            }
    except Exception:
        pass  # Keep whatever was stored in ai_settings

    return AISettingsResponse(settings=settings)


@router.put("/ai", response_model=AISettingsResponse)
async def update_ai_settings(
    payload: AISettingsUpdateRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    state = AISettingsResponse(settings=payload.settings)
    await _set_runtime_setting(db, _ai_key(seller.id), json.dumps(state.model_dump(mode="json")))

    # Sync auto-response fields → SLA config
    try:
        from app.services.sla_config import get_sla_config, update_sla_config

        current_sla = await get_sla_config(db, seller.id)
        sla_changed = False

        if current_sla.get("auto_response_enabled") != payload.settings.auto_replies_positive:
            current_sla["auto_response_enabled"] = payload.settings.auto_replies_positive
            sla_changed = True

        if current_sla.get("auto_response_channels") != payload.settings.auto_response_channels:
            current_sla["auto_response_channels"] = payload.settings.auto_response_channels
            sla_changed = True

        if current_sla.get("auto_response_nm_ids") != payload.settings.auto_response_nm_ids:
            current_sla["auto_response_nm_ids"] = payload.settings.auto_response_nm_ids
            sla_changed = True

        if payload.settings.auto_response_scenarios:
            new_scenarios = {
                k: v.model_dump() for k, v in payload.settings.auto_response_scenarios.items()
            }
            if current_sla.get("auto_response_scenarios") != new_scenarios:
                current_sla["auto_response_scenarios"] = new_scenarios
                sla_changed = True

        if current_sla.get("auto_response_promo_on_5star") != payload.settings.auto_response_promo_on_5star:
            current_sla["auto_response_promo_on_5star"] = payload.settings.auto_response_promo_on_5star
            sla_changed = True

        if sla_changed:
            await update_sla_config(db, seller.id, current_sla)
            logger.info(
                "Synced auto_response settings for seller=%s enabled=%s channels=%s nm_ids=%s",
                seller.id,
                payload.settings.auto_replies_positive,
                payload.settings.auto_response_channels,
                payload.settings.auto_response_nm_ids,
            )
    except Exception as exc:
        logger.warning("Failed to sync auto_response settings for seller=%s: %s", seller.id, exc)

    return state


# ---------------------------------------------------------------------------
# General settings (reply_pending_window_minutes, etc.)
# ---------------------------------------------------------------------------


@router.get("/general", response_model=GeneralSettingsResponse)
async def get_general_settings(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    record = await _get_runtime_setting(db, _general_key(seller.id))
    payload = _safe_json_load(record.value if record else None) or {}

    settings_obj = payload.get("settings") if isinstance(payload, dict) else None
    try:
        settings = GeneralSettings.model_validate(settings_obj or {})
    except Exception as exc:
        logger.warning("Invalid general settings for seller=%s: %s", seller.id, exc)
        settings = GeneralSettings()
    return GeneralSettingsResponse(settings=settings)


@router.put("/general", response_model=GeneralSettingsResponse)
async def update_general_settings(
    payload: GeneralSettingsUpdateRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    state = GeneralSettingsResponse(settings=payload.settings)
    await _set_runtime_setting(db, _general_key(seller.id), json.dumps(state.model_dump(mode="json")))
    return state


# ---------------------------------------------------------------------------
# SLA Config (MVP-014: Configurable Priority Thresholds)
# ---------------------------------------------------------------------------


@router.get("/sla-config", response_model=SLAConfigResponse)
async def get_sla_config_endpoint(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Get current SLA config for authenticated seller (merged with defaults)."""
    from app.services.sla_config import get_sla_config

    config_dict = await get_sla_config(db, seller.id)
    config = SLAConfig.model_validate(config_dict)
    return SLAConfigResponse(config=config)


@router.put("/sla-config", response_model=SLAConfigResponse)
async def update_sla_config_endpoint(
    payload: SLAConfigUpdateRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Update SLA config for authenticated seller (partial merge with defaults)."""
    from app.services.sla_config import update_sla_config

    merged = await update_sla_config(
        db, seller.id, payload.config.model_dump(mode="json"),
    )
    config = SLAConfig.model_validate(merged)
    return SLAConfigResponse(config=config)


@router.post("/sla-config/reset", response_model=SLAConfigResponse)
async def reset_sla_config_endpoint(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Reset SLA config to defaults for authenticated seller."""
    from app.services.sla_config import reset_sla_config

    defaults = await reset_sla_config(db, seller.id)
    config = SLAConfig.model_validate(defaults)
    return SLAConfigResponse(config=config)


# ---------------------------------------------------------------------------
# Auto-response presets
# ---------------------------------------------------------------------------


@router.get("/auto-response/presets")
async def get_auto_response_presets(
    seller: Seller = Depends(get_current_seller),
):
    """Get available auto-response presets."""
    from app.services.auto_response_presets import get_presets

    return {"presets": get_presets()}


class ApplyPresetRequest(BaseModel):
    preset: str = PydanticField(description="Preset name: safe, balanced, or max")


class ApplyPresetResponse(BaseModel):
    preset: str
    channels: list[str]
    scenarios: dict


@router.post("/auto-response/apply-preset", response_model=ApplyPresetResponse)
async def apply_auto_response_preset(
    payload: ApplyPresetRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Apply a preset to the seller's auto-response config.

    Updates SLA config with the preset's scenario config and channels.
    """
    from app.services.auto_response_presets import (
        PRESETS,
        build_scenario_config_for_preset,
    )
    from app.services.sla_config import get_sla_config, update_sla_config

    if payload.preset not in PRESETS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown preset: {payload.preset}")

    preset_def = PRESETS[payload.preset]
    scenario_config = build_scenario_config_for_preset(payload.preset)

    # Read current config, update scenarios + channels
    current = await get_sla_config(db, seller.id)
    current["auto_response_scenarios"] = scenario_config
    current["auto_response_channels"] = preset_def["channels"]

    await update_sla_config(db, seller.id, current)

    return ApplyPresetResponse(
        preset=payload.preset,
        channels=preset_def["channels"],
        scenarios=scenario_config,
    )


# ---------------------------------------------------------------------------
# Sandbox mode toggle (TASK 2)
# ---------------------------------------------------------------------------


class SandboxModeRequest(BaseModel):
    enabled: bool = PydanticField(description="Enable or disable sandbox mode")


class SandboxModeResponse(BaseModel):
    sandbox_mode: bool
    message: str


@router.post("/sandbox-mode", response_model=SandboxModeResponse)
async def toggle_sandbox_mode(
    payload: SandboxModeRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Toggle sandbox mode for auto-responses.

    When enabled, the auto-response pipeline runs fully (intent classification,
    draft generation, guardrails) but does NOT actually send the reply to the
    marketplace. Instead, the draft is stored in interaction.extra_data for review.
    """
    seller.sandbox_mode = payload.enabled
    await db.commit()

    status_label = "включен" if payload.enabled else "выключен"
    logger.info(
        "Sandbox mode %s for seller=%s",
        status_label, seller.id,
    )
    return SandboxModeResponse(
        sandbox_mode=payload.enabled,
        message=f"Sandbox режим {status_label}",
    )


@router.get("/sandbox-mode", response_model=SandboxModeResponse)
async def get_sandbox_mode(
    seller: Seller = Depends(get_current_seller),
):
    """Get current sandbox mode status."""
    is_sandbox = getattr(seller, "sandbox_mode", False) or False
    status_label = "включен" if is_sandbox else "выключен"
    return SandboxModeResponse(
        sandbox_mode=is_sandbox,
        message=f"Sandbox режим {status_label}",
    )


# ---------------------------------------------------------------------------
# Auto-response preview / dry-run endpoint (TASK 3)
# ---------------------------------------------------------------------------


class AutoResponsePreviewRequest(BaseModel):
    text: str = PydanticField(description="Customer message text")
    rating: Optional[int] = PydanticField(default=None, description="Star rating (1-5, for reviews)")
    channel: str = PydanticField(default="review", description="Channel: review, question, chat")
    nm_id: Optional[str] = PydanticField(default=None, description="Product article ID (optional)")


class AutoResponsePreviewResponse(BaseModel):
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    recommendation: Optional[str] = None
    would_auto_send: bool = False
    guardrails_passed: bool = True
    guardrails_warnings: List[str] = PydanticField(default_factory=list)
    auto_guardrails_passed: bool = True
    auto_guardrails_warnings: List[str] = PydanticField(default_factory=list)
    scenario_action: Optional[str] = None
    promo_would_insert: bool = False


@router.post("/auto-response/preview", response_model=AutoResponsePreviewResponse)
async def preview_auto_response(
    payload: AutoResponsePreviewRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """Preview what the auto-response pipeline would produce.

    Runs the full AI analysis, scenario check, guardrails validation,
    and promo eligibility check WITHOUT sending anything. Useful for
    testing auto-response configuration before enabling it.
    """
    from datetime import datetime, timezone

    from app.services.ai_analyzer import AIAnalyzer
    from app.services.guardrails import apply_guardrails, validate_auto_response
    from app.services.llm_runtime import get_llm_runtime_config
    from app.services.product_context import get_product_context_for_nm_id
    from app.services.sla_config import get_sla_config

    channel = payload.channel or "review"
    rating = payload.rating

    result = AutoResponsePreviewResponse()

    # --- Step 1: AI analysis ---
    try:
        llm_runtime = await get_llm_runtime_config(db)
        analyzer = AIAnalyzer(
            provider=llm_runtime.provider,
            model_name=llm_runtime.model_name,
            enabled=llm_runtime.enabled,
        )

        message_text = payload.text or ""
        if channel == "review" and rating is not None:
            rating_stars = "*" * rating
            message_text = f"[{rating_stars} ({rating}/5)] {message_text}"

        messages = [
            {
                "text": message_text,
                "author_type": "buyer",
                "created_at": datetime.now(timezone.utc),
            }
        ]

        # Product context
        product_context = ""
        if payload.nm_id:
            try:
                product_context = await get_product_context_for_nm_id(payload.nm_id)
            except Exception:
                pass

        # Get SLA config for scenario checks
        sla_config = await get_sla_config(db, seller.id)

        from app.services.product_context import build_rating_context
        rating_context = build_rating_context(rating, channel)

        analysis = await analyzer.analyze_chat(
            messages=messages,
            product_name="Товар",
            product_context=product_context,
            rating_context=rating_context,
            channel=channel,
            rating=rating,
            sla_config=sla_config,
        )

        if analysis:
            result.intent = analysis.get("intent")
            result.sentiment = analysis.get("sentiment")
            result.recommendation = analysis.get("recommendation")
    except Exception as exc:
        logger.warning("Preview AI analysis failed for seller=%s: %s", seller.id, exc)
        result.recommendation = None

    # --- Step 2: Scenario check ---
    intent = result.intent or ""
    try:
        sla_config = await get_sla_config(db, seller.id)
        scenarios = sla_config.get("auto_response_scenarios", {})
        scenario = scenarios.get(intent)

        if scenario:
            result.scenario_action = scenario.get("action", "block")
            scenario_enabled = scenario.get("enabled", False)
            scenario_channels = scenario.get("channels", [])

            result.would_auto_send = (
                result.scenario_action == "auto"
                and scenario_enabled
                and (not scenario_channels or channel in scenario_channels)
                and sla_config.get("auto_response_enabled", False)
                and (rating is not None and rating >= 4)
            )
        else:
            result.scenario_action = "block"
            # Check legacy intents
            allowed_intents = sla_config.get("auto_response_intents", [])
            result.would_auto_send = (
                intent in allowed_intents
                and sla_config.get("auto_response_enabled", False)
                and (rating is not None and rating >= 4)
            )
    except Exception:
        result.scenario_action = "unknown"
        result.would_auto_send = False

    # --- Step 3: Guardrails on recommendation ---
    if result.recommendation:
        _, warnings = apply_guardrails(result.recommendation, channel, payload.text)
        error_warnings = [w for w in warnings if w.get("severity") == "error"]
        result.guardrails_passed = len(error_warnings) == 0
        result.guardrails_warnings = [w.get("message", str(w)) for w in error_warnings]

        if result.guardrails_passed:
            result.would_auto_send = result.would_auto_send and True
        else:
            result.would_auto_send = False

        # --- Step 3b: Stricter auto-response guardrails ---
        is_safe, auto_reasons = await validate_auto_response(
            text=result.recommendation,
            channel=channel,
            seller_id=seller.id,
            db=db,
        )
        result.auto_guardrails_passed = is_safe
        result.auto_guardrails_warnings = auto_reasons
        if not is_safe:
            result.would_auto_send = False

    # --- Step 4: Promo eligibility ---
    try:
        if (
            rating == 5
            and channel == "review"
            and sla_config.get("auto_response_promo_on_5star", False)
        ):
            from app.services.auto_response import _insert_promo_code
            promo = await _insert_promo_code(db, seller.id, result.recommendation or "")
            result.promo_would_insert = promo is not None
    except Exception:
        result.promo_would_insert = False

    return result

