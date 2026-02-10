"""Unit tests for authentication module."""
import pytest
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from backend.auth import (
    verify_telegram_auth,
    create_session_token,
    verify_session_token,
    should_refresh_token,
    TELEGRAM_BOT_TOKEN,
    JWT_SECRET,
)


@pytest.mark.unit
class TestTelegramAuth:
    """Tests for Telegram Login Widget verification."""

    def test_verify_telegram_auth_valid(self, mock_telegram_auth_data):
        """Test valid Telegram auth data."""
        assert verify_telegram_auth(mock_telegram_auth_data) is True

    def test_verify_telegram_auth_invalid_hash(self, mock_telegram_auth_data):
        """Test with invalid hash."""
        mock_telegram_auth_data["hash"] = "invalid_hash_12345"
        assert verify_telegram_auth(mock_telegram_auth_data) is False

    def test_verify_telegram_auth_missing_hash(self, mock_telegram_auth_data):
        """Test with missing hash."""
        del mock_telegram_auth_data["hash"]
        assert verify_telegram_auth(mock_telegram_auth_data) is False

    def test_verify_telegram_auth_missing_auth_date(self, mock_telegram_auth_data):
        """Test with missing auth_date."""
        del mock_telegram_auth_data["auth_date"]
        assert verify_telegram_auth(mock_telegram_auth_data) is False

    def test_verify_telegram_auth_expired(self, mock_telegram_auth_data):
        """Test with expired auth_date (older than 24 hours)."""
        old_date = int((datetime.now(timezone.utc) - timedelta(days=2)).timestamp())
        mock_telegram_auth_data["auth_date"] = str(old_date)

        # Recalculate hash for old date
        data = {k: v for k, v in mock_telegram_auth_data.items() if k != "hash"}
        check_items = [f"{k}={v}" for k, v in sorted(data.items())]
        data_check_string = "\n".join(check_items)
        secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
        hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        mock_telegram_auth_data["hash"] = hash_value

        assert verify_telegram_auth(mock_telegram_auth_data) is False

    def test_verify_telegram_auth_tampered_data(self, mock_telegram_auth_data):
        """Test with tampered data (hash doesn't match)."""
        original_hash = mock_telegram_auth_data["hash"]
        mock_telegram_auth_data["first_name"] = "Hacker"
        mock_telegram_auth_data["hash"] = original_hash
        assert verify_telegram_auth(mock_telegram_auth_data) is False


@pytest.mark.unit
class TestJWTSession:
    """Tests for JWT session token management."""

    def test_create_session_token(self):
        """Test JWT token creation."""
        telegram_id = 123456789
        token = create_session_token(telegram_id)
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are long

    def test_verify_session_token_valid(self):
        """Test verification of valid token."""
        telegram_id = 123456789
        token = create_session_token(telegram_id)
        verified_id = verify_session_token(token)
        assert verified_id == telegram_id

    def test_verify_session_token_invalid(self):
        """Test verification of invalid token."""
        invalid_token = "invalid.jwt.token"
        verified_id = verify_session_token(invalid_token)
        assert verified_id is None

    def test_verify_session_token_expired(self):
        """Test verification of expired token."""
        import jwt
        from datetime import datetime, timedelta, timezone

        telegram_id = 123456789
        now = datetime.now(timezone.utc)
        payload = {
            "sub": telegram_id,
            "iat": now - timedelta(days=31),
            "exp": now - timedelta(days=1),
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        verified_id = verify_session_token(expired_token)
        assert verified_id is None

    def test_should_refresh_token_fresh(self):
        """Test refresh check for fresh token."""
        telegram_id = 123456789
        token = create_session_token(telegram_id)
        assert should_refresh_token(token) is False

    def test_should_refresh_token_expiring_soon(self):
        """Test refresh check for token expiring within 7 days."""
        import jwt
        from datetime import datetime, timedelta, timezone

        telegram_id = 123456789
        now = datetime.now(timezone.utc)
        payload = {
            "sub": telegram_id,
            "iat": now - timedelta(days=24),
            "exp": now + timedelta(days=6),  # Expires in 6 days
        }
        token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
        assert should_refresh_token(token) is True

    def test_should_refresh_token_invalid(self):
        """Test refresh check for invalid token."""
        invalid_token = "invalid.jwt.token"
        assert should_refresh_token(invalid_token) is False

    def test_create_and_verify_roundtrip(self):
        """Test creating and verifying multiple tokens."""
        test_ids = [111, 222, 333, 444, 555]
        tokens = {tid: create_session_token(tid) for tid in test_ids}

        # Verify all tokens
        for tid, token in tokens.items():
            verified_id = verify_session_token(token)
            assert verified_id == tid

    def test_token_payload_structure(self):
        """Test JWT token payload structure."""
        import jwt

        telegram_id = 123456789
        token = create_session_token(telegram_id)
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])

        assert "sub" in payload
        assert payload["sub"] == telegram_id
        assert "iat" in payload  # issued at
        assert "exp" in payload  # expiration

    def test_different_ids_different_tokens(self):
        """Test that different telegram IDs produce different tokens."""
        token1 = create_session_token(111)
        token2 = create_session_token(222)
        assert token1 != token2
