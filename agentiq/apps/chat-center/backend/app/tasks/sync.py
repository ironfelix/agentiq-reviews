"""
Sync tasks for fetching chats and messages from marketplaces.

Tasks:
- sync_all_sellers: Periodic task that triggers sync for all active sellers
- sync_seller_chats: Sync chats for a specific seller (WB or Ozon)
- check_sla_escalation: Check and escalate SLA priority for approaching deadlines
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.tasks import celery_app
from app.database import AsyncSessionLocal
from app.models.seller import Seller
from app.models.chat import Chat
from app.models.message import Message
from app.services.wb_connector import WBConnector, get_wb_connector_for_seller
from app.services.ozon_connector import OzonConnector, get_connector_for_seller
from app.services.encryption import decrypt_credentials

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async coroutine in sync context (for Celery tasks)."""
    from app.database import engine

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # Dispose stale connections from previous event loops
        loop.run_until_complete(engine.dispose())
        return loop.run_until_complete(coro)
    finally:
        # Clean up connections before closing loop
        loop.run_until_complete(engine.dispose())
        loop.close()


@celery_app.task(name="app.tasks.sync.sync_all_sellers")
def sync_all_sellers():
    """
    Periodic task: Sync chats for all active sellers.

    Runs every 30 seconds via Celery Beat.
    Triggers individual sync_seller_chats tasks for each active seller.
    """
    logger.info("Starting sync for all sellers")

    async def _get_active_sellers():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Seller.id, Seller.marketplace)
                .where(Seller.is_active == True)
            )
            return result.all()

    try:
        sellers = run_async(_get_active_sellers())
        logger.info(f"Found {len(sellers)} active sellers to sync")

        for seller_id, marketplace in sellers:
            # Trigger async task for each seller
            sync_seller_chats.delay(seller_id, marketplace)

    except Exception as e:
        logger.error(f"Error in sync_all_sellers: {e}")
        raise


