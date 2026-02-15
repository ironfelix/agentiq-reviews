"""Revenue impact analytics for seller communication quality.

Calculates monetary impact (in roubles) of communication quality,
helping sellers understand the ROI of using AgentIQ.

Key metrics:
- Revenue at Risk: monthly revenue potentially lost from unresolved negatives
- Revenue Saved: estimated revenue saved by timely responses to negatives
- Response Time ROI: impact of fast response on conversion
- Potential Additional Savings: what could be saved with better coverage
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent

# ---------------------------------------------------------------------------
# Default coefficients (can be overridden per-seller in the future)
# ---------------------------------------------------------------------------
DEFAULT_AVG_ORDER_VALUE: float = 2000.0  # roubles
CONVERSION_DROP_PER_STAR: float = 0.10  # 10% drop per star below 5
NEGATIVE_SAVE_RATE: float = 0.20  # 20% chance of saving a negative review
FAST_RESPONSE_CONVERSION_BOOST: float = 0.20  # +20% conversions with fast response
REPEAT_PURCHASE_FACTOR: float = 1.5  # saved customer buys ~1.5x over lifetime
SLA_THRESHOLD_MINUTES: int = 60  # 1 hour SLA for negative reviews


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


async def _count_negative_interactions(
    db: AsyncSession,
    *,
    seller_id: int,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, int]:
    """Count negative (1-2 star) interactions by response status.

    Returns dict with keys:
    - negative_total: all 1-2 star interactions in the period
    - negative_responded: those with status='responded'
    - negative_unresolved: those still needing response
    - negative_responded_in_sla: responded within SLA_THRESHOLD_MINUTES
    """
    time_filter = func.coalesce(Interaction.occurred_at, Interaction.created_at)

    base_conditions = [
        Interaction.seller_id == seller_id,
        Interaction.channel == "review",
        Interaction.rating.isnot(None),
        Interaction.rating <= 2,
        time_filter >= start_at,
        time_filter <= end_at,
    ]

    stmt = select(
        func.count().label("negative_total"),
        func.sum(
            case((Interaction.status == "responded", 1), else_=0)
        ).label("negative_responded"),
        func.sum(
            case((Interaction.needs_response.is_(True), 1), else_=0)
        ).label("negative_unresolved"),
    ).where(and_(*base_conditions))

    result = await db.execute(stmt)
    row = result.one()

    negative_total = int(row.negative_total or 0)
    negative_responded = int(row.negative_responded or 0)
    negative_unresolved = int(row.negative_unresolved or 0)

    # Count responded-in-SLA: interactions that have reply events within SLA_THRESHOLD_MINUTES
    # We approximate by checking interaction events with type 'reply_sent'
    # and comparing event time to interaction occurred_at.
    sla_stmt = (
        select(func.count(func.distinct(InteractionEvent.interaction_id)))
        .join(Interaction, InteractionEvent.interaction_id == Interaction.id)
        .where(
            and_(
                Interaction.seller_id == seller_id,
                Interaction.channel == "review",
                Interaction.rating.isnot(None),
                Interaction.rating <= 2,
                time_filter >= start_at,
                time_filter <= end_at,
                InteractionEvent.event_type == "reply_sent",
                # SLA check: event created within SLA_THRESHOLD_MINUTES of interaction
                InteractionEvent.created_at <= func.coalesce(
                    Interaction.occurred_at, Interaction.created_at
                ) + timedelta(minutes=SLA_THRESHOLD_MINUTES),
            )
        )
    )

    try:
        sla_result = await db.execute(sla_stmt)
        negative_responded_in_sla = int(sla_result.scalar_one() or 0)
    except Exception:
        # Fallback: if datetime arithmetic not supported (e.g. SQLite),
        # estimate as fraction of responded.
        negative_responded_in_sla = int(negative_responded * 0.5)

    return {
        "negative_total": negative_total,
        "negative_responded": negative_responded,
        "negative_unresolved": negative_unresolved,
        "negative_responded_in_sla": negative_responded_in_sla,
    }


async def _count_questions_answered_fast(
    db: AsyncSession,
    *,
    seller_id: int,
    start_at: datetime,
    end_at: datetime,
) -> dict[str, int]:
    """Count pre-purchase questions and those answered fast (within SLA).

    Returns dict with keys:
    - questions_total: all questions in the period
    - questions_responded: those with status='responded'
    - questions_responded_fast: responded within SLA_THRESHOLD_MINUTES
    """
    time_filter = func.coalesce(Interaction.occurred_at, Interaction.created_at)

    base_conditions = [
        Interaction.seller_id == seller_id,
        Interaction.channel == "question",
        time_filter >= start_at,
        time_filter <= end_at,
    ]

    stmt = select(
        func.count().label("questions_total"),
        func.sum(
            case((Interaction.status == "responded", 1), else_=0)
        ).label("questions_responded"),
    ).where(and_(*base_conditions))

    result = await db.execute(stmt)
    row = result.one()

    questions_total = int(row.questions_total or 0)
    questions_responded = int(row.questions_responded or 0)

    # Estimate fast responses via interaction events
    sla_stmt = (
        select(func.count(func.distinct(InteractionEvent.interaction_id)))
        .join(Interaction, InteractionEvent.interaction_id == Interaction.id)
        .where(
            and_(
                Interaction.seller_id == seller_id,
                Interaction.channel == "question",
                time_filter >= start_at,
                time_filter <= end_at,
                InteractionEvent.event_type == "reply_sent",
                InteractionEvent.created_at <= func.coalesce(
                    Interaction.occurred_at, Interaction.created_at
                ) + timedelta(minutes=SLA_THRESHOLD_MINUTES),
            )
        )
    )

    try:
        sla_result = await db.execute(sla_stmt)
        questions_responded_fast = int(sla_result.scalar_one() or 0)
    except Exception:
        questions_responded_fast = int(questions_responded * 0.5)

    return {
        "questions_total": questions_total,
        "questions_responded": questions_responded,
        "questions_responded_fast": questions_responded_fast,
    }


async def _count_total_interactions(
    db: AsyncSession,
    *,
    seller_id: int,
    start_at: datetime,
    end_at: datetime,
) -> int:
    """Count all interactions in the period."""
    time_filter = func.coalesce(Interaction.occurred_at, Interaction.created_at)
    stmt = (
        select(func.count())
        .select_from(Interaction)
        .where(
            and_(
                Interaction.seller_id == seller_id,
                time_filter >= start_at,
                time_filter <= end_at,
            )
        )
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_revenue_impact(
    db: AsyncSession,
    seller_id: int,
    period_days: int = 30,
    avg_order_value: Optional[float] = None,
    conversion_drop_per_star: Optional[float] = None,
    negative_save_rate: Optional[float] = None,
    fast_response_conversion_boost: Optional[float] = None,
    repeat_purchase_factor: Optional[float] = None,
) -> dict[str, Any]:
    """Calculate revenue impact metrics for a seller.

    Args:
        db: Async database session.
        seller_id: Seller to compute metrics for.
        period_days: Rolling window in days (default 30).
        avg_order_value: Average order value in roubles (default 2000).
        conversion_drop_per_star: Fraction of conversion lost per star below 5 (default 0.10).
        negative_save_rate: Probability of saving a negative review by fast response (default 0.20).
        fast_response_conversion_boost: Conversion boost from fast response to questions (default 0.20).
        repeat_purchase_factor: Lifetime multiplier for saved customers (default 1.5).

    Returns:
        dict with all computed revenue impact metrics.
    """
    # Apply defaults
    aov = avg_order_value if avg_order_value is not None else DEFAULT_AVG_ORDER_VALUE
    conv_drop = conversion_drop_per_star if conversion_drop_per_star is not None else CONVERSION_DROP_PER_STAR
    save_rate = negative_save_rate if negative_save_rate is not None else NEGATIVE_SAVE_RATE
    fast_boost = fast_response_conversion_boost if fast_response_conversion_boost is not None else FAST_RESPONSE_CONVERSION_BOOST
    repeat_factor = repeat_purchase_factor if repeat_purchase_factor is not None else REPEAT_PURCHASE_FACTOR

    now = datetime.now(timezone.utc)
    period = max(1, period_days)
    start_at = now - timedelta(days=period)

    # Gather raw counts
    neg_counts = await _count_negative_interactions(
        db, seller_id=seller_id, start_at=start_at, end_at=now,
    )
    q_counts = await _count_questions_answered_fast(
        db, seller_id=seller_id, start_at=start_at, end_at=now,
    )
    total_interactions = await _count_total_interactions(
        db, seller_id=seller_id, start_at=start_at, end_at=now,
    )

    # -----------------------------------------------------------------------
    # 1. Revenue at Risk
    # Each unresolved negative review (1-2 stars) represents a potential
    # rating drop that reduces conversion. Avg star impact for 1-2 star
    # reviews is ~3.5 stars below 5 (midpoint of 1 and 2 is 1.5, delta = 3.5).
    # But we use a simpler model: each negative review costs
    # avg_order_value * conversion_drop * rating_severity_weight.
    #
    # rating_severity_weight: 1-star = 1.0, 2-star = 0.6 (less severe)
    # We use the average weight of 0.8 as approximation since we don't
    # have per-rating breakdown here.
    # -----------------------------------------------------------------------
    avg_severity_weight = 0.8
    revenue_at_risk = round(
        neg_counts["negative_unresolved"] * aov * conv_drop * avg_severity_weight,
        2,
    )

    # -----------------------------------------------------------------------
    # 2. Revenue Saved
    # Responding to a negative review within SLA has save_rate probability
    # of the customer updating their review (1-star -> 5-star).
    # Saved customer value = aov * repeat_purchase_factor.
    # -----------------------------------------------------------------------
    revenue_saved = round(
        neg_counts["negative_responded_in_sla"] * aov * save_rate * repeat_factor,
        2,
    )

    # -----------------------------------------------------------------------
    # 3. Potential Additional Savings
    # What revenue could be saved if ALL negative reviews were responded
    # to within SLA (vs current coverage).
    # -----------------------------------------------------------------------
    neg_not_in_sla = neg_counts["negative_total"] - neg_counts["negative_responded_in_sla"]
    potential_additional_savings = round(
        max(0, neg_not_in_sla) * aov * save_rate * repeat_factor,
        2,
    )

    # -----------------------------------------------------------------------
    # 4. Response Time ROI (%)
    # WB stat: +20% conversion when answering within 1 hour.
    # We calculate the effective conversion boost as:
    #   fast_response_rate * fast_response_conversion_boost * 100
    # -----------------------------------------------------------------------
    questions_total = q_counts["questions_total"]
    questions_responded_fast = q_counts["questions_responded_fast"]
    fast_response_rate = _safe_divide(questions_responded_fast, questions_total)
    response_time_roi_percent = round(fast_response_rate * fast_boost * 100, 2)

    # -----------------------------------------------------------------------
    # 5. Question conversion value
    # Questions answered fast lead to conversion boost.
    # Estimated additional revenue from fast question responses.
    # -----------------------------------------------------------------------
    question_revenue_impact = round(
        questions_responded_fast * aov * fast_boost,
        2,
    )

    return {
        "period_days": period,
        "period_start": start_at.isoformat(),
        "period_end": now.isoformat(),
        "total_interactions_analyzed": total_interactions,

        # Core revenue metrics (roubles)
        "revenue_at_risk_monthly": revenue_at_risk,
        "revenue_saved_monthly": revenue_saved,
        "potential_additional_savings": potential_additional_savings,
        "question_revenue_impact": question_revenue_impact,

        # Response time
        "response_time_roi_percent": response_time_roi_percent,

        # Breakdown counts
        "negative_reviews": {
            "total": neg_counts["negative_total"],
            "responded": neg_counts["negative_responded"],
            "unresolved": neg_counts["negative_unresolved"],
            "responded_in_sla": neg_counts["negative_responded_in_sla"],
        },
        "questions": {
            "total": q_counts["questions_total"],
            "responded": q_counts["questions_responded"],
            "responded_fast": q_counts["questions_responded_fast"],
        },

        # Coefficients used
        "coefficients": {
            "avg_order_value": aov,
            "conversion_drop_per_star": conv_drop,
            "negative_save_rate": save_rate,
            "fast_response_conversion_boost": fast_boost,
            "repeat_purchase_factor": repeat_factor,
            "sla_threshold_minutes": SLA_THRESHOLD_MINUTES,
        },
    }
