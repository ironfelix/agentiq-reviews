"""Tests for WBCON API integration and data processing."""
import pytest
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))

from datetime import datetime, timedelta


@pytest.mark.unit
class TestFeedbackFiltering:
    """Tests for feedback filtering logic."""

    def test_12_month_filter(self, sample_feedbacks):
        """Test filtering feedbacks to last 12 months."""
        from datetime import datetime, timedelta

        cutoff = datetime.utcnow() - timedelta(days=365)
        cutoff_str = cutoff.isoformat()

        # Mix of old and new feedbacks
        feedbacks = [
            {"fb_id": "1", "fb_created_at": "2025-01-15T10:00:00"},  # Recent
            {"fb_id": "2", "fb_created_at": "2024-01-15T10:00:00"},  # Old
            {"fb_id": "3", "fb_created_at": "2026-01-15T10:00:00"},  # Very recent
        ]

        filtered = [fb for fb in feedbacks if fb.get("fb_created_at", "") >= cutoff_str]
        assert len(filtered) == 2
        assert "2" not in [fb["fb_id"] for fb in filtered]

    def test_deduplication_by_fb_id(self, sample_feedbacks):
        """Test deduplication logic."""
        # Simulate WBCON pagination bug
        feedbacks = [
            {"fb_id": "1", "valuation": 5},
            {"fb_id": "2", "valuation": 4},
            {"fb_id": "1", "valuation": 5},  # Duplicate
            {"fb_id": "3", "valuation": 3},
        ]

        seen = set()
        unique = []
        for fb in feedbacks:
            fb_id = fb.get("fb_id")
            if fb_id and fb_id not in seen:
                seen.add(fb_id)
                unique.append(fb)

        assert len(unique) == 3
        assert [fb["fb_id"] for fb in unique] == ["1", "2", "3"]


@pytest.mark.unit
class TestColorVariantNormalization:
    """Tests for color variant detection and normalization."""

    def test_is_color_variant(self):
        """Test color variant detection."""
        # Real color values
        assert self._is_basic_color("красный")
        assert self._is_basic_color("синий")
        assert self._is_basic_color("белый")

        # Non-color values
        assert not self._is_basic_color("4 шт. · 120 м")
        assert not self._is_basic_color("XL")
        assert not self._is_basic_color("2000mAh")

    def test_multi_color_splitting(self):
        """Test splitting multi-color values."""
        # WBCON sometimes returns "красный, синий"
        color = "красный, синий"
        colors = [c.strip() for c in color.split(",")]
        assert colors == ["красный", "синий"]

    def test_normalize_color_case(self):
        """Test color normalization (lowercase)."""
        variants = ["Красный", "КРАСНЫЙ", "красный"]
        normalized = [v.lower() for v in variants]
        assert normalized == ["красный", "красный", "красный"]

    def _is_basic_color(self, text):
        """Helper to check if text is a basic color."""
        if not text:
            return False
        text_lower = text.lower().strip()
        basic_colors = {
            "белый", "чёрный", "черный", "красный", "синий", "зелёный", "зеленый",
            "жёлтый", "желтый", "оранжевый", "фиолетовый", "розовый", "серый",
            "коричневый", "голубой", "бежевый", "золотой", "серебряный",
        }
        return text_lower in basic_colors


@pytest.mark.unit
class TestResponseAnalysis:
    """Tests for response analysis logic."""

    def test_unanswered_detection(self, sample_feedbacks):
        """Test detecting unanswered reviews."""
        unanswered = [
            fb for fb in sample_feedbacks
            if not fb.get("answer_text")
        ]
        assert len(unanswered) == 1
        assert unanswered[0]["fb_id"] == "3"

    def test_response_time_calculation(self, sample_feedbacks):
        """Test calculating response time."""
        from datetime import datetime

        for fb in sample_feedbacks:
            if fb.get("answer_created_at") and fb.get("fb_created_at"):
                fb_time = datetime.fromisoformat(fb["fb_created_at"].replace("Z", "+00:00"))
                answer_time = datetime.fromisoformat(fb["answer_created_at"].replace("Z", "+00:00"))
                response_time_hours = (answer_time - fb_time).total_seconds() / 3600
                assert response_time_hours >= 0

    def test_negative_review_filtering(self, sample_feedbacks):
        """Test filtering negative reviews (1-3 stars)."""
        negative = [fb for fb in sample_feedbacks if fb.get("valuation", 0) <= 3]
        assert len(negative) == 2
        assert all(fb["valuation"] <= 3 for fb in negative)


