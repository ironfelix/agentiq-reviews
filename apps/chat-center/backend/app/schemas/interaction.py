"""Interaction schemas for API validation."""

from datetime import datetime
from typing import Optional, Any, Dict

from pydantic import BaseModel, Field


class InteractionResponse(BaseModel):
    """Schema for interaction response."""

    id: int
    seller_id: int
    marketplace: str = Field(..., description="Marketplace identifier (wb/ozon/etc.)")
    channel: str = Field(..., description="Interaction channel (review/question/chat)")
    external_id: str = Field(..., description="External channel entity ID")
    customer_id: Optional[str] = Field(None, description="Buyer identifier if provided by channel")
    order_id: Optional[str] = Field(None, description="Order ID if provided by channel")
    nm_id: Optional[str] = Field(None, description="WB product nmId")
    product_article: Optional[str] = Field(None, description="Product article/SKU")
    subject: Optional[str] = Field(None, description="Short title/subject")
    text: Optional[str] = Field(None, description="Interaction text")
    rating: Optional[int] = Field(None, ge=1, le=5, description="Review rating if channel=review")
    status: str = Field(..., description="Workflow status")
    priority: str = Field(..., description="Priority level")
    needs_response: bool = Field(..., description="Whether operator response is required")
    source: str = Field(..., description="Data source (wb_api/wbcon_fallback)")
    occurred_at: Optional[datetime] = Field(None, description="When customer event happened")
    created_at: datetime
    updated_at: datetime
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Raw channel details")

    class Config:
        from_attributes = True


class InteractionListResponse(BaseModel):
    """Schema for interactions list response."""

    interactions: list[InteractionResponse]
    total: int
    page: int = Field(1, description="Current page number")
    page_size: int = Field(50, description="Items per page")


class InteractionSyncResponse(BaseModel):
    """Schema for ingestion/sync result."""

    seller_id: int
    channel: str
    source: str
    fetched: int
    created: int
    updated: int
    skipped: int


class InteractionReplyRequest(BaseModel):
    """Request schema for replying to an interaction."""

    text: str = Field(..., min_length=1, max_length=5000, description="Reply text")


class InteractionReplyResponse(BaseModel):
    """Response schema for reply action."""

    interaction: InteractionResponse
    result: str


class InteractionDraftRequest(BaseModel):
    """Request schema for AI draft generation."""

    force_regenerate: bool = Field(False, description="Ignore cached draft and regenerate")


class InteractionDraftResponse(BaseModel):
    """Response schema for AI draft generation."""

    interaction: InteractionResponse
    draft_text: str
    intent: Optional[str] = None
    sentiment: Optional[str] = None
    sla_priority: Optional[str] = None
    recommendation_reason: Optional[str] = None
    source: str = Field(..., description="draft source: llm/fallback/cached")


class InteractionQualityTotals(BaseModel):
    """Aggregated quality counters and rates."""

    replies_total: int
    draft_generated: int
    draft_cache_hits: int
    draft_accepted: int
    draft_edited: int
    reply_manual: int
    accept_rate: float
    edit_rate: float
    manual_rate: float


class InteractionChannelQuality(BaseModel):
    """Per-channel quality counters and rates."""

    channel: str
    replies_total: int
    draft_generated: int
    draft_cache_hits: int
    draft_accepted: int
    draft_edited: int
    reply_manual: int
    accept_rate: float
    edit_rate: float
    manual_rate: float


class InteractionChannelPipeline(BaseModel):
    """Current interaction backlog by channel."""

    channel: str
    interactions_total: int
    needs_response_total: int
    responded_total: int


class InteractionPipelineMetrics(BaseModel):
    """Current storage/dispatcher status."""

    interactions_total: int
    needs_response_total: int
    responded_total: int
    by_channel: list[InteractionChannelPipeline]


class InteractionQualityMetricsResponse(BaseModel):
    """Response schema for interaction quality metrics endpoint."""

    period_days: int
    generated_from: datetime
    generated_to: datetime
    totals: InteractionQualityTotals
    by_channel: list[InteractionChannelQuality]
    pipeline: InteractionPipelineMetrics


class InteractionQualityHistoryPoint(BaseModel):
    """Day-level quality point for trends."""

    date: str
    replies_total: int
    draft_accepted: int
    draft_edited: int
    reply_manual: int
    accept_rate: float
    edit_rate: float
    manual_rate: float


class InteractionQualityHistoryResponse(BaseModel):
    """Response schema for quality history endpoint."""

    period_days: int
    generated_from: datetime
    generated_to: datetime
    series: list[InteractionQualityHistoryPoint]


class InteractionTimelineStep(BaseModel):
    """One deterministic step in cross-channel thread timeline."""

    interaction_id: int
    channel: str
    external_id: str
    occurred_at: Optional[datetime] = None
    status: str
    priority: str
    needs_response: bool
    subject: Optional[str] = None
    match_reason: str
    confidence: float
    auto_action_allowed: bool
    action_mode: str
    policy_reason: str
    is_current: bool = False
    wb_url: Optional[str] = None
    last_reply_text: Optional[str] = None
    last_ai_draft_text: Optional[str] = None


class InteractionTimelineResponse(BaseModel):
    """Deterministic cross-channel timeline for one interaction."""

    interaction_id: int
    thread_scope: str
    thread_key: Dict[str, Optional[str]]
    channels_present: list[str]
    steps: list[InteractionTimelineStep]


class InteractionOpsAlert(BaseModel):
    """One operational alert for pilot monitoring."""

    code: str
    severity: str
    title: str
    message: str


class InteractionOpsAlertsResponse(BaseModel):
    """Operational alerts response for seller dashboard."""

    generated_at: datetime
    question_sla: Dict[str, Any]
    quality_regression: Dict[str, Any]
    alerts: list[InteractionOpsAlert]


class InteractionPilotReadinessCheck(BaseModel):
    """One readiness check in go/no-go matrix."""

    code: str
    title: str
    status: str
    blocker: bool
    details: str


class InteractionPilotReadinessSummary(BaseModel):
    """Readiness summary counters."""

    total_checks: int
    passed: int
    warnings: int
    failed: int
    blockers: list[str]


class InteractionPilotReadinessResponse(BaseModel):
    """Pilot go/no-go readiness response."""

    generated_at: datetime
    go_no_go: bool
    decision: str
    summary: InteractionPilotReadinessSummary
    thresholds: Dict[str, Any]
    checks: list[InteractionPilotReadinessCheck]
