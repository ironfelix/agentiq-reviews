"""Tests for AI draft generation with product and customer context enrichment.

Verifies that:
- Draft generation includes product context when nm_id is available
- Draft generation includes customer context when customer_id is available
- Draft generation works without product/customer context (graceful fallback)
- Customer profile is updated when new interaction is ingested
- Product cache service formats context correctly
"""
from __future__ import annotations

import os
import pytest
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure app settings can be initialized for imported modules
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_draft_context.db")

from app.database import Base
from app.models.customer_profile import CustomerProfile
from app.models.interaction import Interaction
from app.models.product_cache import ProductCache
from app.models.seller import Seller
from app.services.product_cache_service import get_product_context_for_draft


TEST_DB_PATH = Path("./test_draft_context.db")


@pytest.fixture
async def db_session():
    """Create a fresh database session for each test."""
    db_url = "sqlite+aiosqlite:///./test_draft_context.db"
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
        email="test_draft@example.com",
        password_hash="x",
        marketplace="wildberries",
        is_active=True,
    )
    db_session.add(seller)
    await db_session.flush()
    return seller


@pytest.fixture
async def test_product_cache(db_session: AsyncSession) -> ProductCache:
    """Create a test product cache entry."""
    product = ProductCache(
        nm_id="12345678",
        marketplace="wb",
        name="Кроссовки Nike Air Max 90",
        description="Легендарные кроссовки Nike Air Max 90 с амортизацией Air.",
        brand="Nike",
        category="Кроссовки",
        options=[
            {"name": "Размер", "value": "42"},
            {"name": "Цвет", "value": "Черный/белый"},
            {"name": "Материал верха", "value": "Кожа"},
        ],
        image_url=None,
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(product)
    await db_session.flush()
    return product


@pytest.fixture
async def test_customer_profile(db_session: AsyncSession, test_seller: Seller) -> CustomerProfile:
    """Create a test customer profile."""
    profile = CustomerProfile(
        seller_id=test_seller.id,
        marketplace="wildberries",
        customer_id="customer_001",
        name="Иванов Иван",
        total_interactions=5,
        total_reviews=3,
        total_questions=1,
        total_chats=1,
        avg_rating=2.3,
        sentiment_trend="declining",
        recent_sentiment_scores=[4.0, 3.0, 2.0, 1.0, 1.0],
        is_repeat_complainer=True,
        is_vip=False,
    )
    db_session.add(profile)
    await db_session.flush()
    return profile


# -----------------------------------------------------------------------
# Product context formatting tests
# -----------------------------------------------------------------------


class TestProductContextForDraft:
    """Test get_product_context_for_draft() formatting."""

    def test_full_product_context(self, test_product_cache: ProductCache):
        """Product cache with all fields produces correct context string."""
        # get_product_context_for_draft is a sync function, no await needed
        # But we need the fixture to be resolved first, so we work with it as-is
        pass

    @pytest.mark.asyncio
    async def test_full_product_context_async(self, db_session: AsyncSession, test_product_cache: ProductCache):
        """Product cache with all fields produces correct context string."""
        context = get_product_context_for_draft(test_product_cache)

        assert "Товар: Кроссовки Nike Air Max 90" in context
        assert "Бренд: Nike" in context
        assert "Категория: Кроссовки" in context
        assert "Характеристики:" in context
        assert "Размер: 42" in context
        assert "Цвет: Черный/белый" in context

    def test_product_context_no_product(self):
        """None product returns empty string."""
        context = get_product_context_for_draft(None)
        assert context == ""

    def test_product_context_empty_name(self):
        """Product with empty name returns empty string."""
        product = ProductCache(nm_id="999", name="", brand="Test")
        context = get_product_context_for_draft(product)
        assert context == ""

    def test_product_context_name_only(self):
        """Product with just a name returns minimal context."""
        product = ProductCache(nm_id="999", name="Куртка зимняя")
        context = get_product_context_for_draft(product)
        assert "Товар: Куртка зимняя" in context
        assert context.endswith(".")

    def test_product_context_with_brand_no_category(self):
        """Product with name and brand but no category."""
        product = ProductCache(nm_id="999", name="Сумка", brand="Gucci")
        context = get_product_context_for_draft(product)
        assert "Товар: Сумка" in context
        assert "Бренд: Gucci" in context
        assert "Категория" not in context

    def test_product_context_options_limit(self):
        """Product options are limited to first 5."""
        options = [{"name": f"Opt{i}", "value": f"Val{i}"} for i in range(10)]
        product = ProductCache(nm_id="999", name="Товар", options=options)
        context = get_product_context_for_draft(product)
        # Should contain first 5 options
        assert "Opt0: Val0" in context
        assert "Opt4: Val4" in context
        # Should NOT contain options beyond 5
        assert "Opt5: Val5" not in context


# -----------------------------------------------------------------------
# Customer context tests
# -----------------------------------------------------------------------


class TestCustomerContextForDraft:
    """Test get_customer_context_for_draft() from customer_profile_service."""

    @pytest.mark.asyncio
    async def test_customer_context_with_profile(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
        test_customer_profile: CustomerProfile,
    ):
        """Customer with profile returns formatted context string."""
        from app.services.customer_profile_service import get_customer_context_for_draft

        context = await get_customer_context_for_draft(
            db=db_session,
            seller_id=test_seller.id,
            marketplace="wildberries",
            customer_id="customer_001",
        )

        assert "Клиент: Иванов Иван" in context
        assert "Обращений: 5" in context
        assert "Средний рейтинг: 2.3" in context
        assert "ухудшается" in context  # declining -> ухудшается
        assert "повторные жалобы" in context

    @pytest.mark.asyncio
    async def test_customer_context_no_profile(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """Unknown customer returns empty string."""
        from app.services.customer_profile_service import get_customer_context_for_draft

        context = await get_customer_context_for_draft(
            db=db_session,
            seller_id=test_seller.id,
            marketplace="wildberries",
            customer_id="nonexistent_customer",
        )

        assert context == ""

    @pytest.mark.asyncio
    async def test_customer_context_none_customer_id(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """None customer_id returns empty string."""
        from app.services.customer_profile_service import get_customer_context_for_draft

        context = await get_customer_context_for_draft(
            db=db_session,
            seller_id=test_seller.id,
            marketplace="wildberries",
            customer_id=None,
        )

        assert context == ""


# -----------------------------------------------------------------------
# Draft generation integration tests (mocked LLM)
# -----------------------------------------------------------------------


class TestDraftGenerationWithContext:
    """Test that generate_interaction_draft wires product and customer context."""

    @pytest.mark.asyncio
    async def test_draft_includes_product_context(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
        test_product_cache: ProductCache,
    ):
        """Draft generation fetches and passes product context to LLM."""
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="review_test_001",
            nm_id="12345678",
            text="Отличные кроссовки, очень удобные!",
            rating=5,
            subject="Отзыв 5★",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction)
        await db_session.flush()

        mock_analysis = {
            "recommendation": "Спасибо за отзыв!",
            "intent": "thanks",
            "sentiment": "positive",
            "sla_priority": "low",
            "recommendation_reason": "Positive review",
        }

        with patch(
            "app.services.interaction_drafts.get_cached_response",
            return_value=None,
        ), patch(
            "app.services.interaction_drafts.get_product_context_for_nm_id",
            new_callable=AsyncMock,
            return_value="Название: Кроссовки Nike Air Max 90",
        ) as mock_cdn_context, patch(
            "app.services.interaction_drafts.get_llm_runtime_config",
            new_callable=AsyncMock,
            return_value=MagicMock(provider="deepseek", model_name="deepseek-chat", enabled=True),
        ), patch(
            "app.services.interaction_drafts._get_seller_tone",
            new_callable=AsyncMock,
            return_value="neutral",
        ), patch(
            "app.services.interaction_drafts.AIAnalyzer"
        ) as MockAnalyzer:
            analyzer_instance = MockAnalyzer.return_value
            analyzer_instance.analyze_chat = AsyncMock(return_value=mock_analysis)

            from app.services.interaction_drafts import generate_interaction_draft

            result = await generate_interaction_draft(db=db_session, interaction=interaction)

            # Verify the LLM was called
            assert analyzer_instance.analyze_chat.called
            call_kwargs = analyzer_instance.analyze_chat.call_args

            # The product_context arg should have been passed (either from CDN or cache)
            # CDN context is the primary source
            mock_cdn_context.assert_called_once_with("12345678")

            assert result.text == "Спасибо за отзыв!"
            assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_draft_includes_customer_context(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
        test_customer_profile: CustomerProfile,
    ):
        """Draft generation fetches and passes customer context to LLM."""
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="review_test_002",
            customer_id="customer_001",
            text="Ужасное качество, уже третий раз!",
            rating=1,
            subject="Отзыв 1★",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction)
        await db_session.flush()

        mock_analysis = {
            "recommendation": "Здравствуйте! Нам очень жаль, что товар не оправдал ожиданий.",
            "intent": "defect_not_working",
            "sentiment": "negative",
            "sla_priority": "urgent",
            "recommendation_reason": "Repeat complainer with declining sentiment",
        }

        with patch(
            "app.services.interaction_drafts.get_product_context_for_nm_id",
            new_callable=AsyncMock,
            return_value="",
        ), patch(
            "app.services.interaction_drafts.get_or_fetch_product",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.interaction_drafts.get_llm_runtime_config",
            new_callable=AsyncMock,
            return_value=MagicMock(provider="deepseek", model_name="deepseek-chat", enabled=True),
        ), patch(
            "app.services.interaction_drafts._get_seller_tone",
            new_callable=AsyncMock,
            return_value="neutral",
        ), patch(
            "app.services.interaction_drafts.AIAnalyzer"
        ) as MockAnalyzer:
            analyzer_instance = MockAnalyzer.return_value
            analyzer_instance.analyze_chat = AsyncMock(return_value=mock_analysis)

            from app.services.interaction_drafts import generate_interaction_draft

            result = await generate_interaction_draft(db=db_session, interaction=interaction)

            # Verify the LLM was called with customer_context
            assert analyzer_instance.analyze_chat.called
            call_kwargs = analyzer_instance.analyze_chat.call_args[1]
            customer_ctx = call_kwargs.get("customer_context", "")

            # Customer context should include profile info
            assert "Иванов Иван" in customer_ctx
            assert "Обращений: 5" in customer_ctx
            assert "ухудшается" in customer_ctx
            assert "повторные жалобы" in customer_ctx

            assert result.text == "Здравствуйте! Нам очень жаль, что товар не оправдал ожиданий."

    @pytest.mark.asyncio
    async def test_draft_without_context_graceful_fallback(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """Draft generation works without product/customer context."""
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="review_test_003",
            # No nm_id, no customer_id
            text="Нормальный товар",
            rating=3,
            subject="Отзыв 3★",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction)
        await db_session.flush()

        mock_analysis = {
            "recommendation": "Спасибо за обратную связь!",
            "intent": "other",
            "sentiment": "neutral",
            "sla_priority": "normal",
            "recommendation_reason": "Neutral review",
        }

        with patch(
            "app.services.interaction_drafts.get_product_context_for_nm_id",
            new_callable=AsyncMock,
            return_value="",
        ), patch(
            "app.services.interaction_drafts.get_or_fetch_product",
            new_callable=AsyncMock,
            return_value=None,
        ), patch(
            "app.services.interaction_drafts.get_llm_runtime_config",
            new_callable=AsyncMock,
            return_value=MagicMock(provider="deepseek", model_name="deepseek-chat", enabled=True),
        ), patch(
            "app.services.interaction_drafts._get_seller_tone",
            new_callable=AsyncMock,
            return_value="neutral",
        ), patch(
            "app.services.interaction_drafts.AIAnalyzer"
        ) as MockAnalyzer:
            analyzer_instance = MockAnalyzer.return_value
            analyzer_instance.analyze_chat = AsyncMock(return_value=mock_analysis)

            from app.services.interaction_drafts import generate_interaction_draft

            result = await generate_interaction_draft(db=db_session, interaction=interaction)

            # Verify the LLM was called with empty context
            assert analyzer_instance.analyze_chat.called
            call_kwargs = analyzer_instance.analyze_chat.call_args[1]

            # Both contexts should be empty (graceful fallback)
            assert call_kwargs.get("product_context", "") == ""
            assert call_kwargs.get("customer_context", "") == ""

            assert result.text == "Спасибо за обратную связь!"
            assert result.source == "llm"

    @pytest.mark.asyncio
    async def test_draft_product_cache_fallback_when_cdn_fails(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
        test_product_cache: ProductCache,
    ):
        """When CDN context fails, product cache DB context is used instead."""
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="review_test_004",
            nm_id="12345678",
            text="Хороший товар",
            rating=4,
            subject="Отзыв 4★",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction)
        await db_session.flush()

        mock_analysis = {
            "recommendation": "Благодарим за отзыв!",
            "intent": "thanks",
            "sentiment": "positive",
            "sla_priority": "low",
            "recommendation_reason": "Positive review",
        }

        with patch(
            "app.services.interaction_drafts.get_cached_response",
            return_value=None,
        ), patch(
            "app.services.interaction_drafts.get_product_context_for_nm_id",
            new_callable=AsyncMock,
            return_value="",  # CDN returns empty (failed)
        ), patch(
            "app.services.interaction_drafts.get_llm_runtime_config",
            new_callable=AsyncMock,
            return_value=MagicMock(provider="deepseek", model_name="deepseek-chat", enabled=True),
        ), patch(
            "app.services.interaction_drafts._get_seller_tone",
            new_callable=AsyncMock,
            return_value="neutral",
        ), patch(
            "app.services.interaction_drafts.AIAnalyzer"
        ) as MockAnalyzer:
            analyzer_instance = MockAnalyzer.return_value
            analyzer_instance.analyze_chat = AsyncMock(return_value=mock_analysis)

            from app.services.interaction_drafts import generate_interaction_draft

            result = await generate_interaction_draft(db=db_session, interaction=interaction)

            # Verify the LLM was called with product context from DB cache
            call_kwargs = analyzer_instance.analyze_chat.call_args[1]
            product_ctx = call_kwargs.get("product_context", "")

            # DB cache should provide product context since CDN returned empty
            assert "Кроссовки Nike Air Max 90" in product_ctx
            assert "Nike" in product_ctx

    @pytest.mark.asyncio
    async def test_draft_context_errors_dont_break_generation(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """Errors in context fetching don't prevent draft generation."""
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="review_test_005",
            nm_id="99999",
            customer_id="customer_error",
            text="Товар ОК",
            rating=4,
            subject="Отзыв 4★",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction)
        await db_session.flush()

        mock_analysis = {
            "recommendation": "Спасибо!",
            "intent": "thanks",
            "sentiment": "positive",
            "sla_priority": "low",
            "recommendation_reason": "Positive",
        }

        with patch(
            "app.services.interaction_drafts.get_cached_response",
            return_value=None,
        ), patch(
            "app.services.interaction_drafts.get_product_context_for_nm_id",
            new_callable=AsyncMock,
            side_effect=Exception("CDN timeout"),
        ), patch(
            "app.services.interaction_drafts.get_or_fetch_product",
            new_callable=AsyncMock,
            side_effect=Exception("DB connection error"),
        ), patch(
            "app.services.interaction_drafts.get_customer_context_for_draft",
            new_callable=AsyncMock,
            side_effect=Exception("Profile service error"),
        ), patch(
            "app.services.interaction_drafts.get_llm_runtime_config",
            new_callable=AsyncMock,
            return_value=MagicMock(provider="deepseek", model_name="deepseek-chat", enabled=True),
        ), patch(
            "app.services.interaction_drafts._get_seller_tone",
            new_callable=AsyncMock,
            return_value="neutral",
        ), patch(
            "app.services.interaction_drafts.AIAnalyzer"
        ) as MockAnalyzer:
            analyzer_instance = MockAnalyzer.return_value
            analyzer_instance.analyze_chat = AsyncMock(return_value=mock_analysis)

            from app.services.interaction_drafts import generate_interaction_draft

            # Should NOT raise even though all context fetches fail
            result = await generate_interaction_draft(db=db_session, interaction=interaction)

            assert result.text == "Спасибо!"
            assert result.source == "llm"


