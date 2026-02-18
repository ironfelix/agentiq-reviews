"""Settings schemas (promo codes, AI preferences)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

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
    nm_ids: list[int] = Field(default_factory=list)
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

ScenarioAction = Literal["auto", "draft", "block"]


class ScenarioConfig(BaseModel):
    """Configuration for a single auto-response scenario."""
    action: ScenarioAction = "block"
    channels: list[str] = Field(default_factory=list)
    enabled: bool = False


class AutoResponseDelayConfig(BaseModel):
    """Random delay config between auto-responses."""
    min_seconds: float = 3.0
    max_seconds: float = 8.0
    word_count_factor: float = 0.025


class AISettings(BaseModel):
    tone: Tone = "friendly"
    auto_replies_positive: bool = False
    ai_suggestions: bool = True
    auto_response_channels: list[str] = Field(
        default_factory=lambda: ["review"],
        description="Which channels to auto-respond on: review, question, chat",
    )
    auto_response_nm_ids: list[int] = Field(
        default_factory=list,
        description="Whitelist of article IDs (nm_id) for auto-response. Empty = all articles.",
    )
    auto_response_scenarios: Dict[str, ScenarioConfig] = Field(
        default_factory=dict,
        description="Mapping intent -> scenario config (action/channels/enabled).",
    )
    auto_response_promo_on_5star: bool = Field(
        default=False,
        description="Insert promo code in auto-response for 5-star reviews.",
    )


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
    auto_response_channels: list[str] = Field(
        default_factory=lambda: ["review"],
        description="Which channels to auto-respond on: review, question, chat",
    )
    auto_response_nm_ids: list[int] = Field(
        default_factory=list,
        description="Whitelist of article IDs (nm_id) for auto-response. Empty = all articles.",
    )
    auto_response_scenarios: Dict[str, ScenarioConfig] = Field(
        default_factory=dict,
        description="Mapping intent -> scenario config (action/channels/enabled).",
    )
    auto_response_promo_on_5star: bool = False
    auto_response_delay: AutoResponseDelayConfig = Field(
        default_factory=AutoResponseDelayConfig,
    )


class SLAConfigResponse(BaseModel):
    """Response wrapper for SLA config."""

    config: SLAConfig = Field(default_factory=SLAConfig)


class SLAConfigUpdateRequest(BaseModel):
    """Request to update SLA config (partial updates supported)."""

    config: SLAConfig

