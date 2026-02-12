#!/usr/bin/env python3
"""
One-time script to recalculate chat_status for all existing chats.
Run after deploying the _recalculate_chat_status fix.

Usage:
    cd /opt/agentiq && source venv/bin/activate
    python fix_chat_statuses.py
"""

import asyncio
import os
import sys

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Get database URL from environment or use default
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://agentiq:agentiq@localhost/agentiq_chat"
).replace("postgresql://", "postgresql+asyncpg://")


async def recalculate_all_chat_statuses():
    """Recalculate chat_status for all chats based on message history."""

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Import models here to avoid import issues
        from app.models import Chat, Message

        # Get all chats
        result = await db.execute(select(Chat))
        chats = result.scalars().all()

        print(f"Found {len(chats)} chats to process")

        for chat in chats:
            old_status = chat.chat_status

            # Get all messages for this chat, ordered by time
            msg_result = await db.execute(
                select(Message)
                .where(Message.chat_id == chat.id)
                .order_by(Message.sent_at.asc())
            )
            messages = msg_result.scalars().all()

            if not messages:
                chat.chat_status = "waiting"
            else:
                last_message = messages[-1]

                if last_message.author_type in ("buyer", "customer"):
                    # Check if seller ever responded before this message
                    seller_messages = [
                        m for m in messages[:-1]
                        if m.author_type in ("seller", "system")
                    ]
                    if seller_messages:
                        chat.chat_status = "client-replied"
                    else:
                        chat.chat_status = "waiting"

                elif last_message.author_type == "seller":
                    chat.chat_status = "responded"
                    chat.unread_count = 0

                elif last_message.author_type == "system":
                    chat.chat_status = "auto-response"

                else:
                    chat.chat_status = "waiting"

            if old_status != chat.chat_status:
                print(f"  Chat {chat.id}: {old_status} -> {chat.chat_status}")

        await db.commit()
        print("\nDone! All chat statuses recalculated.")


if __name__ == "__main__":
    asyncio.run(recalculate_all_chat_statuses())
