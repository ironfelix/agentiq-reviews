"""
Authentication service - JWT tokens and password hashing.

Features:
- Password hashing with bcrypt
- JWT access token generation and validation
- Token refresh logic
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# JWT settings
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days


class TokenData(BaseModel):
    """Token payload data"""
    seller_id: int
    email: str
    exp: datetime


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


def create_access_token(
    seller_id: int,
    email: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.

    Args:
        seller_id: Seller ID to encode
        email: Seller email
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(seller_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate JWT access token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])

        seller_id = int(payload.get("sub"))
        email = payload.get("email")
        exp_raw = payload.get("exp")
        if exp_raw is None:
            return None
        exp = datetime.fromtimestamp(float(exp_raw), tz=timezone.utc)

        if not seller_id or not email:
            return None

        return TokenData(seller_id=seller_id, email=email, exp=exp)

    except JWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None
    except (ValueError, TypeError) as e:
        logger.debug(f"Token payload error: {e}")
        return None


def is_token_expired(token_data: TokenData) -> bool:
    """Check if token is expired."""
    exp = token_data.exp
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > exp
