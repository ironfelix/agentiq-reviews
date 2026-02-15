"""Tests for revenue impact analytics service."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure app settings can be initialized for imported modules.
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_revenue_analytics.db")

from app.database import Base
from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent
from app.models.seller import Seller
from app.services.interaction_metrics import record_reply_events
from app.services.revenue_analytics import get_revenue_impact

TEST_DB_PATH = Path("./test_revenue_analytics.db")


async def _make_engine_and_session():
    """Create a fresh SQLite engine + session factory for isolated tests."""
    db_url = "sqlite+aiosqlite:///./test_revenue_analytics.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    return engine, session_factory


async def _cleanup(engine):
    """Drop tables and dispose engine."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_revenue_impact_with_mixed_interactions():
    """Test revenue calculation with a mix of negative, positive reviews and questions."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Revenue Test Seller",
                email="revenue-test@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.flush()

            now = datetime.now(timezone.utc)

            # Negative review - unresolved (needs_response=True)
            neg_unresolved = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="review",
                external_id="rev-neg-1",
                text="Terrible product, broke on day 1",
                rating=1,
                status="open",
                priority="high",
                needs_response=True,
                source="wb_api",
                occurred_at=now - timedelta(days=5),
            )

            # Negative review - responded (within SLA)
            neg_responded = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="review",
                external_id="rev-neg-2",
                text="Poor quality, not what I expected",
                rating=2,
                status="responded",
                priority="low",
                needs_response=False,
                source="wb_api",
                occurred_at=now - timedelta(days=10),
            )

            # Positive review (should NOT count in negative metrics)
            pos_review = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="review",
                external_id="rev-pos-1",
                text="Great product!",
                rating=5,
                status="responded",
                priority="low",
                needs_response=False,
                source="wb_api",
                occurred_at=now - timedelta(days=3),
            )

            # Question - responded
            question_responded = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="question",
                external_id="q-1",
                text="What size should I get?",
                status="responded",
                priority="high",
                needs_response=False,
                source="wb_api",
                occurred_at=now - timedelta(days=2),
            )

            # Question - unresponded
            question_open = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="question",
                external_id="q-2",
                text="Is this compatible with X?",
                status="open",
                priority="normal",
                needs_response=True,
                source="wb_api",
                occurred_at=now - timedelta(days=1),
            )

            db.add_all([neg_unresolved, neg_responded, pos_review, question_responded, question_open])
            await db.flush()

            # Record reply event for responded negative (simulates a reply)
            record_reply_events(db=db, interaction=neg_responded, reply_text="We are sorry!")
            record_reply_events(db=db, interaction=question_responded, reply_text="Size M fits.")

            await db.commit()

            # Run revenue impact calculation
            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
                avg_order_value=2000.0,
            )

            # Validate structure
            assert "revenue_at_risk_monthly" in result
            assert "revenue_saved_monthly" in result
            assert "potential_additional_savings" in result
            assert "question_revenue_impact" in result
            assert "response_time_roi_percent" in result
            assert "negative_reviews" in result
            assert "questions" in result
            assert "coefficients" in result

            # Validate negative review counts
            assert result["negative_reviews"]["total"] == 2
            assert result["negative_reviews"]["responded"] == 1
            assert result["negative_reviews"]["unresolved"] == 1

            # Validate question counts
            assert result["questions"]["total"] == 2
            assert result["questions"]["responded"] == 1

            # Revenue at risk should be > 0 (1 unresolved negative)
            assert result["revenue_at_risk_monthly"] > 0

            # Total interactions should include all 5
            assert result["total_interactions_analyzed"] == 5

            # Period
            assert result["period_days"] == 30

            # Coefficients should match defaults
            assert result["coefficients"]["avg_order_value"] == 2000.0
            assert result["coefficients"]["sla_threshold_minutes"] == 60

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_no_interactions():
    """Edge case: seller with no interactions should return zero metrics."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Empty Seller",
                email="empty-seller@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
            )

            assert result["total_interactions_analyzed"] == 0
            assert result["revenue_at_risk_monthly"] == 0.0
            assert result["revenue_saved_monthly"] == 0.0
            assert result["potential_additional_savings"] == 0.0
            assert result["question_revenue_impact"] == 0.0
            assert result["response_time_roi_percent"] == 0.0
            assert result["negative_reviews"]["total"] == 0
            assert result["negative_reviews"]["unresolved"] == 0
            assert result["questions"]["total"] == 0

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_all_positive():
    """Edge case: all positive reviews (3-5 stars), no negatives."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Happy Seller",
                email="happy-seller@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.flush()

            now = datetime.now(timezone.utc)
            interactions = []
            for i in range(5):
                interactions.append(
                    Interaction(
                        seller_id=seller.id,
                        marketplace="wildberries",
                        channel="review",
                        external_id=f"rev-pos-{i}",
                        text=f"Great product #{i}",
                        rating=5 - (i % 3),  # ratings 5, 4, 3, 5, 4
                        status="responded",
                        priority="low",
                        needs_response=False,
                        source="wb_api",
                        occurred_at=now - timedelta(days=i + 1),
                    )
                )
            db.add_all(interactions)
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
            )

            assert result["total_interactions_analyzed"] == 5
            assert result["revenue_at_risk_monthly"] == 0.0
            assert result["revenue_saved_monthly"] == 0.0
            assert result["potential_additional_savings"] == 0.0
            assert result["negative_reviews"]["total"] == 0
            assert result["negative_reviews"]["unresolved"] == 0

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_all_negative_unresolved():
    """Edge case: all negative reviews (1-2 stars), none responded."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Struggling Seller",
                email="struggling@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.flush()

            now = datetime.now(timezone.utc)
            interactions = []
            for i in range(10):
                interactions.append(
                    Interaction(
                        seller_id=seller.id,
                        marketplace="wildberries",
                        channel="review",
                        external_id=f"rev-neg-{i}",
                        text=f"Terrible product #{i}",
                        rating=1 + (i % 2),  # alternating 1 and 2
                        status="open",
                        priority="high",
                        needs_response=True,
                        source="wb_api",
                        occurred_at=now - timedelta(days=i + 1),
                    )
                )
            db.add_all(interactions)
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
                avg_order_value=3000.0,
            )

            assert result["negative_reviews"]["total"] == 10
            assert result["negative_reviews"]["unresolved"] == 10
            assert result["negative_reviews"]["responded"] == 0
            assert result["negative_reviews"]["responded_in_sla"] == 0

            # Revenue at risk = 10 * 3000 * 0.10 * 0.8 = 2400.0
            assert result["revenue_at_risk_monthly"] == 2400.0

            # Revenue saved = 0 (no responses)
            assert result["revenue_saved_monthly"] == 0.0

            # Potential savings = 10 * 3000 * 0.20 * 1.5 = 9000.0
            assert result["potential_additional_savings"] == 9000.0

            # Custom avg_order_value passed through
            assert result["coefficients"]["avg_order_value"] == 3000.0

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_period_filtering():
    """Interactions outside the period should not be counted."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Period Filter Seller",
                email="period-filter@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.flush()

            now = datetime.now(timezone.utc)

            # Recent negative (within 7 days)
            recent_neg = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="review",
                external_id="rev-recent",
                text="Bad product",
                rating=1,
                status="open",
                priority="high",
                needs_response=True,
                source="wb_api",
                occurred_at=now - timedelta(days=3),
            )

            # Old negative (60 days ago - outside 7 day window)
            old_neg = Interaction(
                seller_id=seller.id,
                marketplace="wildberries",
                channel="review",
                external_id="rev-old",
                text="Bad product from long ago",
                rating=1,
                status="open",
                priority="high",
                needs_response=True,
                source="wb_api",
                occurred_at=now - timedelta(days=60),
            )

            db.add_all([recent_neg, old_neg])
            await db.commit()

            # Query with 7-day window
            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=7,
            )

            # Only the recent one should be counted
            assert result["negative_reviews"]["total"] == 1
            assert result["negative_reviews"]["unresolved"] == 1
            assert result["total_interactions_analyzed"] == 1
            assert result["period_days"] == 7

            # Query with 90-day window - both should count
            result_wide = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=90,
            )
            assert result_wide["negative_reviews"]["total"] == 2
            assert result_wide["total_interactions_analyzed"] == 2

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_custom_coefficients():
    """Custom coefficients should be properly applied."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Custom Coeff Seller",
                email="custom-coeff@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.flush()

            now = datetime.now(timezone.utc)

            # 5 unresolved negatives
            for i in range(5):
                db.add(
                    Interaction(
                        seller_id=seller.id,
                        marketplace="wildberries",
                        channel="review",
                        external_id=f"rev-custom-{i}",
                        text=f"Bad #{i}",
                        rating=1,
                        status="open",
                        priority="high",
                        needs_response=True,
                        source="wb_api",
                        occurred_at=now - timedelta(days=i + 1),
                    )
                )
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
                avg_order_value=5000.0,
                conversion_drop_per_star=0.15,
                negative_save_rate=0.30,
                fast_response_conversion_boost=0.25,
                repeat_purchase_factor=2.0,
            )

            assert result["coefficients"]["avg_order_value"] == 5000.0
            assert result["coefficients"]["conversion_drop_per_star"] == 0.15
            assert result["coefficients"]["negative_save_rate"] == 0.30
            assert result["coefficients"]["fast_response_conversion_boost"] == 0.25
            assert result["coefficients"]["repeat_purchase_factor"] == 2.0

            # Revenue at risk = 5 * 5000 * 0.15 * 0.8 = 3000.0
            assert result["revenue_at_risk_monthly"] == 3000.0

            # Potential savings = 5 * 5000 * 0.30 * 2.0 = 15000.0
            assert result["potential_additional_savings"] == 15000.0

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_seller_isolation():
    """Metrics for one seller should not include another seller's interactions."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller_a = Seller(
                name="Seller A",
                email="seller-a@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            seller_b = Seller(
                name="Seller B",
                email="seller-b@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add_all([seller_a, seller_b])
            await db.flush()

            now = datetime.now(timezone.utc)

            # Seller A: 3 negative reviews
            for i in range(3):
                db.add(
                    Interaction(
                        seller_id=seller_a.id,
                        marketplace="wildberries",
                        channel="review",
                        external_id=f"rev-a-{i}",
                        text=f"Bad A #{i}",
                        rating=1,
                        status="open",
                        priority="high",
                        needs_response=True,
                        source="wb_api",
                        occurred_at=now - timedelta(days=i + 1),
                    )
                )

            # Seller B: 7 negative reviews
            for i in range(7):
                db.add(
                    Interaction(
                        seller_id=seller_b.id,
                        marketplace="wildberries",
                        channel="review",
                        external_id=f"rev-b-{i}",
                        text=f"Bad B #{i}",
                        rating=2,
                        status="open",
                        priority="high",
                        needs_response=True,
                        source="wb_api",
                        occurred_at=now - timedelta(days=i + 1),
                    )
                )

            await db.commit()

            result_a = await get_revenue_impact(db=db, seller_id=seller_a.id, period_days=30)
            result_b = await get_revenue_impact(db=db, seller_id=seller_b.id, period_days=30)

            assert result_a["negative_reviews"]["total"] == 3
            assert result_a["total_interactions_analyzed"] == 3
            assert result_b["negative_reviews"]["total"] == 7
            assert result_b["total_interactions_analyzed"] == 7

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_response_schema_validation():
    """Verify the response can be validated by the Pydantic schema."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Schema Test Seller",
                email="schema-test@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=30,
            )

            # Import schema and validate
            from app.schemas.analytics import RevenueImpactResponse
            response = RevenueImpactResponse(**result)

            assert response.period_days == 30
            assert response.revenue_at_risk_monthly == 0.0
            assert response.coefficients.avg_order_value == 2000.0
            assert response.negative_reviews.total == 0
            assert response.questions.total == 0

    finally:
        await _cleanup(engine)


@pytest.mark.asyncio
async def test_revenue_impact_minimum_period():
    """Period of 0 or negative should be clamped to 1."""
    engine, session_factory = await _make_engine_and_session()

    try:
        async with session_factory() as db:
            seller = Seller(
                name="Min Period Seller",
                email="min-period@example.com",
                password_hash="x",
                marketplace="wildberries",
                is_active=True,
            )
            db.add(seller)
            await db.commit()

            result = await get_revenue_impact(
                db=db,
                seller_id=seller.id,
                period_days=0,
            )

            assert result["period_days"] == 1

    finally:
        await _cleanup(engine)
