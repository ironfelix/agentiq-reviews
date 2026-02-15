"""Tests for customer profile aggregation service."""

import os
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure app settings can be initialized for imported modules
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_customer_profile.db")

from app.database import Base
from app.models.customer_profile import CustomerProfile
from app.models.interaction import Interaction
from app.models.seller import Seller
from app.services import customer_profile_service

TEST_DB_PATH = Path("./test_customer_profile.db")


@pytest.fixture
async def db_session():
    """Create a fresh database session for each test."""
    db_url = "sqlite+aiosqlite:///./test_customer_profile.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        yield session

    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture
async def test_seller(db_session: AsyncSession):
    """Create a test seller."""
    seller = Seller(
        name="Test Store",
        email="test@example.com",
        password_hash="x",
        marketplace="wildberries",
        is_active=True,
    )
    db_session.add(seller)
    await db_session.flush()
    return seller


@pytest.mark.asyncio
async def test_get_or_create_new(db_session: AsyncSession, test_seller: Seller):
    """Test creating a new customer profile."""
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="new_customer_123",
        name="John Doe",
    )

    assert profile is not None
    assert profile.customer_id == "new_customer_123"
    assert profile.name == "John Doe"
    assert profile.seller_id == test_seller.id
    assert profile.marketplace == "wb"
    assert profile.total_interactions == 0
    assert profile.sentiment_trend == "neutral"


@pytest.mark.asyncio
async def test_get_or_create_existing(db_session: AsyncSession, test_seller: Seller):
    """Test getting an existing customer profile."""
    # Create first profile
    profile1 = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="existing_customer_789",
        name="Jane Smith",
    )
    await db_session.commit()
    profile1_id = profile1.id

    # Get same profile again
    profile2 = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="existing_customer_789",
    )

    assert profile2.id == profile1_id
    assert profile2.name == "Jane Smith"
    assert profile2.customer_id == "existing_customer_789"


@pytest.mark.asyncio
async def test_get_or_create_no_customer_id(db_session: AsyncSession, test_seller: Seller):
    """Test handling of interactions without customer_id."""
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id=None,
        name="Anonymous",
    )

    assert profile is not None
    assert profile.customer_id is None
    assert profile.name == "Anonymous"
    assert profile.id is None  # Not persisted


@pytest.mark.asyncio
async def test_update_from_review(db_session: AsyncSession, test_seller: Seller):
    """Test updating profile from a review interaction."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_review_001",
    )
    await db_session.commit()

    # Create review interaction
    interaction = Interaction(
        seller_id=test_seller.id,
        marketplace="wb",
        channel="review",
        external_id="review_001",
        customer_id="customer_review_001",
        rating=4,
        text="Good product",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(interaction)
    await db_session.commit()

    # Update profile
    updated_profile = await customer_profile_service.update_profile_from_interaction(
        db=db_session,
        profile=profile,
        interaction=interaction,
    )
    await db_session.commit()

    assert updated_profile.total_interactions == 1
    assert updated_profile.total_reviews == 1
    assert updated_profile.total_questions == 0
    assert updated_profile.total_chats == 0
    assert updated_profile.avg_rating == 4.0
    assert updated_profile.last_interaction_at is not None
    assert updated_profile.first_interaction_at is not None
    assert 4.0 in updated_profile.recent_sentiment_scores


@pytest.mark.asyncio
async def test_update_from_chat(db_session: AsyncSession, test_seller: Seller):
    """Test updating profile from a chat interaction (no rating)."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_chat_001",
    )
    await db_session.commit()

    # Create chat interaction
    interaction = Interaction(
        seller_id=test_seller.id,
        marketplace="wb",
        channel="chat",
        external_id="chat_001",
        customer_id="customer_chat_001",
        text="How do I return this?",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(interaction)
    await db_session.commit()

    # Update profile
    updated_profile = await customer_profile_service.update_profile_from_interaction(
        db=db_session,
        profile=profile,
        interaction=interaction,
    )
    await db_session.commit()

    assert updated_profile.total_interactions == 1
    assert updated_profile.total_chats == 1
    assert updated_profile.total_reviews == 0
    assert updated_profile.avg_rating is None  # No rating for chats


@pytest.mark.asyncio
async def test_sentiment_trend_declining(db_session: AsyncSession, test_seller: Seller):
    """Test sentiment trend calculation: declining."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_declining_001",
    )
    await db_session.commit()

    # Create 5 reviews: 5, 4, 3, 2, 1 (declining)
    ratings = [5, 4, 3, 2, 1]
    for i, rating in enumerate(ratings):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_decline_{i}",
            customer_id="customer_declining_001",
            rating=rating,
            text=f"Review {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    assert profile.sentiment_trend == "declining"
    assert profile.recent_sentiment_scores == [5.0, 4.0, 3.0, 2.0, 1.0]  # Last 5 (appended in order)


@pytest.mark.asyncio
async def test_sentiment_trend_improving(db_session: AsyncSession, test_seller: Seller):
    """Test sentiment trend calculation: improving."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_improving_001",
    )
    await db_session.commit()

    # Create reviews: 1, 2, 3, 4, 5 (improving)
    ratings = [1, 2, 3, 4, 5]
    for i, rating in enumerate(ratings):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_improve_{i}",
            customer_id="customer_improving_001",
            rating=rating,
            text=f"Review {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    assert profile.sentiment_trend == "improving"