@celery_app.task(
    name="app.tasks.sync.sync_seller_chats",
    bind=True,
    max_retries=3,
    default_retry_delay=30
)
def sync_seller_chats(self, seller_id: int, marketplace: str):
    """
    Sync chats and messages for a specific seller.

    Args:
        seller_id: Seller ID
        marketplace: 'wildberries' or 'ozon'

    This task:
    1. Gets connector for seller's marketplace
    2. Fetches new events/messages using cursor from last sync
    3. Upserts chats and messages to database
    4. Updates last_sync cursor for next run
    """
    logger.info(f"Syncing seller {seller_id} ({marketplace})")

    async def _sync():
        async with AsyncSessionLocal() as db:
            try:
                # Get seller
                result = await db.execute(
                    select(Seller).where(Seller.id == seller_id)
                )
                seller = result.scalar_one_or_none()

                if not seller:
                    logger.warning(f"Seller {seller_id} not found")
                    return

                if not seller.api_key_encrypted:
                    logger.warning(f"Seller {seller_id} has no API credentials")
                    return

                # Update sync status to syncing
                seller.sync_status = "syncing"
                seller.sync_error = None
                await db.commit()

                # Get last sync cursor from metadata (stored in extra field)
                # TODO: [TECH DEBT] Cursor не сохраняется между синхронизациями!
                # Нужно: добавить таблицу sync_state или поле seller.sync_cursor
                # Без этого каждая синхронизация начинается с начала
                # Issue: При большом количестве чатов это неэффективно
                last_cursor = None

                # Sync based on marketplace
                if marketplace == "wildberries":
                    await _sync_wb(db, seller, last_cursor)
                elif marketplace == "ozon":
                    await _sync_ozon(db, seller, last_cursor)
                else:
                    logger.warning(f"Unknown marketplace: {marketplace}")
                    seller.sync_status = "error"
                    seller.sync_error = f"Unknown marketplace: {marketplace}"
                    await db.commit()
                    return

                # Update last_sync_at and status
                seller.last_sync_at = datetime.utcnow()
                seller.sync_status = "success"
                seller.sync_error = None
                await db.commit()

                logger.info(f"Successfully synced seller {seller_id}")

            except Exception as e:
                logger.error(f"Error syncing seller {seller_id}: {e}")
                # Update sync status to error
                try:
                    seller.sync_status = "error"
                    seller.sync_error = str(e)[:500]
                    await db.commit()
                except:
                    await db.rollback()
                raise

    try:
        run_async(_sync())
    except Exception as e:
        logger.error(f"Sync failed for seller {seller_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 30)


async def _sync_wb(db, seller: Seller, last_cursor: Optional[int] = None):
    """Sync WB chats and messages."""
    api_token = decrypt_credentials(seller.api_key_encrypted)
    connector = WBConnector(api_token=api_token)

    # Fetch new messages
    result = await connector.fetch_messages(since_cursor=last_cursor)
    messages = result["messages"]
    next_cursor = result["next_cursor"]

    if not messages:
        logger.debug(f"No new messages for seller {seller.id}")
        return

    logger.info(f"Fetched {len(messages)} messages for seller {seller.id}")

    # Group messages by chat
    chats_data = {}
    for msg in messages:
        chat_id = msg["chat_id"]

        if chat_id not in chats_data:
            chats_data[chat_id] = {
                "external_chat_id": chat_id,
                "client_name": msg.get("client_name", ""),
                "client_id": msg.get("client_id", ""),
                "messages": [],
                "is_new_chat": msg.get("is_new_chat", False),
                "last_message_at": msg["created_at"],
                "last_message_text": msg["text"][:500] if msg["text"] else "",
            }

        chats_data[chat_id]["messages"].append(msg)

        # Update last message time
        if msg["created_at"] > chats_data[chat_id]["last_message_at"]:
            chats_data[chat_id]["last_message_at"] = msg["created_at"]
            chats_data[chat_id]["last_message_text"] = msg["text"][:500] if msg["text"] else ""

    # Upsert chats and messages
    for chat_id, chat_data in chats_data.items():
        await _upsert_chat_and_messages(
            db,
            seller_id=seller.id,
            marketplace="wildberries",
            chat_data=chat_data
        )

    await db.commit()
    logger.info(f"Synced {len(chats_data)} chats for seller {seller.id}")


async def _sync_ozon(db, seller: Seller, last_cursor: Optional[str] = None):
    """Sync Ozon chats and messages."""
    api_key = decrypt_credentials(seller.api_key_encrypted)
    connector = OzonConnector(client_id=seller.client_id, api_key=api_key)

    # Fetch updates
    result = await connector.get_updates(from_message_id=last_cursor)
    messages = result.get("messages", [])

    if not messages:
        logger.debug(f"No new messages for seller {seller.id}")
        return

    logger.info(f"Fetched {len(messages)} messages for seller {seller.id}")

    # Group messages by chat
    chats_data = {}
    for msg in messages:
        chat_id = msg["chat_id"]

        if chat_id not in chats_data:
            chats_data[chat_id] = {
                "external_chat_id": chat_id,
                "client_name": "",
                "client_id": msg.get("user", {}).get("id", ""),
                "messages": [],
                "is_new_chat": False,
                "last_message_at": datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00")),
                "last_message_text": msg.get("data", {}).get("text", "")[:500],
            }

        # Convert Ozon message format
        chats_data[chat_id]["messages"].append({
            "external_message_id": msg["id"],
            "chat_id": chat_id,
            "author_type": "buyer" if msg.get("direction") == "income" else "seller",
            "text": msg.get("data", {}).get("text", ""),
            "attachments": msg.get("data", {}).get("attachments", []),
            "created_at": datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00")),
        })

    # Upsert chats and messages
    for chat_id, chat_data in chats_data.items():
        await _upsert_chat_and_messages(
            db,
            seller_id=seller.id,
            marketplace="ozon",
            chat_data=chat_data
        )

    await db.commit()
    logger.info(f"Synced {len(chats_data)} chats for seller {seller.id}")


async def _upsert_chat_and_messages(db, seller_id: int, marketplace: str, chat_data: dict):
    """
    Upsert chat and its messages to database.

    Uses PostgreSQL INSERT ... ON CONFLICT for atomic upsert.
    After inserting messages, recalculates chat_status based on last message author.
    """
    external_chat_id = chat_data["external_chat_id"]

    # Find or create chat
    result = await db.execute(
        select(Chat).where(
            and_(
                Chat.seller_id == seller_id,
                Chat.marketplace_chat_id == external_chat_id
            )
        )
    )
    chat = result.scalar_one_or_none()

    if not chat:
        # Create new chat with temporary status (will be recalculated below)
        chat = Chat(
            seller_id=seller_id,
            marketplace=marketplace,
            marketplace_chat_id=external_chat_id,
            customer_name=chat_data.get("client_name", ""),
            customer_id=chat_data.get("client_id", ""),
            status="open",
            unread_count=0,
            last_message_at=chat_data["last_message_at"],
            first_message_at=chat_data["last_message_at"],
            last_message_preview=chat_data.get("last_message_text", ""),
            chat_status="waiting",  # Will be recalculated after messages are inserted
            sla_priority="normal",
        )
        db.add(chat)
        await db.flush()  # Get chat.id
        logger.debug(f"Created new chat {chat.id} for {external_chat_id}")
    else:
        # Update existing chat metadata
        chat.last_message_at = chat_data["last_message_at"]
        chat.last_message_preview = chat_data.get("last_message_text", "")
        chat.customer_name = chat_data.get("client_name") or chat.customer_name

    # Insert messages (skip duplicates)
    new_buyer_messages = 0
    for msg in chat_data["messages"]:
        # Check if message exists
        existing = await db.execute(
            select(Message.id).where(
                and_(
                    Message.chat_id == chat.id,
                    Message.external_message_id == msg["external_message_id"]
                )
            )
        )
        if existing.scalar_one_or_none():
            continue  # Skip duplicate

        message = Message(
            chat_id=chat.id,
            external_message_id=msg["external_message_id"],
            direction="incoming" if msg["author_type"] == "buyer" else "outgoing",
            text=msg.get("text", ""),
            attachments=msg.get("attachments"),
            author_type=msg["author_type"],
            status="sent",
            is_read=msg["author_type"] == "seller",  # Seller messages are read
            sent_at=msg["created_at"],
        )
        db.add(message)

        # Count new buyer messages for unread increment
        if msg["author_type"] == "buyer":
            new_buyer_messages += 1

    # Increment unread count for new buyer messages
    chat.unread_count += new_buyer_messages

    # CRITICAL: Recalculate chat_status based on ALL messages in the chat
    await _recalculate_chat_status(db, chat)

    logger.debug(f"Upserted {len(chat_data['messages'])} messages for chat {chat.id}")


async def _recalculate_chat_status(db, chat: Chat):
    """
    Recalculate chat_status based on message history.

    Logic:
    - If last message from buyer: "waiting" or "client-replied" (if we responded before)
    - If last message from seller: "responded"
    - If last message from system: "auto-response"

    This ensures correct status after sync, regardless of message order.
    """
    # Get all messages for this chat, ordered by time
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.sent_at.asc())
    )
    messages = result.scalars().all()

    if not messages:
        chat.chat_status = "waiting"
        return

    last_message = messages[-1]

    if last_message.author_type in ("buyer", "customer"):
        # Check if we ever responded before this message
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
        # Clear unread count when seller has responded
        chat.unread_count = 0

    elif last_message.author_type == "system":
        chat.chat_status = "auto-response"

    else:
        chat.chat_status = "waiting"  # Fallback

    logger.debug(f"Chat {chat.id} status recalculated: {chat.chat_status}")


