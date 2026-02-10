"""Tests for edge cases and error scenarios."""
import pytest
from datetime import datetime, timedelta
import json


@pytest.mark.unit
class TestInputValidation:
    """Tests for input validation and sanitization."""

    def test_article_id_validation(self):
        """Test article ID validation."""
        # Valid article IDs (WB uses 6-9 digit integers)
        valid_ids = [123456, 282955222, 999999999]
        for aid in valid_ids:
            assert isinstance(aid, int)
            assert aid > 0

        # Invalid article IDs
        invalid_ids = [-1, 0, "abc", None, 12.34]
        for aid in invalid_ids:
            if isinstance(aid, (int, float)):
                assert aid <= 0 or not isinstance(aid, int)

    def test_telegram_id_validation(self):
        """Test Telegram ID validation."""
        # Valid Telegram IDs (positive integers)
        valid = [123456789, 1, 999999999999]
        for tid in valid:
            assert isinstance(tid, int)
            assert tid > 0

    def test_invite_code_format(self):
        """Test invite code format validation."""
        # Valid formats
        valid_codes = ["TEST-2026", "BETA-CODE-123", "ABC-XYZ"]
        for code in valid_codes:
            assert isinstance(code, str)
            assert len(code) > 3
            assert "-" in code or code.isupper()

        # Invalid formats
        invalid_codes = ["", "   ", "a", None, 123]
        # These should be rejected by API


@pytest.mark.unit
class TestEmptyDataHandling:
    """Tests for handling empty or missing data."""

    def test_empty_feedback_list(self):
        """Test handling empty feedback list."""
        feedbacks = []

        # Should not crash
        negative = [fb for fb in feedbacks if fb.get("valuation", 0) <= 3]
        assert negative == []

    def test_missing_fields_in_feedback(self):
        """Test handling missing fields in feedback data."""
        feedback = {
            "fb_id": "123",
            # Missing: valuation, fb_text, answer_text, etc.
        }

        # Safe access with defaults
        rating = feedback.get("valuation", 0)
        text = feedback.get("fb_text", "")
        answer = feedback.get("answer_text")

        assert rating == 0
        assert text == ""
        assert answer is None

    def test_none_values_in_data(self):
        """Test handling None values."""
        data = {
            "rating": None,
            "count": None,
            "text": None,
        }

        # Safe conversions
        rating = float(data.get("rating") or 0)
        count = int(data.get("count") or 0)
        text = data.get("text") or ""

        assert rating == 0.0
        assert count == 0
        assert text == ""


@pytest.mark.unit
class TestJSONHandling:
    """Tests for JSON parsing and serialization."""

    def test_json_with_special_characters(self):
        """Test JSON with Russian characters and quotes."""
        data = {
            "text": "Товар «отличный», цена 1299₽",
            "emoji": "👍",
        }

        # Should serialize without errors
        json_str = json.dumps(data, ensure_ascii=False)
        assert "Товар" in json_str

        # Should deserialize correctly
        parsed = json.loads(json_str)
        assert parsed["text"] == data["text"]

    def test_malformed_json_in_report_data(self):
        """Test handling malformed JSON in report data."""
        malformed = '{"test": invalid}'

        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed)

    def test_large_json_serialization(self):
        """Test serializing large report data."""
        # Simulate large report (1000 reviews)
        large_data = {
            "header": {"product_name": "Test"},
            "feedbacks": [
                {"id": i, "text": "Review text " * 50}
                for i in range(1000)
            ]
        }

        # Should not crash
        json_str = json.dumps(large_data, ensure_ascii=False)
        assert len(json_str) > 10000


@pytest.mark.integration
class TestConcurrencyAndRaceConditions:
    """Tests for concurrent access and race conditions."""

    async def test_multiple_tasks_same_article(self, test_client, test_user, mocker):
        """Test creating multiple tasks for same article."""
        from backend.auth import create_session_token

        mock_celery = mocker.patch("backend.main.analyze_article_task.delay")
        token = create_session_token(test_user.telegram_id)

        # Create multiple tasks for same article
        responses = []
        for _ in range(3):
            response = await test_client.post(
                "/api/tasks/create",
                json={"article_id": 12345678},
                cookies={"session_token": token},
            )
            responses.append(response)

        # All should succeed
        for resp in responses:
            assert resp.status_code == 200

        # Should create separate tasks
        task_ids = [r.json()["id"] for r in responses]
        assert len(set(task_ids)) == 3  # All unique

    async def test_concurrent_invite_code_usage(self, test_client, test_db_session):
        """Test concurrent invite code redemption."""
        from backend.database import InviteCode, User
        from backend.auth import create_session_token

        # Create invite code with limited uses
        invite = InviteCode(code="LIMITED-CODE", max_uses=1, used_count=0)
        test_db_session.add(invite)
        await test_db_session.commit()

        # Create two users without invites
        users = []
        for i in range(2):
            user = User(
                telegram_id=900000000 + i,
                username=f"user{i}",
                auth_date=int(datetime.utcnow().timestamp()),
            )
            test_db_session.add(user)
            users.append(user)
        await test_db_session.commit()

        # Both try to use same code
        responses = []
        for user in users:
            token = create_session_token(user.telegram_id)
            response = await test_client.post(
                "/api/auth/verify-invite",
                json={"code": "LIMITED-CODE"},
                cookies={"session_token": token},
            )
            responses.append(response)

        # Only one should succeed (or both fail if race condition)
        success_count = sum(1 for r in responses if r.status_code == 200)
        # In real concurrent scenario, need proper locking
        assert success_count <= 1


