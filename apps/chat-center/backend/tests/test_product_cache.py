"""Tests for product cache service (WB CDN card.json sync)."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession
from httpx import Response

from app.models.product_cache import ProductCache
from app.services.product_cache_service import (
    get_basket_number,
    build_card_url,
    fetch_product_from_cdn,
    get_or_fetch_product,
    get_product_context_for_draft,
    CACHE_TTL_HOURS,
)


class TestGetBasketNumber:
    """Test basket number calculation for WB CDN."""

    def test_boundary_values(self):
        """Test all boundary values from ranges."""
        # vol = nm_id // 100000
        # ≤143→01
        assert get_basket_number(14300000) == "01"  # vol=143
        assert get_basket_number(14400000) == "02"  # vol=144

        # ≤287→02
        assert get_basket_number(28700000) == "02"  # vol=287
        assert get_basket_number(28800000) == "03"  # vol=288

        # ≤431→03
        assert get_basket_number(43100000) == "03"  # vol=431
        assert get_basket_number(43200000) == "04"  # vol=432

        # ≤3485→20
        assert get_basket_number(348500000) == "20"  # vol=3485
        assert get_basket_number(348600000) == "21"  # vol=3486

        # ≤4565→25
        assert get_basket_number(456500000) == "25"  # vol=4565
        assert get_basket_number(456600000) == "26"  # vol=4566

        # else→26
        assert get_basket_number(500000000) == "26"  # vol=5000

    def test_typical_values(self):
        """Test typical nm_id values."""
        # Small nm_id (early products)
        assert get_basket_number(123456) == "01"  # vol=1

        # Medium nm_id: vol = 12345678 // 100000 = 123, 123 <= 143 → "01"
        assert get_basket_number(12345678) == "01"  # vol=123

        # Large nm_id: vol = 123456789 // 100000 = 1234, 1169 < 1234 <= 1313 → "09"
        assert get_basket_number(123456789) == "09"  # vol=1234


class TestBuildCardUrl:
    """Test WB CDN URL construction."""

    def test_url_format(self):
        """Test URL format is correct."""
        nm_id = 12345678
        url = build_card_url(nm_id)

        # vol = 12345678 // 100000 = 123, 123 <= 143 → basket "01"
        # part = 12345678 // 1000 = 12345
        assert url == "https://basket-01.wbbasket.ru/vol123/part12345/12345678/info/ru/card.json"

    def test_small_nm_id(self):
        """Test URL for small nm_id."""
        nm_id = 123456
        url = build_card_url(nm_id)

        # vol = 123456 // 100000 = 1
        # part = 123456 // 1000 = 123
        # basket for vol=1 is "01"
        assert url == "https://basket-01.wbbasket.ru/vol1/part123/123456/info/ru/card.json"

    def test_large_nm_id(self):
        """Test URL for large nm_id."""
        nm_id = 500000000
        url = build_card_url(nm_id)

        # vol = 500000000 // 100000 = 5000
        # part = 500000000 // 1000 = 500000
        # basket for vol=5000 is "26"
        assert url == "https://basket-26.wbbasket.ru/vol5000/part500000/500000000/info/ru/card.json"


class TestFetchProductFromCdn:
    """Test CDN fetching with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_fetch(self):
        """Test successful CDN fetch and parsing."""
        mock_response_data = {
            "imt_name": "Nike Air Max 90",
            "description": "Классические кроссовки для повседневной носки",
            "brand": "Nike",
            "subj_name": "Кроссовки",
            "options": [
                {"name": "Размер", "value": "42"},
                {"name": "Цвет", "value": "Черный"},
                {"name": "Материал", "value": "Кожа"},
            ],
            "media": {
                "photo360": ["https://example.com/image.jpg"]
            }
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock(spec=Response)
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_product_from_cdn(12345678)

            assert result is not None
            assert result["name"] == "Nike Air Max 90"
            assert result["description"] == "Классические кроссовки для повседневной носки"
            assert result["brand"] == "Nike"
            assert result["category"] == "Кроссовки"
            assert len(result["options"]) == 3
            assert result["options"][0] == {"name": "Размер", "value": "42"}
            assert result["image_url"] == "https://example.com/image.jpg"

    @pytest.mark.asyncio
    async def test_empty_options(self):
        """Test parsing when options array is empty."""
        mock_response_data = {
            "imt_name": "Test Product",
            "description": "",
            "brand": "",
            "subj_name": "",
            "options": [],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock(spec=Response)
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_product_from_cdn(12345678)

            assert result is not None
            assert result["name"] == "Test Product"
            assert result["options"] == []

    @pytest.mark.asyncio
    async def test_http_404(self):
        """Test graceful handling of HTTP 404."""
        from httpx import HTTPStatusError, Request

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock(spec=Response)
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = HTTPStatusError(
                "Not Found",
                request=Request("GET", "http://test"),
                response=mock_response
            )

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_product_from_cdn(12345678)

            assert result is None

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Test graceful handling of timeout."""
        from httpx import TimeoutException

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=TimeoutException("Timeout")
            )

            result = await fetch_product_from_cdn(12345678)

            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_json(self):
        """Test graceful handling of invalid JSON."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock(spec=Response)
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_response.raise_for_status = AsyncMock()

            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_product_from_cdn(12345678)

            assert result is None


class TestGetOrFetchProduct:
    """Test cache hit/miss logic with database."""

    @pytest.mark.asyncio
    async def test_cache_hit_fresh(self, db_session: AsyncSession):
        """Test cache hit when product is fresh (< 24h)."""
        # Create fresh cached product
        fresh_product = ProductCache(
            nm_id="12345678",
            marketplace="wb",
            name="Test Product",
            description="Test description",
            brand="Test Brand",
            category="Test Category",
            options=[{"name": "Size", "value": "M"}],
            fetched_at=datetime.now(timezone.utc) - timedelta(hours=1),  # 1 hour old
        )
        db_session.add(fresh_product)
        await db_session.commit()

        # Should return from cache without CDN call
        with patch("app.services.product_cache_service.fetch_product_from_cdn") as mock_fetch:
            result = await get_or_fetch_product(db_session, "12345678")

            assert result is not None
            assert result.nm_id == "12345678"
            assert result.name == "Test Product"
            mock_fetch.assert_not_called()  # No CDN call

    @pytest.mark.asyncio
    async def test_cache_miss_new_product(self, db_session: AsyncSession):
        """Test cache miss when product doesn't exist in DB."""
        mock_cdn_data = {
            "name": "New Product",
            "description": "New description",
            "brand": "New Brand",
            "category": "New Category",
            "options": [{"name": "Color", "value": "Red"}],
            "image_url": "https://example.com/img.jpg",
        }

        with patch("app.services.product_cache_service.fetch_product_from_cdn", return_value=mock_cdn_data):
            result = await get_or_fetch_product(db_session, "99999999")

            assert result is not None
            assert result.nm_id == "99999999"
            assert result.name == "New Product"
            assert result.brand == "New Brand"
            assert result.fetched_at is not None

    @pytest.mark.asyncio
    async def test_cache_stale_refresh(self, db_session: AsyncSession):
        """Test cache refresh when product is stale (>= 24h)."""
        # Create stale cached product
        stale_product = ProductCache(
            nm_id="12345678",
            marketplace="wb",
            name="Old Product Name",
            description="Old description",
            brand="Old Brand",
            category="Old Category",
            options=[],
            fetched_at=datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS + 1),  # 25 hours old
        )
        db_session.add(stale_product)
        await db_session.commit()

        mock_cdn_data = {
            "name": "Updated Product Name",
            "description": "Updated description",
            "brand": "Updated Brand",
            "category": "Updated Category",
            "options": [{"name": "Size", "value": "L"}],
            "image_url": None,
        }

        with patch("app.services.product_cache_service.fetch_product_from_cdn", return_value=mock_cdn_data):
            result = await get_or_fetch_product(db_session, "12345678")

            assert result is not None
            assert result.nm_id == "12345678"
            assert result.name == "Updated Product Name"  # Updated from CDN
            assert result.brand == "Updated Brand"

    @pytest.mark.asyncio
    async def test_cdn_unavailable_stale_fallback(self, db_session: AsyncSession):
        """Test fallback to stale cache when CDN is unavailable."""
        # Create stale cached product
        stale_product = ProductCache(
            nm_id="12345678",
            marketplace="wb",
            name="Stale Product",
            description="Stale description",
            brand="Stale Brand",
            category="Stale Category",
            options=[],
            fetched_at=datetime.now(timezone.utc) - timedelta(hours=CACHE_TTL_HOURS + 1),  # 25 hours old
        )
        db_session.add(stale_product)
        await db_session.commit()

        # CDN returns None (unavailable)
        with patch("app.services.product_cache_service.fetch_product_from_cdn", return_value=None):
            result = await get_or_fetch_product(db_session, "12345678")

            # Should return stale cache as fallback
            assert result is not None
            assert result.nm_id == "12345678"
            assert result.name == "Stale Product"

    @pytest.mark.asyncio
    async def test_cdn_unavailable_no_cache(self, db_session: AsyncSession):
        """Test None return when CDN unavailable and no cache."""
        with patch("app.services.product_cache_service.fetch_product_from_cdn", return_value=None):
            result = await get_or_fetch_product(db_session, "99999999")

            # Should return None (no cache, no CDN)
            assert result is None

    @pytest.mark.asyncio
    async def test_invalid_nm_id(self, db_session: AsyncSession):
        """Test graceful handling of invalid nm_id."""
        result = await get_or_fetch_product(db_session, "invalid")
        assert result is None

        result = await get_or_fetch_product(db_session, "")
        assert result is None

        result = await get_or_fetch_product(db_session, None)
        assert result is None


class TestGetProductContextForDraft:
    """Test context string formatting for AI prompts."""

    def test_full_context(self):
        """Test formatting with all fields present."""
        product = ProductCache(
            nm_id="12345678",
            name="Nike Air Max 90",
            brand="Nike",
            category="Кроссовки",
            options=[
                {"name": "Размер", "value": "42"},
                {"name": "Цвет", "value": "Черный"},
                {"name": "Материал", "value": "Кожа"},
            ],
        )

        context = get_product_context_for_draft(product)

        assert "Товар: Nike Air Max 90" in context
        assert "Бренд: Nike" in context
        assert "Категория: Кроссовки" in context
        assert "Характеристики: Размер: 42, Цвет: Черный, Материал: Кожа" in context

    def test_minimal_context(self):
        """Test formatting with only name."""
        product = ProductCache(
            nm_id="12345678",
            name="Simple Product",
            brand=None,
            category=None,
            options=None,
        )

        context = get_product_context_for_draft(product)

        assert context == "Товар: Simple Product."

    def test_options_limit(self):
        """Test that only first 5 options are included."""
        options = [
            {"name": f"Opt{i}", "value": f"Val{i}"}
            for i in range(10)
        ]

        product = ProductCache(
            nm_id="12345678",
            name="Product with Many Options",
            options=options,
        )

        context = get_product_context_for_draft(product)

        # Should only include first 5
        assert "Opt0: Val0" in context
        assert "Opt4: Val4" in context
        assert "Opt5: Val5" not in context

    def test_empty_product(self):
        """Test empty string for None product."""
        context = get_product_context_for_draft(None)
        assert context == ""

    def test_product_without_name(self):
        """Test empty string for product without name."""
        product = ProductCache(
            nm_id="12345678",
            name=None,
            brand="Brand",
            category="Category",
        )

        context = get_product_context_for_draft(product)
        assert context == ""

    def test_invalid_options_format(self):
        """Test graceful handling of invalid options format."""
        product = ProductCache(
            nm_id="12345678",
            name="Test Product",
            options="not a list",  # Invalid format
        )

        context = get_product_context_for_draft(product)

        # Should not crash, just skip options
        assert "Товар: Test Product" in context
        assert "Характеристики" not in context