@celery_app.task(name="app.tasks.sync.check_sla_escalation")
def check_sla_escalation():
    """
    Check SLA deadlines and escalate priority for approaching deadlines.

    Runs every 5 minutes via Celery Beat.
    Escalates to 'urgent' if deadline is within 30 minutes.
    """
    logger.info("Checking SLA escalation")

    async def _check():
        async with AsyncSessionLocal() as db:
            # Find chats where deadline is approaching (< 30 min) and not yet urgent
            threshold = datetime.utcnow() + timedelta(minutes=30)

            result = await db.execute(
                select(Chat).where(
                    and_(
                        Chat.sla_deadline_at != None,
                        Chat.sla_deadline_at < threshold,
                        Chat.sla_priority != "urgent",
                        Chat.chat_status.in_(["waiting", "client-replied"])
                    )
                )
            )
            chats = result.scalars().all()

            if not chats:
                logger.debug("No chats need SLA escalation")
                return

            logger.info(f"Escalating {len(chats)} chats to urgent")

            for chat in chats:
                chat.sla_priority = "urgent"
                logger.debug(f"Escalated chat {chat.id} to urgent")

            await db.commit()

    try:
        run_async(_check())
    except Exception as e:
        logger.error(f"Error in check_sla_escalation: {e}")
        raise


