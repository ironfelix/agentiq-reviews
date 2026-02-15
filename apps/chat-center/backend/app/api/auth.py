"""Auth API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import logging

from app.config import get_settings
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
    SyncNowRequest,
    SyncNowResponse,
)
from app.services.encryption import encrypt_credentials
from app.services.demo_data import seed_demo_interactions
from app.services.interaction_ingest import (
    ingest_chat_interactions,
    ingest_wb_questions_to_interactions,
    ingest_wb_reviews_to_interactions,
)
from app.services.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.middleware.auth import get_current_seller

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


async def _run_direct_wb_sync(
    *,
    db: AsyncSession,
    seller: Seller,
    include_interactions: bool,
) -> tuple[list[str], str]:
    """
    Run direct WB sync in API process (no Celery worker dependency).

    Used in DEBUG/local mode to avoid endless `syncing` when worker is not running.
    """
    scopes: list[str] = []
    channel_errors: list[str] = []

    if (seller.marketplace or "wildberries") != "wildberries":
        seller.sync_status = "error"
        seller.sync_error = "direct sync is supported only for wildberries marketplace"
        seller.last_sync_at = datetime.now(timezone.utc)
        await db.commit()
        return [], "Direct sync unsupported for current marketplace"

    try:
        chats_stats = await ingest_chat_interactions(
            db=db,
            seller_id=seller.id,
            max_items=500,
            direct_wb_fetch=True,
        )
        scopes.append("chats_direct")
        logger.info("Direct WB chats sync seller=%s stats=%s", seller.id, chats_stats)
    except Exception as exc:
        channel_errors.append(f"chats:{exc}")
        logger.exception("Direct chats sync failed for seller=%s", seller.id)

    if include_interactions:
        try:
            reviews_result = await ingest_wb_reviews_to_interactions(
                db=db,
                seller_id=seller.id,
                marketplace=seller.marketplace or "wildberries",
                only_unanswered=False,
                max_items=200,
                page_size=100,
            )
            reviews_stats = reviews_result.as_dict()
            scopes.append("reviews_direct")
            logger.info("Direct WB reviews sync seller=%s stats=%s", seller.id, reviews_stats)
        except Exception as exc:
            channel_errors.append(f"reviews:{exc}")
            logger.exception("Direct reviews sync failed for seller=%s", seller.id)

        try:
            questions_result = await ingest_wb_questions_to_interactions(
                db=db,
                seller_id=seller.id,
                marketplace=seller.marketplace or "wildberries",
                only_unanswered=False,
                max_items=200,
                page_size=100,
            )
            questions_stats = questions_result.as_dict()
            scopes.append("questions_direct")
            logger.info("Direct WB questions sync seller=%s stats=%s", seller.id, questions_stats)
        except Exception as exc:
            channel_errors.append(f"questions:{exc}")
            logger.exception("Direct questions sync failed for seller=%s", seller.id)

    seller.last_sync_at = datetime.now(timezone.utc)
    if channel_errors:
        seller.sync_status = "error"
        seller.sync_error = "; ".join(channel_errors)[:500]
        message = "Direct sync finished with errors"
    else:
        seller.sync_status = "success"
        seller.sync_error = None
        message = "Direct sync completed"

    await db.commit()
    return scopes, message


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
            has_api_credentials=bool(seller.api_key_encrypted),
            sync_status=seller.sync_status,
            sync_error=seller.sync_error,
            last_sync_at=seller.last_sync_at,
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
            has_api_credentials=bool(seller.api_key_encrypted),
            sync_status=seller.sync_status,
            sync_error=seller.sync_error,
            last_sync_at=seller.last_sync_at,
            created_at=seller.created_at,
        )
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current authenticated seller info.

    Requires valid JWT token.
    """
    # Guardrail: stale syncing status should not spin forever in UI.
    if seller.sync_status == "syncing" and isinstance(seller.updated_at, datetime):
        updated_at = seller.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_minutes = int((datetime.now(timezone.utc) - updated_at).total_seconds() / 60)
        if age_minutes >= 5:
            seller.sync_status = "error"
            seller.sync_error = seller.sync_error or (
                "Синхронизация не завершилась в ожидаемое время. Попробуйте повторить."
            )
            await db.commit()
            await db.refresh(seller)

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

    # In local/demo mode run direct sync so UX doesn't depend on Celery worker.
    if settings.DEBUG:
        try:
            scopes, message = await _run_direct_wb_sync(
                db=db,
                seller=seller,
                include_interactions=True,
            )
            logger.info("Direct bootstrap sync seller=%s scopes=%s msg=%s", seller.id, scopes, message)
        except Exception as e:
            logger.exception("Direct bootstrap sync failed for seller=%s", seller.id)
            seller.sync_status = "error"
            seller.sync_error = f"[connect_marketplace] direct_sync_failed: {str(e)[:350]}"
            seller.last_sync_at = datetime.now(timezone.utc)
            await db.commit()
    else:
        # Production path: trigger background sync via Celery
        try:
            from app.tasks.sync import sync_seller_chats, sync_seller_interactions

            sync_seller_chats.delay(seller.id, seller.marketplace or "wildberries")
            # Unified inbox depends on interactions; queue initial sync right away.
            if (seller.marketplace or "wildberries") == "wildberries":
                sync_seller_interactions.delay(seller.id)
            logger.info(f"Triggered sync for seller {seller.id}")
        except Exception as e:
            logger.warning("Failed to trigger sync task for seller=%s: %s", seller.id, e)
            # Demo-blocker guardrail: if we cannot queue sync, don't leave UI in infinite "syncing".
            seller.sync_status = "error"
            seller.sync_error = (
                seller.sync_error
                or "Не удалось запустить синхронизацию. Проверьте, что Celery/Redis запущены, и нажмите «Повторить»."
            )
            seller.last_sync_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(seller)

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


