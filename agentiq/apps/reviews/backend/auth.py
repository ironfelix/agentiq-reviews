"""Telegram authentication + JWT session tokens."""
import hashlib
import hmac
import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
JWT_SECRET = os.getenv("SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30
JWT_REFRESH_THRESHOLD_DAYS = 7

# Security: Enforce JWT_SECRET is set
if not JWT_SECRET:
    raise RuntimeError(
        "SECRET_KEY environment variable must be set! "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )

# Security: Validate JWT_SECRET strength (minimum 32 bytes)
if len(JWT_SECRET) < 32:
    raise RuntimeError(
        f"SECRET_KEY is too weak ({len(JWT_SECRET)} chars). "
        "Must be at least 32 characters for security. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
    )


def verify_telegram_auth(auth_data: dict) -> bool:
    """
    Verify Telegram Login Widget data.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    received_hash = auth_data.get("hash", "")
    if not received_hash:
        return False

    auth_date = auth_data.get("auth_date")
    if not auth_date:
        return False

    try:
        auth_timestamp = int(auth_date)
        now = int(datetime.now(timezone.utc).timestamp())
        if now - auth_timestamp > 86400:  # 24 hours
            return False
    except (ValueError, TypeError):
        return False

    check_items = []
    for key, value in sorted(auth_data.items()):
        if key == "hash":
            continue
        if value is not None:
            check_items.append(f"{key}={value}")

    data_check_string = "\n".join(check_items)

    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    return calculated_hash == received_hash


def create_session_token(telegram_id: int) -> str:
    """Create JWT session token (HS256, 30 days)."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": telegram_id,
        "iat": now,
        "exp": now + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_session_token(token: str) -> Optional[int]:
    """Verify JWT and return telegram_id, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, KeyError, ValueError):
        return None


def should_refresh_token(token: str) -> bool:
    """Check if token expires within JWT_REFRESH_THRESHOLD_DAYS."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        remaining = exp - datetime.now(timezone.utc)
        return remaining < timedelta(days=JWT_REFRESH_THRESHOLD_DAYS)
    except Exception:
        return False
