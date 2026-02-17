"""Settings API endpoints (promo codes, AI settings, SLA config)."""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends
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

