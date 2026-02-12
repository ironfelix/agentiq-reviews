"""
Authentication middleware for FastAPI.

Provides dependencies for protected endpoints:
- get_current_seller: Requires valid JWT token
- get_optional_seller: Returns seller if token provided, None otherwise
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.seller import Seller
from app.services.auth import decode_access_token, is_token_expired

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)


async def get_current_seller(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Seller:
    """
    Get current authenticated seller from JWT token.

    Usage:
        @router.get("/protected")
        async def protected_route(seller: Seller = Depends(get_current_seller)):
            return {"seller_id": seller.id}

    Raises:
        HTTPException 401: If token missing or invalid
        HTTPException 403: If seller not found or inactive
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Decode token
    token_data = decode_access_token(token)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check expiration
    if is_token_expired(token_data):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get seller from database
    result = await db.execute(
        select(Seller).where(Seller.id == token_data.seller_id)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller not found"
        )

    if not seller.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller account is deactivated"
        )

    return seller


async def get_optional_seller(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[Seller]:
    """
    Get current seller if token provided, None otherwise.

    Useful for endpoints that work both authenticated and anonymous.

    Usage:
        @router.get("/public")
        async def public_route(seller: Optional[Seller] = Depends(get_optional_seller)):
            if seller:
                return {"mode": "authenticated", "seller_id": seller.id}
            return {"mode": "anonymous"}
    """
    if not credentials:
        return None

    try:
        return await get_current_seller(credentials, db)
    except HTTPException:
        return None


def require_seller_ownership(chat_seller_id: int, current_seller: Seller) -> None:
    """
    Verify that current seller owns the resource.

    Args:
        chat_seller_id: Seller ID from the resource (chat, message, etc.)
        current_seller: Current authenticated seller

    Raises:
        HTTPException 403: If seller doesn't own the resource
    """
    if chat_seller_id != current_seller.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you don't own this resource"
        )