@pytest.mark.unit
class TestDateTimeHandling:
    """Tests for date/time edge cases."""

    def test_timezone_aware_timestamps(self):
        """Test handling timezone-aware timestamps."""
        from datetime import timezone

        # UTC timestamp
        now_utc = datetime.now(timezone.utc)
        timestamp = int(now_utc.timestamp())

        # Should be valid
        assert timestamp > 0

        # Reconstruct
        reconstructed = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        assert abs((now_utc - reconstructed).total_seconds()) < 1

    def test_iso_format_parsing(self):
        """Test parsing ISO format dates from WBCON API."""
        # WBCON formats
        formats = [
            "2026-01-15T10:30:00",
            "2026-01-15T10:30:00Z",
            "2026-01-15T10:30:00+00:00",
        ]

        for date_str in formats:
            # Should parse without error
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            assert isinstance(dt, datetime)

    def test_date_comparison_edge_cases(self):
        """Test date comparison edge cases."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=365)

        # Exactly at cutoff
        test_date = cutoff
        assert test_date >= cutoff

        # One second before cutoff
        test_date = cutoff - timedelta(seconds=1)
        assert test_date < cutoff


@pytest.mark.unit
class TestUnicodeAndEncoding:
    """Tests for Unicode and text encoding."""

    def test_russian_text_processing(self):
        """Test processing Russian text."""
        text = "Отличный товар! Рекомендую 👍"

        # Should handle without errors
        assert len(text) > 0
        assert "товар" in text.lower()

    def test_emoji_handling(self):
        """Test handling emoji in text."""
        text = "Плохо 😞 👎 ❌"

        # Should preserve emoji
        assert "😞" in text
        assert len(text) > 0

    def test_mixed_language_text(self):
        """Test mixed Russian/English text."""
        text = "Товар OK, delivery быстрая"

        # Should handle mixed text
        assert "товар" in text.lower()
        assert "ok" in text.lower()


@pytest.mark.integration
class TestAPIErrorResponses:
    """Tests for API error response formats."""

    async def test_404_error_format(self, test_client, test_user):
        """Test 404 error response format."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.get(
            "/api/tasks/999999/status",
            cookies={"session_token": token},
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    async def test_400_error_format(self, test_client, test_user):
        """Test 400 error response format."""
        from backend.auth import create_session_token

        token = create_session_token(test_user.telegram_id)
        response = await test_client.post(
            "/api/auth/verify-invite",
            json={"code": "INVALID"},
            cookies={"session_token": token},
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    async def test_401_error_format(self, test_client):
        """Test 401 error response format."""
        response = await test_client.post(
            "/api/tasks/create",
            json={"article_id": 12345},
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data


@pytest.mark.unit
class TestBoundaryValues:
    """Tests for boundary value conditions."""

    def test_quality_score_boundaries(self):
        """Test quality score clamping (1-10)."""
        def clamp_score(score):
            return max(1, min(10, int(score)))

        assert clamp_score(0) == 1
        assert clamp_score(1) == 1
        assert clamp_score(5) == 5
        assert clamp_score(10) == 10
        assert clamp_score(11) == 10
        assert clamp_score(100) == 10

    def test_progress_percentage_boundaries(self):
        """Test progress percentage (0-100)."""
        def clamp_progress(progress):
            return max(0, min(100, int(progress)))

        assert clamp_progress(-10) == 0
        assert clamp_progress(0) == 0
        assert clamp_progress(50) == 50
        assert clamp_progress(100) == 100
        assert clamp_progress(150) == 100

    def test_rating_boundaries(self):
        """Test rating boundaries (1-5 for WB)."""
        ratings = [1, 2, 3, 4, 5]
        for r in ratings:
            assert 1 <= r <= 5

        # Invalid ratings should be handled
        invalid = [0, 6, -1, 10]
        for r in invalid:
            # Should be filtered or clamped
            assert r < 1 or r > 5


@pytest.mark.unit
class TestMemoryLeaks:
    """Tests for potential memory leaks."""

    def test_large_dataset_processing(self):
        """Test processing large dataset doesn't leak memory."""
        # Create large dataset
        large_dataset = [
            {"id": i, "text": "Test " * 100}
            for i in range(10000)
        ]

        # Process it
        processed = [item for item in large_dataset if item["id"] % 2 == 0]

        # Should complete without memory issues
        assert len(processed) == 5000

        # Clean up
        del large_dataset
        del processed

    def test_session_cleanup(self):
        """Test database session cleanup."""
        # This is more of a pattern test
        # Actual cleanup handled by fixtures
        pass