@pytest.mark.asyncio
async def test_is_repeat_complainer(db_session: AsyncSession, test_seller: Seller):
    """Test is_repeat_complainer flag: 3+ reviews with rating <= 2."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_complainer_001",
    )
    await db_session.commit()

    # Create 3 negative reviews
    for i in range(3):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_negative_{i}",
            customer_id="customer_complainer_001",
            rating=1,
            text=f"Bad product {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    assert profile.is_repeat_complainer is True
    assert profile.total_reviews == 3


@pytest.mark.asyncio
async def test_customer_context_string(db_session: AsyncSession, test_seller: Seller):
    """Test customer context string generation."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_context_001",
        name="Alice Johnson",
    )
    await db_session.commit()

    # Add some interactions
    for i in range(3):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_context_{i}",
            customer_id="customer_context_001",
            rating=4,
            text=f"Review {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    # Get context string
    context = await customer_profile_service.get_customer_context_for_draft(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_context_001",
    )

    assert "Клиент: Alice Johnson" in context
    assert "Обращений: 3" in context
    assert "Средний рейтинг: 4.0" in context


@pytest.mark.asyncio
async def test_customer_context_unknown(db_session: AsyncSession, test_seller: Seller):
    """Test customer context for unknown customer (empty string)."""
    context = await customer_profile_service.get_customer_context_for_draft(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="nonexistent_customer",
    )

    assert context == ""


@pytest.mark.asyncio
async def test_customer_context_no_customer_id(db_session: AsyncSession, test_seller: Seller):
    """Test customer context when customer_id is None."""
    context = await customer_profile_service.get_customer_context_for_draft(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id=None,
    )

    assert context == ""


@pytest.mark.asyncio
async def test_refresh_profile(db_session: AsyncSession, test_seller: Seller):
    """Test full profile rebuild from all interactions."""
    customer_id = "customer_refresh_001"

    # Use a base time that's timezone-aware
    base_time = datetime.now(timezone.utc)

    # Create some interactions first
    interactions_data = [
        {"channel": "review", "rating": 5, "external_id": "r1"},
        {"channel": "review", "rating": 4, "external_id": "r2"},
        {"channel": "review", "rating": 1, "external_id": "r3"},
        {"channel": "question", "rating": None, "external_id": "q1"},
        {"channel": "chat", "rating": None, "external_id": "c1"},
    ]

    for i, data in enumerate(interactions_data):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel=data["channel"],
            external_id=data["external_id"],
            customer_id=customer_id,
            rating=data["rating"],
            text="Test message",
            occurred_at=base_time + timedelta(hours=i),
            created_at=base_time + timedelta(hours=i),  # Explicitly set created_at to avoid timezone issues
        )
        db_session.add(interaction)
    await db_session.commit()

    # Refresh profile
    profile = await customer_profile_service.refresh_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id=customer_id,
    )
    await db_session.commit()

    assert profile.total_interactions == 5
    assert profile.total_reviews == 3
    assert profile.total_questions == 1
    assert profile.total_chats == 1
    # avg_rating = (5 + 4 + 1) / 3 = 3.33...
    assert profile.avg_rating is not None
    assert abs(profile.avg_rating - 3.33) < 0.01
    assert len(profile.recent_sentiment_scores) == 3  # Only reviews have ratings


@pytest.mark.asyncio
async def test_avg_rating_calculation(db_session: AsyncSession, test_seller: Seller):
    """Test average rating calculation with multiple reviews."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_avg_rating_001",
    )
    await db_session.commit()

    # Add reviews with different ratings
    ratings = [5, 4, 3, 4, 5]
    for i, rating in enumerate(ratings):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_avg_{i}",
            customer_id="customer_avg_rating_001",
            rating=rating,
            text=f"Review {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    # avg = (5 + 4 + 3 + 4 + 5) / 5 = 4.2
    assert profile.avg_rating is not None
    assert abs(profile.avg_rating - 4.2) < 0.01


@pytest.mark.asyncio
async def test_sentiment_trend_stable(db_session: AsyncSession, test_seller: Seller):
    """Test sentiment trend: stable (small fluctuations)."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_stable_001",
    )
    await db_session.commit()

    # Create reviews: 4, 4, 4, 4 (stable)
    ratings = [4, 4, 4, 4]
    for i, rating in enumerate(ratings):
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wb",
            channel="review",
            external_id=f"review_stable_{i}",
            customer_id="customer_stable_001",
            rating=rating,
            text=f"Review {i}",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=i),
        )
        db_session.add(interaction)
        await db_session.commit()

        profile = await customer_profile_service.update_profile_from_interaction(
            db=db_session,
            profile=profile,
            interaction=interaction,
        )
        await db_session.commit()

    assert profile.sentiment_trend == "stable"


@pytest.mark.asyncio
async def test_sentiment_trend_neutral_few_scores(db_session: AsyncSession, test_seller: Seller):
    """Test sentiment trend: neutral when < 2 scores."""
    # Create profile
    profile = await customer_profile_service.get_or_create_profile(
        db=db_session,
        seller_id=test_seller.id,
        marketplace="wb",
        customer_id="customer_neutral_001",
    )
    await db_session.commit()

    # Only 1 review
    interaction = Interaction(
        seller_id=test_seller.id,
        marketplace="wb",
        channel="review",
        external_id="review_neutral_1",
        customer_id="customer_neutral_001",
        rating=5,
        text="Review",
        occurred_at=datetime.now(timezone.utc),
    )
    db_session.add(interaction)
    await db_session.commit()

    profile = await customer_profile_service.update_profile_from_interaction(
        db=db_session,
        profile=profile,
        interaction=interaction,
    )
    await db_session.commit()

    assert profile.sentiment_trend == "neutral"
