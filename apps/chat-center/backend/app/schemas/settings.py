"""Settings schemas (promo codes, AI preferences)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class PromoChannels(BaseModel):
    chat_positive: bool = True
    chat_negative: bool = True
    chat_questions: bool = True
    reviews_positive: bool = False
    reviews_negative: bool = False


class PromoCode(BaseModel):
    id: str
    code: str
    discount_label: str = "—"
    expires_label: str = "без срока"
    scope_label: str = "Все товары"
    sent_count: int = 0
    active: bool = True
    channels: PromoChannels = Field(default_factory=PromoChannels)
    created_at: datetime
    updated_at: datetime


class PromoConfig(BaseModel):
    """Automation toggles for promo insertion."""

    ai_offer_enabled: bool = True
    warn_reviews_enabled: bool = True


class PromoSettingsResponse(BaseModel):
    promo_codes: list[PromoCode] = Field(default_factory=list)
    config: PromoConfig = Field(default_factory=PromoConfig)


class PromoSettingsUpdateRequest(BaseModel):
    promo_codes: Optional[list[PromoCode]] = None
    config: Optional[PromoConfig] = None


Tone = Literal["formal", "friendly", "neutral"]


class AISettings(BaseModel):
    tone: Tone = "friendly"
    auto_replies_positive: bool = False
    ai_suggestions: bool = True


class AISettingsResponse(BaseModel):
    settings: AISettings = Field(default_factory=AISettings)


class AISettingsUpdateRequest(BaseModel):
    settings: AISettings


class GeneralSettings(BaseModel):
    """Operational settings configurable per seller."""

    reply_pending_window_minutes: int = Field(
        default=180,
        ge=30,
        le=1440,
        description="How long (minutes) to keep interaction as 'responded' while WB moderation is pending. Min 30, max 1440 (24h).",
    )


class GeneralSettingsResponse(BaseModel):
    settings: GeneralSettings = Field(default_factory=GeneralSettings)


class GeneralSettingsUpdateRequest(BaseModel):
    settings: GeneralSettings


# ---------------------------------------------------------------------------
# SLA Config schemas (MVP-014: Configurable Priority Thresholds)
# ---------------------------------------------------------------------------

Priority = Literal["urgent", "high", "normal", "low"]


class IntentSLAConfig(BaseModel):
    """SLA configuration for a single intent."""

    priority: Priority = "normal"
    sla_minutes: int = Field(default=240, ge=1, le=10080, description="SLA deadline in minutes (1 min - 7 days)")


class SLAConfig(BaseModel):
    """Full SLA configuration for a seller."""

    intents: dict[str, IntentSLAConfig] = Field(default_factory=dict)
    auto_response_enabled: bool = False
    auto_response_intents: list[str] = Field(default_factory=list)


class SLAConfigResponse(BaseModel):
    """Response wrapper for SLA config."""

    config: SLAConfig = Field(default_factory=SLAConfig)


class SLAConfigUpdateRequest(BaseModel):
    """Request to update SLA config (partial updates supported)."""

    config: SLAConfig