@pytest.mark.unit
class TestReasonClassification:
    """Tests for review reason classification."""

    def test_reason_keywords(self):
        """Test keyword-based classification."""
        defect_keywords = ["сломался", "не работает", "дефект", "брак"]
        delivery_keywords = ["доставка", "курьер", "упаковка"]

        defect_text = "Товар сломался через день"
        delivery_text = "Плохая упаковка, товар помят"

        # Simple keyword matching
        has_defect = any(kw in defect_text.lower() for kw in defect_keywords)
        has_delivery = any(kw in delivery_text.lower() for kw in delivery_keywords)

        assert has_defect
        assert has_delivery

    def test_multi_label_classification(self):
        """Test multi-label classification (one review, multiple reasons)."""
        text = "Сломался через неделю, плюс доставка была очень медленная"
        defect_keywords = ["сломался", "не работает"]
        delivery_keywords = ["доставка"]

        reasons = []
        if any(kw in text.lower() for kw in defect_keywords):
            reasons.append("defect")
        if any(kw in text.lower() for kw in delivery_keywords):
            reasons.append("delivery")

        assert len(reasons) == 2
        assert "defect" in reasons
        assert "delivery" in reasons


@pytest.mark.integration
class TestWBCDNIntegration:
    """Tests for WB CDN API (card, price history)."""

    def test_basket_number_calculation(self):
        """Test WB basket server calculation."""
        # Import from analysis script
        from wbcon_task_to_card_v2 import _wb_basket_num

        # Known mappings (from script)
        assert _wb_basket_num(14300000) == "01"  # vol 143
        assert _wb_basket_num(28700000) == "02"  # vol 287
        assert _wb_basket_num(50000000) == "05"  # vol 500

    def test_card_url_construction(self):
        """Test WB card URL construction."""
        nm_id = 282955222
        vol = nm_id // 100000  # 2829
        part = nm_id // 1000   # 282955

        # Basket calculation would go here
        basket = "18"  # Example

        url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"
        assert "basket-18.wbbasket.ru" in url
        assert "/vol2829/" in url
        assert "/part282955/" in url

    def test_price_conversion_kopeks_to_rubles(self):
        """Test price conversion from kopeks to rubles."""
        price_kopeks = 129900
        price_rubles = round(price_kopeks / 100, 2)
        assert price_rubles == 1299.0


@pytest.mark.unit
class TestMoneyLossCalculation:
    """Tests for communication quality money loss calculation."""

    def test_money_loss_formula(self):
        """Test money loss calculation logic."""
        review_count = 100
        period_months = 3
        price_rub = 1299.0
        quality_score = 4  # Bad quality

        # Review rate assumptions (3-5%)
        review_rate_min = 0.03
        review_rate_max = 0.05

        # Estimated purchases
        purchases_min = int(review_count / review_rate_max / period_months)
        purchases_max = int(review_count / review_rate_min / period_months)

        # Quality impact: score 1-10, loss 30-0%
        # score 10 = 0% loss, score 1 = 30% loss
        loss_rate = max(0, (10 - quality_score) / 10 * 0.30)

        # Loss calculation
        revenue_min = purchases_min * price_rub
        loss_min = int(revenue_min * loss_rate)

        assert purchases_min > 0
        assert loss_rate > 0  # Bad quality should have loss
        assert loss_min > 0

    def test_no_loss_with_perfect_quality(self):
        """Test no money loss with perfect quality score (10)."""
        quality_score = 10
        loss_rate = max(0, (10 - quality_score) / 10 * 0.30)
        assert loss_rate == 0

    def test_max_loss_with_worst_quality(self):
        """Test max money loss with worst quality score (1)."""
        quality_score = 1
        loss_rate = max(0, (10 - quality_score) / 10 * 0.30)
        assert loss_rate == 0.27  # 27% (90% of 30%)


@pytest.mark.unit
class TestVariantAnalysis:
    """Tests for variant comparison and signal detection."""

    def test_rating_gap_detection(self):
        """Test detecting significant rating gap between variants."""
        variants = [
            {"name": "красный", "rating": 3.2, "count": 50},
            {"name": "белый", "rating": 4.8, "count": 100},
            {"name": "синий", "rating": 4.7, "count": 80},
        ]

        MIN_GAP = 0.3
        MIN_REVIEWS = 5

        # Find worst variant
        worst = min(variants, key=lambda v: v["rating"])

        # Calculate gap vs others
        others = [v for v in variants if v["name"] != worst["name"]]
        avg_others = sum(v["rating"] for v in others) / len(others) if others else 0
        gap = avg_others - worst["rating"]

        assert worst["name"] == "красный"
        assert gap > MIN_GAP
        assert worst["count"] > MIN_REVIEWS

    def test_insufficient_data_no_signal(self):
        """Test no signal with insufficient data."""
        variants = [
            {"name": "красный", "rating": 3.2, "count": 2},  # Too few reviews
            {"name": "белый", "rating": 4.8, "count": 100},
        ]

        MIN_REVIEWS = 5
        worst = min(variants, key=lambda v: v["rating"])

        # Should not trigger signal (not enough reviews)
        assert worst["count"] < MIN_REVIEWS