@celery_app.task(name="app.tasks.sync.auto_close_inactive_chats")
def auto_close_inactive_chats():
    """
    Auto-close chats that have been inactive for 10 days.

    Runs daily via Celery Beat.
    Only closes chats in 'responded' or 'auto-response' status.
    """
    logger.info("Checking for inactive chats to auto-close")

    async def _close():
        async with AsyncSessionLocal() as db:
            # Find chats inactive for 10+ days
            threshold = datetime.utcnow() - timedelta(days=10)

            result = await db.execute(
                select(Chat).where(
                    and_(
                        Chat.last_message_at < threshold,
                        Chat.chat_status.in_(["responded", "auto-response"]),
                    )
                )
            )
            chats = result.scalars().all()

            if not chats:
                logger.debug("No chats to auto-close")
                return

            logger.info(f"Auto-closing {len(chats)} inactive chats")

            for chat in chats:
                chat.chat_status = "closed"
                chat.closed_at = datetime.utcnow()
                logger.debug(f"Auto-closed chat {chat.id}")

            await db.commit()

    try:
        run_async(_close())
    except Exception as e:
        logger.error(f"Error in auto_close_inactive_chats: {e}")
        raise


@celery_app.task(
    name="app.tasks.sync.send_message_to_marketplace",
    bind=True,
    max_retries=5,
    default_retry_delay=10
)
def send_message_to_marketplace(self, message_id: int):
    """
    Send a pending message to the marketplace.

    Args:
        message_id: Message ID in our database

    This task:
    1. Gets message and associated chat/seller
    2. Sends message via appropriate connector
    3. Updates message status to 'sent'
    """
    logger.info(f"Sending message {message_id} to marketplace")

    async def _send():
        async with AsyncSessionLocal() as db:
            # Get message with chat and seller
            result = await db.execute(
                select(Message)
                .where(Message.id == message_id)
            )
            message = result.scalar_one_or_none()

            if not message:
                logger.error(f"Message {message_id} not found")
                return

            if message.status != "pending":
                logger.warning(f"Message {message_id} already processed (status={message.status})")
                return

            # Get chat
            chat_result = await db.execute(
                select(Chat).where(Chat.id == message.chat_id)
            )
            chat = chat_result.scalar_one_or_none()

            if not chat:
                logger.error(f"Chat {message.chat_id} not found")
                message.status = "failed"
                await db.commit()
                return

            # Get seller
            seller_result = await db.execute(
                select(Seller).where(Seller.id == chat.seller_id)
            )
            seller = seller_result.scalar_one_or_none()

            if not seller or not seller.api_key_encrypted:
                logger.error(f"Seller {chat.seller_id} not found or has no credentials")
                message.status = "failed"
                await db.commit()
                return

            try:
                api_key = decrypt_credentials(seller.api_key_encrypted)

                if chat.marketplace == "wildberries":
                    connector = WBConnector(api_token=api_key)
                    result = await connector.send_message(
                        chat_id=chat.marketplace_chat_id,
                        text=message.text
                    )
                    message.external_message_id = result["external_message_id"]

                elif chat.marketplace == "ozon":
                    connector = OzonConnector(
                        client_id=seller.client_id,
                        api_key=api_key
                    )
                    result = await connector.send_message(
                        chat_id=chat.marketplace_chat_id,
                        text=message.text
                    )
                    message.external_message_id = result.get("message_id", "")

                else:
                    logger.error(f"Unknown marketplace: {chat.marketplace}")
                    message.status = "failed"
                    await db.commit()
                    return

                # Success
                message.status = "sent"
                chat.chat_status = "responded"
                chat.unread_count = 0  # Reset unread after responding

                await db.commit()
                logger.info(f"Message {message_id} sent successfully")

            except ValueError as e:
                # Moderation error - don't retry
                logger.error(f"Message {message_id} rejected by moderation: {e}")
                message.status = "failed"
                await db.commit()

            except Exception as e:
                logger.error(f"Failed to send message {message_id}: {e}")
                raise

    try:
        run_async(_send())
    except Exception as e:
        logger.error(f"Error sending message {message_id}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 10)


@celery_app.task(
    name="app.tasks.sync.analyze_chat_with_ai",
    bind=True,
    max_retries=2,
    default_retry_delay=5
)
def analyze_chat_with_ai(self, chat_id: int):
    """
    Analyze chat with AI and update recommendations.

    Args:
        chat_id: Chat ID in our database

    This task:
    1. Gets chat and messages
    2. Calls AIAnalyzer for analysis
    3. Updates chat with ai_analysis_json and ai_suggestion_text
    """
    logger.info(f"Analyzing chat {chat_id} with AI")

    async def _analyze():
        from app.services.ai_analyzer import analyze_chat_for_db

        async with AsyncSessionLocal() as db:
            try:
                analysis = await analyze_chat_for_db(chat_id, db)
                if analysis:
                    logger.info(f"AI analysis complete for chat {chat_id}: intent={analysis.get('intent')}")
                else:
                    logger.debug(f"No AI analysis generated for chat {chat_id}")
            except Exception as e:
                logger.error(f"AI analysis failed for chat {chat_id}: {e}")
                raise

    try:
        run_async(_analyze())
    except Exception as e:
        logger.error(f"Error in AI analysis for chat {chat_id}: {e}")
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 5)


