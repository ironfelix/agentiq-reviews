"""Revenue impact analytics response schemas."""

from __future__ import annotations

from typing import Dict

from pydantic import BaseModel, Field


class NegativeReviewBreakdown(BaseModel):
    """Breakdown of negative (1-2 star) review counts."""

    total: int = Field(..., description="Total negative reviews in period")
    responded: int = Field(..., description="Negative reviews that were responded to")
    unresolved: int = Field(..., description="Negative reviews still needing response")
    responded_in_sla: int = Field(..., description="Negative reviews responded within SLA")


class QuestionBreakdown(BaseModel):
    """Breakdown of question interaction counts."""

    total: int = Field(..., description="Total questions in period")
    responded: int = Field(..., description="Questions that were responded to")
    responded_fast: int = Field(..., description="Questions responded within SLA")


class RevenueCoefficients(BaseModel):
    """Coefficients used in revenue impact calculation."""

    avg_order_value: float = Field(..., description="Average order value in roubles")
    conversion_drop_per_star: float = Field(
        ..., description="Fraction of conversion lost per star below 5",
    )
    negative_save_rate: float = Field(
        ..., description="Probability of saving a negative review by fast response",
    )
    fast_response_conversion_boost: float = Field(
        ..., description="Conversion boost from fast response to questions",
    )
    repeat_purchase_factor: float = Field(
        ..., description="Lifetime multiplier for saved customers",
    )
    sla_threshold_minutes: int = Field(
        ..., description="SLA threshold in minutes for 'fast' response",
    )


class RevenueImpactResponse(BaseModel):
    """Response schema for revenue impact analytics endpoint."""

    period_days: int = Field(..., description="Rolling window in days")
    period_start: str = Field(..., description="Period start (ISO 8601)")
    period_end: str = Field(..., description="Period end (ISO 8601)")
    total_interactions_analyzed: int = Field(
        ..., description="Total interactions analyzed in the period",
    )

    # Core revenue metrics (roubles)
    revenue_at_risk_monthly: float = Field(
        ..., description="Monthly revenue potentially lost from unresolved negatives (roubles)",
    )
    revenue_saved_monthly: float = Field(
        ..., description="Estimated revenue saved by responding to negatives within SLA (roubles)",
    )
    potential_additional_savings: float = Field(
        ..., description="Additional revenue that could be saved with full SLA coverage (roubles)",
    )
    question_revenue_impact: float = Field(
        ..., description="Estimated additional revenue from fast question responses (roubles)",
    )

    # Response time ROI
    response_time_roi_percent: float = Field(
        ..., description="Effective conversion boost percentage from fast responses",
    )

    # Breakdown counts
    negative_reviews: NegativeReviewBreakdown
    questions: QuestionBreakdown

    # Coefficients used in calculation
    coefficients: RevenueCoefficients
