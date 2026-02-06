"""Telegram authentication utilities."""
import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")


def verify_telegram_auth(auth_data: dict) -> bool:
    """
    Verify Telegram Login Widget data.

    According to Telegram docs:
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")

    # Extract hash
    received_hash = auth_data.get("hash", "")
    if not received_hash:
        return False

    # Check auth_date (should be within last 24 hours)
    auth_date = auth_data.get("auth_date")
    if not auth_date:
        return False

    try:
        auth_timestamp = int(auth_date)
        now = int(datetime.utcnow().timestamp())
        if now - auth_timestamp > 86400:  # 24 hours
            return False
    except (ValueError, TypeError):
        return False

    # Prepare data check string
    check_items = []
    for key, value in sorted(auth_data.items()):
        if key == "hash":
            continue
        if value is not None:
            check_items.append(f"{key}={value}")

    data_check_string = "\n".join(check_items)

    # Calculate hash
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()

    return calculated_hash == received_hash


def create_session_token(telegram_id: int) -> str:
    """
    Create a simple session token.
    For MVP: just base64-encoded telegram_id + timestamp.
    In production: use JWT or proper session management.
    """
    import base64
    timestamp = int(datetime.utcnow().timestamp())
    data = f"{telegram_id}:{timestamp}"
    return base64.b64encode(data.encode()).decode()


def verify_session_token(token: str) -> Optional[int]:
    """
    Verify session token and return telegram_id if valid.
    """
    try:
        import base64
        decoded = base64.b64decode(token.encode()).decode()
        telegram_id_str, timestamp_str = decoded.split(":")
        telegram_id = int(telegram_id_str)
        timestamp = int(timestamp_str)

        # Check if token is still valid (7 days)
        now = int(datetime.utcnow().timestamp())
        if now - timestamp > 604800:  # 7 days
            return None

        return telegram_id
    except Exception:
        return None