@celery_app.task(name="app.tasks.sync.analyze_pending_chats")
def analyze_pending_chats():
    """
    Periodic task: Analyze chats that need AI suggestions.

    Runs every 2 minutes via Celery Beat.
    Finds chats with unread messages but no AI suggestion.
    """
    logger.info("Looking for chats to analyze with AI")

    async def _find_and_analyze():
        async with AsyncSessionLocal() as db:
            # Find chats that need analysis:
            # - Has unread messages (unread_count > 0)
            # - No AI suggestion yet (ai_suggestion_text is null)
            # - Status is waiting or client-replied
            result = await db.execute(
                select(Chat.id).where(
                    and_(
                        Chat.unread_count > 0,
                        Chat.ai_suggestion_text == None,
                        Chat.chat_status.in_(["waiting", "client-replied"])
                    )
                ).limit(10)  # Process 10 at a time
            )
            chat_ids = [row[0] for row in result.all()]

            if not chat_ids:
                logger.debug("No chats need AI analysis")
                return

            logger.info(f"Queuing AI analysis for {len(chat_ids)} chats")

            for chat_id in chat_ids:
                analyze_chat_with_ai.delay(chat_id)

    try:
        run_async(_find_and_analyze())
    except Exception as e:
        logger.error(f"Error in analyze_pending_chats: {e}")
        raise
