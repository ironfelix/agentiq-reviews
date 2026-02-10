"""Auth API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.seller import Seller
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    AuthResponse,
    SellerAuthInfo,
    PasswordChangeRequest,
    MeResponse,
    ConnectMarketplaceRequest,
)
from app.services.encryption import encrypt_credentials
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.middleware.auth import get_current_seller

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new seller account.

    - Email must be unique
    - Password must be at least 8 characters
    - Returns JWT token on success
    """
    # Check if email already exists
    existing = await db.execute(
        select(Seller).where(Seller.email == payload.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    # Create seller
    seller = Seller(
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        name=payload.name,
        marketplace=payload.marketplace,
        is_active=True,
        is_verified=False,
    )

    db.add(seller)
    await db.commit()
    await db.refresh(seller)

    # Generate token
    access_token = create_access_token(seller.id, seller.email)
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(f"New seller registered: {seller.email} (id={seller.id})")

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        seller=SellerAuthInfo(
            id=seller.id,
            email=seller.email,
            name=seller.name,
            marketplace=seller.marketplace,
            is_active=seller.is_active,
            is_verified=seller.is_verified,
            created_at=seller.created_at,
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password.

    Returns JWT token on success.
    """
    # Find seller by email
    result = await db.execute(
        select(Seller).where(Seller.email == payload.email)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not seller.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account not set up for password login"
        )

    if not verify_password(payload.password, seller.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not seller.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # Update last login
    seller.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Generate token
    access_token = create_access_token(seller.id, seller.email)
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(f"Seller logged in: {seller.email} (id={seller.id})")

    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        seller=SellerAuthInfo(
            id=seller.id,
            email=seller.email,
            name=seller.name,
            marketplace=seller.marketplace,
            is_active=seller.is_active,
            is_verified=seller.is_verified,
            created_at=seller.created_at,
        )
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    seller: Seller = Depends(get_current_seller)
):
    """
    Get current authenticated seller info.

    Requires valid JWT token.
    """
    return MeResponse(
        id=seller.id,
        email=seller.email,
        name=seller.name,
        marketplace=seller.marketplace,
        is_active=seller.is_active,
        is_verified=seller.is_verified,
        has_api_credentials=bool(seller.api_key_encrypted),
        last_sync_at=seller.last_sync_at,
        sync_status=seller.sync_status,
        sync_error=seller.sync_error,
        created_at=seller.created_at,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    seller: Seller = Depends(get_current_seller)
):
    """
    Refresh JWT token.

    Returns new token with extended expiration.
    """
    access_token = create_access_token(seller.id, seller.email)
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password for current seller.

    Requires current password verification.
    """
    if not seller.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account not set up for password login"
        )

    if not verify_password(payload.current_password, seller.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )

    seller.password_hash = get_password_hash(payload.new_password)
    await db.commit()

    logger.info(f"Password changed for seller: {seller.email}")


@router.post("/connect-marketplace", response_model=MeResponse)
async def connect_marketplace(
    payload: ConnectMarketplaceRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db)
):
    """
    Connect marketplace API credentials.

    Saves encrypted API key for Wildberries integration.
    After connecting, chats will be synced from the marketplace.
    """
    # Encrypt and save API key
    seller.api_key_encrypted = encrypt_credentials(payload.api_key)
    if payload.client_id:
        seller.client_id = payload.client_id

    # Set sync_status to 'syncing'
    seller.sync_status = "syncing"

    await db.commit()
    await db.refresh(seller)

    logger.info(f"Marketplace connected for seller: {seller.email}")

    # Trigger immediate sync
    try:
        from app.tasks.sync import sync_seller_chats
        sync_seller_chats.delay(seller.id, seller.marketplace or "wildberries")
        logger.info(f"Triggered sync for seller {seller.id}")
    except Exception as e:
        logger.warning(f"Failed to trigger sync task: {e}")
        # Continue anyway - sync will happen on next periodic run

    return MeResponse(
        id=seller.id,
        email=seller.email,
        name=seller.name,
        marketplace=seller.marketplace,
        is_active=seller.is_active,
        is_verified=seller.is_verified,
        has_api_credentials=bool(seller.api_key_encrypted),
        last_sync_at=seller.last_sync_at,
        sync_status=seller.sync_status,
        created_at=seller.created_at,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    seller: Seller = Depends(get_current_seller)
):
    """
    Logout current session.

    Note: JWT tokens are stateless, so this endpoint just serves as a
    placeholder. Client should remove token from storage.
    """
    logger.info(f"Seller logged out: {seller.email}")
    # In a real implementation, you might want to:
    # - Add token to a blacklist (Redis)
    # - Rotate refresh tokens
    # For now, just log the action
