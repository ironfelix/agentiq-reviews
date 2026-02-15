"""Customer profile aggregation service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_profile import CustomerProfile
from app.models.interaction import Interaction


def _calculate_sentiment_trend(scores: list[float]) -> str:
    """
    Calculate sentiment trend from recent scores.

    Args:
        scores: List of sentiment scores (e.g., ratings)

    Returns:
        "improving" | "declining" | "stable" | "neutral"
    """
    if len(scores) < 2:
        return "neutral"

    # Split into first half and second half
    mid = len(scores) // 2
    first_half = scores[:mid]
    second_half = scores[mid:]

    if not first_half or not second_half:
        return "neutral"

    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)

    diff = avg_second - avg_first

    if diff >= 1.0:
        return "improving"
    elif diff <= -1.0:
        return "declining"
    else:
        return "stable"


async def get_or_create_profile(
    db: AsyncSession,
    seller_id: int,
    marketplace: str,
    customer_id: Optional[str],
    name: Optional[str] = None,
) -> CustomerProfile:
    """
    Get existing customer profile or create new one.

    Args:
        db: Database session
        seller_id: Seller ID
        marketplace: Marketplace name
        customer_id: Customer ID (can be None)
        name: Customer name (optional)

    Returns:
        CustomerProfile instance
    """
    # If no customer_id, we can't track this customer
    if not customer_id:
        # Create anonymous profile (not persisted, just for context)
        profile = CustomerProfile(
            seller_id=seller_id,
            marketplace=marketplace,
            customer_id=None,
            name=name,
            total_interactions=0,
        )
        return profile

    # Try to find existing profile
    stmt = select(CustomerProfile).where(
        and_(
            CustomerProfile.seller_id == seller_id,
            CustomerProfile.marketplace == marketplace,
            CustomerProfile.customer_id == customer_id,
        )
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if profile:
        # Update name if provided and not set
        if name and not profile.name:
            profile.name = name
        return profile

    # Create new profile
    profile = CustomerProfile(
        seller_id=seller_id,
        marketplace=marketplace,
        customer_id=customer_id,
        name=name,
        total_interactions=0,
        total_reviews=0,
        total_questions=0,
        total_chats=0,
        sentiment_trend="neutral",
        recent_sentiment_scores=[],
        is_repeat_complainer=False,
        is_vip=False,
    )
    db.add(profile)
    await db.flush()  # Get ID without committing
    return profile


async def update_profile_from_interaction(
    db: AsyncSession,
    profile: CustomerProfile,
    interaction: Interaction,
) -> CustomerProfile:
    """
    Update customer profile based on new interaction.

    Args:
        db: Database session
        profile: CustomerProfile instance
        interaction: Interaction instance

    Returns:
        Updated CustomerProfile
    """
    # Skip anonymous profiles
    if not profile.customer_id or not profile.id:
        return profile

    # Increment counters
    profile.total_interactions += 1

    if interaction.channel == "review":
        profile.total_reviews += 1
    elif interaction.channel == "question":
        profile.total_questions += 1
    elif interaction.channel == "chat":
        profile.total_chats += 1

    # Update avg_rating if this is a review
    if interaction.channel == "review" and interaction.rating is not None:
        if profile.avg_rating is None:
            profile.avg_rating = float(interaction.rating)
        else:
            # Incremental average: avg_new = (avg_old * count_old + new_value) / count_new
            total_ratings = profile.total_reviews
            profile.avg_rating = (
                (profile.avg_rating * (total_ratings - 1)) + float(interaction.rating)
            ) / total_ratings

    # Update timestamps (normalize tz to avoid naive/aware comparison errors)
    interaction_time = interaction.occurred_at or interaction.created_at
    if interaction_time and interaction_time.tzinfo is None:
        interaction_time = interaction_time.replace(tzinfo=timezone.utc)
    if interaction_time:
        first = profile.first_interaction_at
        if first and first.tzinfo is None:
            first = first.replace(tzinfo=timezone.utc)
        if first is None or interaction_time < first:
            profile.first_interaction_at = interaction_time

        last = profile.last_interaction_at
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last is None or interaction_time > last:
            profile.last_interaction_at = interaction_time

    # Update sentiment scores (use rating as sentiment proxy)
    if interaction.rating is not None:
        recent_scores = profile.recent_sentiment_scores or []
        recent_scores.append(float(interaction.rating))
        # Keep only last 5 scores
        profile.recent_sentiment_scores = recent_scores[-5:]
        profile.sentiment_trend = _calculate_sentiment_trend(profile.recent_sentiment_scores)

    # Update flags
    # is_repeat_complainer: 3+ interactions with rating <= 2
    if profile.total_reviews >= 3:
        # Count negative reviews
        negative_count_stmt = select(func.count()).where(
            and_(
                Interaction.seller_id == profile.seller_id,
                Interaction.marketplace == profile.marketplace,
                Interaction.customer_id == profile.customer_id,
                Interaction.channel == "review",
                Interaction.rating <= 2,
            )
        )
        result = await db.execute(negative_count_stmt)
        negative_count = result.scalar_one()
        profile.is_repeat_complainer = negative_count >= 3

    profile.updated_at = datetime.now(timezone.utc)
    return profile


async def get_customer_context_for_draft(
    db: AsyncSession,
    seller_id: int,
    marketplace: str,
    customer_id: Optional[str],
) -> str:
    """
    Get customer context string for AI draft generation.

    Args:
        db: Database session
        seller_id: Seller ID
        marketplace: Marketplace name
        customer_id: Customer ID

    Returns:
        Context string (empty if profile not found)
    """
    if not customer_id:
        return ""

    stmt = select(CustomerProfile).where(
        and_(
            CustomerProfile.seller_id == seller_id,
            CustomerProfile.marketplace == marketplace,
            CustomerProfile.customer_id == customer_id,
        )
    )
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()

    if not profile:
        return ""

    # Build context string
    parts = []

    if profile.name:
        parts.append(f"Клиент: {profile.name}")
    else:
        parts.append("Клиент")

    parts.append(f"Обращений: {profile.total_interactions}")

    if profile.avg_rating is not None:
        parts.append(f"Средний рейтинг: {profile.avg_rating:.1f}")

    if profile.sentiment_trend and profile.sentiment_trend != "neutral":
        trend_map = {
            "improving": "улучшается",
            "declining": "ухудшается",
            "stable": "стабильный",
        }
        parts.append(f"Тренд: {trend_map.get(profile.sentiment_trend, profile.sentiment_trend)}")

    if profile.is_repeat_complainer:
        parts.append("(повторные жалобы)")

    return ". ".join(parts) + "."


async def refresh_profile(
    db: AsyncSession,
    seller_id: int,
    marketplace: str,
    customer_id: str,
) -> CustomerProfile:
    """
    Rebuild customer profile from all interactions (for rebuild/migration).

    Args:
        db: Database session
        seller_id: Seller ID
        marketplace: Marketplace name
        customer_id: Customer ID

    Returns:
        Refreshed CustomerProfile
    """
    # Get or create profile
    profile = await get_or_create_profile(db, seller_id, marketplace, customer_id)

    # Reset counters
    profile.total_interactions = 0
    profile.total_reviews = 0
    profile.total_questions = 0
    profile.total_chats = 0
    profile.avg_rating = None
    profile.first_interaction_at = None
    profile.last_interaction_at = None
    profile.recent_sentiment_scores = []
    profile.sentiment_trend = "neutral"
    profile.is_repeat_complainer = False
    profile.is_vip = False

    # Fetch all interactions for this customer
    stmt = (
        select(Interaction)
        .where(
            and_(
                Interaction.seller_id == seller_id,
                Interaction.marketplace == marketplace,
                Interaction.customer_id == customer_id,
            )
        )
        .order_by(Interaction.occurred_at.asc().nullsfirst(), Interaction.created_at.asc())
    )
    result = await db.execute(stmt)
    interactions = result.scalars().all()

    # Process each interaction
    for interaction in interactions:
        profile.total_interactions += 1

        if interaction.channel == "review":
            profile.total_reviews += 1
        elif interaction.channel == "question":
            profile.total_questions += 1
        elif interaction.channel == "chat":
            profile.total_chats += 1

        # Update avg_rating
        if interaction.channel == "review" and interaction.rating is not None:
            if profile.avg_rating is None:
                profile.avg_rating = float(interaction.rating)
            else:
                total_ratings = profile.total_reviews
                profile.avg_rating = (
                    (profile.avg_rating * (total_ratings - 1)) + float(interaction.rating)
                ) / total_ratings

        # Update timestamps (normalize tz to avoid naive/aware comparison errors)
        interaction_time = interaction.occurred_at or interaction.created_at
        if interaction_time and interaction_time.tzinfo is None:
            interaction_time = interaction_time.replace(tzinfo=timezone.utc)
        if interaction_time:
            first = profile.first_interaction_at
            if first and first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            if first is None or interaction_time < first:
                profile.first_interaction_at = interaction_time

            last = profile.last_interaction_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if last is None or interaction_time > last:
                profile.last_interaction_at = interaction_time

        # Collect sentiment scores (last 5 only)
        if interaction.rating is not None:
            recent_scores = profile.recent_sentiment_scores or []
            recent_scores.append(float(interaction.rating))
            profile.recent_sentiment_scores = recent_scores[-5:]

    # Calculate sentiment trend
    if profile.recent_sentiment_scores:
        profile.sentiment_trend = _calculate_sentiment_trend(profile.recent_sentiment_scores)

    # Update flags
    if profile.total_reviews >= 3:
        negative_count = sum(
            1
            for interaction in interactions
            if interaction.channel == "review" and interaction.rating and interaction.rating <= 2
        )
        profile.is_repeat_complainer = negative_count >= 3

    profile.updated_at = datetime.now(timezone.utc)
    return profile