# -----------------------------------------------------------------------
# Customer profile update on ingestion tests
# -----------------------------------------------------------------------


class TestCustomerProfileUpdateOnIngest:
    """Test that customer profiles are updated when interactions are ingested."""

    @pytest.mark.asyncio
    async def test_profile_created_for_new_interaction(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """Customer profile is created when a new interaction is ingested."""
        from app.services.customer_profile_service import get_or_create_profile, update_profile_from_interaction

        # Create an interaction with a customer_id
        interaction = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="ingest_review_001",
            customer_id="ingest_customer_001",
            rating=4,
            text="Great product!",
            occurred_at=datetime.now(timezone.utc),
            extra_data={"user_name": "Test User"},
        )
        db_session.add(interaction)
        await db_session.flush()

        # Simulate what _update_customer_profiles_for_new_interactions does
        profile = await get_or_create_profile(
            db=db_session,
            seller_id=test_seller.id,
            marketplace="wildberries",
            customer_id="ingest_customer_001",
            name="Test User",
        )
        profile = await update_profile_from_interaction(db_session, profile, interaction)
        await db_session.commit()

        assert profile.total_interactions == 1
        assert profile.total_reviews == 1
        assert profile.avg_rating == 4.0
        assert profile.name == "Test User"

    @pytest.mark.asyncio
    async def test_profile_updated_for_subsequent_interaction(
        self,
        db_session: AsyncSession,
        test_seller: Seller,
    ):
        """Existing customer profile is updated with new interaction data."""
        from app.services.customer_profile_service import get_or_create_profile, update_profile_from_interaction

        # Create initial profile
        profile = await get_or_create_profile(
            db=db_session,
            seller_id=test_seller.id,
            marketplace="wildberries",
            customer_id="ingest_customer_002",
            name="Returning Customer",
        )
        await db_session.commit()

        # First interaction
        interaction1 = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="ingest_review_002a",
            customer_id="ingest_customer_002",
            rating=5,
            text="Love it!",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction1)
        await db_session.flush()
        profile = await update_profile_from_interaction(db_session, profile, interaction1)
        await db_session.commit()

        assert profile.total_interactions == 1
        assert profile.avg_rating == 5.0

        # Second interaction
        interaction2 = Interaction(
            seller_id=test_seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="ingest_review_002b",
            customer_id="ingest_customer_002",
            rating=3,
            text="OK this time",
            occurred_at=datetime.now(timezone.utc),
        )
        db_session.add(interaction2)
        await db_session.flush()
        profile = await update_profile_from_interaction(db_session, profile, interaction2)
        await db_session.commit()

        assert profile.total_interactions == 2
        assert profile.total_reviews == 2
        # avg = (5 + 3) / 2 = 4.0
        assert abs(profile.avg_rating - 4.0) < 0.01


