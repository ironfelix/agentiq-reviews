"""Messages API endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime, timezone
from typing import Optional
import logging
import uuid

from app.database import get_db
from app.models.message import Message
from app.models.chat import Chat
from app.models.seller import Seller
from app.schemas.message import (
    MessageCreate,
    MessageResponse,
    MessageListResponse
)
from app.middleware.auth import get_optional_seller, require_seller_ownership
from app.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/chat/{chat_id}", response_model=MessageListResponse)
async def list_messages(
    chat_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get messages for a specific chat"""

    # Verify chat exists
    chat_result = await db.execute(
        select(Chat).where(Chat.id == chat_id)
    )
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {chat_id} not found"
        )

    # Seller isolation
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    # Count total messages
    count_result = await db.execute(
        select(func.count(Message.id)).where(Message.chat_id == chat_id)
    )
    total = count_result.scalar_one()

    # Get messages
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat_id)
        .order_by(Message.sent_at.asc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()

    return MessageListResponse(
        messages=[MessageResponse.model_validate(m) for m in messages],
        total=total
    )


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """
    Send message to chat.

    In production mode (seller has API credentials):
    - Creates message with status='pending'
    - Triggers Celery task to send to marketplace
    - Returns immediately, task sends async

    In demo mode (no credentials):
    - Creates message with status='sent'
    - Does not send to marketplace
    """

    # Get chat with seller
    chat_result = await db.execute(
        select(Chat).where(Chat.id == message_data.chat_id)
    )
    chat = chat_result.scalar_one_or_none()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chat {message_data.chat_id} not found"
        )

    # Seller isolation
    if current_seller:
        require_seller_ownership(chat.seller_id, current_seller)

    if not message_data.text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message text is required"
        )

    # Check if seller has credentials (production mode)
    seller_result = await db.execute(
        select(Seller).where(Seller.id == chat.seller_id)
    )
    seller = seller_result.scalar_one_or_none()
    has_credentials = seller and seller.api_key_encrypted

    # Create message record
    message = Message(
        chat_id=chat.id,
        external_message_id=f"pending_{uuid.uuid4().hex[:12]}",
        direction="outgoing",
        text=message_data.text,
        author_type="seller",
        status="pending" if has_credentials else "sent",
        sent_at=datetime.now(timezone.utc)
    )

    db.add(message)

    # Update chat
    chat.last_message_at = message.sent_at
    chat.last_message_preview = message.text[:500] if message.text else ""

    await db.commit()
    await db.refresh(message)

    # Trigger async send task if production mode
    if has_credentials:
        try:
            from app.tasks.sync import send_message_to_marketplace
            send_message_to_marketplace.delay(message.id)
            logger.info(f"Queued message {message.id} for sending to {chat.marketplace}")
        except Exception as e:
            logger.warning(f"Failed to queue message task: {e}. Message saved but not sent.")
    else:
        # Demo mode - mark as sent immediately
        chat.chat_status = "responded"
        chat.unread_count = 0
        await db.commit()
        logger.info(f"Demo mode: message {message.id} saved to chat {chat.id}")

    return MessageResponse.model_validate(message)


@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: int,
    current_seller: Optional[Seller] = Depends(get_optional_seller),
    db: AsyncSession = Depends(get_db)
):
    """Get message by ID"""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    message = result.scalar_one_or_none()

    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {message_id} not found"
        )

    # Seller isolation: check ownership via chat
    if current_seller:
        chat_result = await db.execute(
            select(Chat).where(Chat.id == message.chat_id)
        )
        chat = chat_result.scalar_one_or_none()
        if chat:
            require_seller_ownership(chat.seller_id, current_seller)

    return MessageResponse.model_validate(message)
