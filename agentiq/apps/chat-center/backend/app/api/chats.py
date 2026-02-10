"""Chats API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, and_
from typing import Optional
from datetime import datetime, timezone
import logging

from app.database import get_db
from app.models.chat import Chat
from app.models.seller import Seller
from app.schemas.chat import ChatResponse, ChatListResponse, ChatFilter
from app.middleware.auth import get_current_seller, get_optional_seller, require_seller_ownership

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", response_model=ChatListResponse)
async def list_chats(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    marketplace: Optional[str] = Query(None, description="Filter by marketplace"),
    has_unread: Optional[bool] = Query(None, description="Filter by unread status"),
    sla_priority: Optional[str] = Query(None, description="Filter by SLA priority"),
    sla_overdue_only: bool = Query(False, description="Show only SLA overdue chats"),
    search: Optional[str] = Query(None, description="Search in customer name or order_id"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """
    Get list of chats with filters.

    If authenticated, returns only chats for current seller.
    If not authenticated, returns all chats (demo mode).
    """

    # Calculate offset from page
    offset = (page - 1) * page_size

    # Build query
    query = select(Chat)
    conditions = []

    # Seller isolation: filter by authenticated seller
    if current_seller:
        conditions.append(Chat.seller_id == current_seller.id)
    if status_filter:
        conditions.append(Chat.status == status_filter)
    if marketplace:
        conditions.append(Chat.marketplace == marketplace)
    if has_unread is not None:
        if has_unread:
            conditions.append(Chat.unread_count > 0)
        else:
            conditions.append(Chat.unread_count == 0)
    if sla_priority:
        conditions.append(Chat.sla_priority == sla_priority)
    if sla_overdue_only:
        now = datetime.now(timezone.utc)
        conditions.append(and_(
            Chat.sla_deadline_at.isnot(None),
            Chat.sla_deadline_at < now
        ))
    if search:
        conditions.append(or_(
            Chat.customer_name.ilike(f"%{search}%"),
            Chat.order_id.ilike(f"%{search}%"),
            Chat.marketplace_chat_id.ilike(f"%{search}%")
        ))

    if conditions:
        query = query.where(and_(*conditions))

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get chats
    query = query.order_by(Chat.last_message_at.desc().nullslast()).offset(offset).limit(page_size)
    result = await db.execute(query)
    chats = result.scalars().all()

    return ChatListResponse(
        chats=[ChatResponse.model_validate(c) for c in chats],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get chat by ID"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found"
        )

    # Seller isolation: verify ownership if authenticated
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    return ChatResponse.model_validate(chat)


@router.post("/{chat_id}/mark-read", response_model=ChatResponse)
async def mark_chat_as_read(
    chat_id: int,
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """Mark all messages in chat as read"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found"
        )

    # Seller isolation
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    chat.unread_count = 0
    await db.commit()
    await db.refresh(chat)

    logger.info(f"Marked chat {chat_id} as read")
    return ChatResponse.model_validate(chat)


@router.post("/{chat_id}/close", response_model=ChatResponse)
async def close_chat(
    chat_id: int,
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """Close chat"""
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found"
        )

    # Seller isolation
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    chat.status = "closed"
    await db.commit()
    await db.refresh(chat)

    logger.info(f"Closed chat {chat_id}")
    return ChatResponse.model_validate(chat)


@router.post("/{chat_id}/analyze", response_model=ChatResponse)
async def analyze_chat(
    chat_id: int,
    async_mode: bool = Query(False, description="Run analysis in background"),
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger AI analysis for a chat.

    Args:
        chat_id: Chat ID
        async_mode: If True, run analysis in background (returns immediately)

    Returns:
        Updated chat with AI analysis
    """
    result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found"
        )

    # Seller isolation
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    if async_mode:
        # Trigger background task
        try:
            from app.tasks.sync import analyze_chat_with_ai
            analyze_chat_with_ai.delay(chat_id)
            logger.info(f"Queued AI analysis for chat {chat_id}")
        except Exception as e:
            logger.warning(f"Failed to queue AI task: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Background task queue unavailable"
            )
    else:
        # Run analysis synchronously
        from app.services.ai_analyzer import analyze_chat_for_db

        analysis = await analyze_chat_for_db(chat_id, db)
        if not analysis:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Unable to analyze chat (no messages or LLM unavailable)"
            )

        await db.refresh(chat)

    logger.info(f"AI analysis completed for chat {chat_id}")
    return ChatResponse.model_validate(chat)