@router.post("/sync-now", response_model=SyncNowResponse)
async def sync_now(
    payload: SyncNowRequest,
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger manual background sync for current seller.

    Queues chat sync for selected marketplace and, optionally,
    unified interactions sync for WB.
    """
    if not seller.api_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marketplace API key is not connected",
        )

    queued_scopes: list[str] = []
    seller.sync_status = "syncing"
    seller.sync_error = None
    await db.commit()
    await db.refresh(seller)

    try:
        from app.tasks.sync import sync_seller_chats, sync_seller_interactions

        sync_seller_chats.delay(seller.id, seller.marketplace or "wildberries")
        queued_scopes.append("chats")

        if payload.include_interactions and (seller.marketplace or "wildberries") == "wildberries":
            sync_seller_interactions.delay(seller.id)
            queued_scopes.append("interactions")
    except Exception as e:
        logger.warning(f"Failed to queue sync tasks for seller {seller.id}: {e}")
        seller.sync_status = "error"
        seller.sync_error = f"[sync_now] queue_failed: {str(e)[:350]}"
        await db.commit()
        await db.refresh(seller)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to queue sync tasks",
        ) from e

    return SyncNowResponse(
        seller_id=seller.id,
        sync_status=seller.sync_status or "syncing",
        queued_scopes=queued_scopes,
        message="Sync queued",
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


@router.post("/seed-demo")
async def seed_demo(
    seller: Seller = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
):
    """
    Seed demo interactions for the current seller.

    Called when user clicks "Пропустить подключение" during onboarding.
    Creates realistic demo interactions (reviews, questions, chats) so the
    inbox looks alive. Idempotent — skips if demo data already exists.
    """
    try:
        result = await seed_demo_interactions(db=db, seller_id=seller.id)
    except Exception as exc:
        logger.exception("Failed to seed demo data for seller=%s", seller.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seed demo data: {exc}",
        ) from exc

    return result