# -----------------------------------------------------------------------
# get_user_prompt customer_context_block tests
# -----------------------------------------------------------------------


class TestUserPromptCustomerContext:
    """Test that get_user_prompt includes customer context block."""

    def test_review_prompt_includes_customer_context(self):
        """Review prompt includes customer context when provided."""
        from app.services.ai_analyzer import get_user_prompt

        prompt = get_user_prompt(
            "review",
            product_name="Кроссовки",
            review_text="Отличный товар!",
            rating=5,
            customer_context_block="\nИнформация о клиенте:\nКлиент: Иванов. Обращений: 5.\n",
        )

        assert "Информация о клиенте" in prompt
        assert "Клиент: Иванов" in prompt
        assert "Обращений: 5" in prompt

    def test_question_prompt_includes_customer_context(self):
        """Question prompt includes customer context when provided."""
        from app.services.ai_analyzer import get_user_prompt

        prompt = get_user_prompt(
            "question",
            product_name="Куртка",
            question_text="Какой размер?",
            customer_context_block="\nИнформация о клиенте:\nКлиент. Обращений: 2.\n",
        )

        assert "Информация о клиенте" in prompt
        assert "Обращений: 2" in prompt

    def test_chat_prompt_includes_customer_context(self):
        """Chat prompt includes customer context when provided."""
        from app.services.ai_analyzer import get_user_prompt

        prompt = get_user_prompt(
            "chat",
            product_name="Товар",
            messages_block="[buyer] Привет",
            customer_context_block="\nИнформация о клиенте:\nКлиент: Петров. Обращений: 10. (повторные жалобы).\n",
        )

        assert "Информация о клиенте" in prompt
        assert "повторные жалобы" in prompt

    def test_prompt_without_customer_context(self):
        """Prompt without customer context does not contain customer block."""
        from app.services.ai_analyzer import get_user_prompt

        prompt = get_user_prompt(
            "review",
            product_name="Кроссовки",
            review_text="Отличный товар!",
            rating=5,
            customer_context_block="",
        )

        assert "Информация о клиенте" not in prompt

    def test_prompt_default_customer_context_empty(self):
        """Default customer_context_block is empty string."""
        from app.services.ai_analyzer import get_user_prompt

        prompt = get_user_prompt(
            "review",
            product_name="Кроссовки",
            review_text="Отличный товар!",
            rating=5,
        )

        assert "Информация о клиенте" not in prompt
