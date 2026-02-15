"""
Sync tasks for fetching chats and messages from marketplaces.

Tasks:
- sync_all_sellers: Periodic task that triggers sync for all active sellers
- sync_seller_chats: Sync chats for a specific seller (WB or Ozon)
- check_sla_escalation: Check and escalate SLA priority for approaching deadlines
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from celery import shared_task
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.tasks import celery_app
from app.database import AsyncSessionLocal
from app.models.seller import Seller
from app.models.chat import Chat
from app.models.message import Message
from app.models.runtime_setting import RuntimeSetting
from app.services.wb_connector import WBConnector, get_wb_connector_for_seller, fetch_product_name
from app.services.ozon_connector import OzonConnector, get_connector_for_seller
from app.services.encryption import decrypt_credentials
from app.services.interaction_ingest import (
    ingest_chat_interactions,
    ingest_wb_questions_to_interactions,
    ingest_wb_reviews_to_interactions,
)
from app.services.rate_limiter import try_acquire_sync_lock, release_sync_lock
from app.services.sync_metrics import SyncMetrics, sync_health_monitor
from app.config import get_settings

logger = logging.getLogger(__name__)
MAX_TASK_RETRIES = 3
MAX_RETRY_BACKOFF_SECONDS = 15 * 60

# Initialize Sentry for Celery if configured
_settings = get_settings()
if _settings.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=_settings.SENTRY_DSN,
        environment=_settings.SENTRY_ENVIRONMENT,
        traces_sample_rate=_settings.SENTRY_TRACES_SAMPLE_RATE,
        release="1.0.0",
        integrations=[
            CeleryIntegration(),
        ],
    )
    logger.info("Sentry initialized for Celery tasks (env: %s)", _settings.SENTRY_ENVIRONMENT)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _truncate_error(message: str, *, limit: int = 500) -> str:
    return message[:limit]


def _format_sync_error(
    *,
    scope: str,
    message: str,
    attempt: Optional[int] = None,
    max_attempts: Optional[int] = None,
    will_retry: Optional[bool] = None,
) -> str:
    retry_part = ""
    if attempt is not None and max_attempts is not None:
        retry_part = f" attempt={attempt}/{max_attempts}"
    retry_state = ""
    if will_retry is True:
        retry_state = " retry=scheduled"
    elif will_retry is False:
        retry_state = " retry=exhausted"
    return _truncate_error(f"[{scope}] {message}{retry_part}{retry_state}")


async def _set_seller_sync_state(
    *,
    seller_id: int,
    sync_status: str,
    sync_error: Optional[str] = None,
    set_last_sync: bool = False,
) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Seller).where(Seller.id == seller_id))
        seller = result.scalar_one_or_none()
        if not seller:
            return
        seller.sync_status = sync_status
        seller.sync_error = _truncate_error(sync_error) if isinstance(sync_error, str) else None
        if set_last_sync:
            seller.last_sync_at = _now_utc()
        await db.commit()


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


def _sync_cursor_key(*, seller_id: int, marketplace: str) -> str:
    """Build RuntimeSetting key for incremental sync cursor per seller/marketplace."""
    return f"sync_cursor:{marketplace}:{seller_id}"


async def _load_sync_cursor(
    db,
    *,
    seller_id: int,
    marketplace: str,
) -> Optional[str]:
    """Load last successful incremental cursor."""
    key = _sync_cursor_key(seller_id=seller_id, marketplace=marketplace)
    result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting or setting.value is None:
        return None
    value = setting.value.strip()
    return value if value else None


async def _save_sync_cursor(
    db,
    *,
    seller_id: int,
    marketplace: str,
    cursor: Optional[str],
) -> None:
    """Persist incremental cursor after successful sync."""
    if cursor is None:
        return
    value = str(cursor).strip()
    if not value:
        return

    key = _sync_cursor_key(seller_id=seller_id, marketplace=marketplace)
    result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(RuntimeSetting(key=key, value=value))


def _watermark_key(*, seller_id: int, channel: str) -> str:
    """Build RuntimeSetting key for incremental ingestion watermark per seller+channel."""
    return f"sync_watermark:{channel}:{seller_id}"


async def _load_watermark(
    db,
    *,
    seller_id: int,
    channel: str,
) -> Optional[datetime]:
    """Load last successful ingestion watermark (occurred_at of newest synced record)."""
    key = _watermark_key(seller_id=seller_id, channel=channel)
    result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
    setting = result.scalar_one_or_none()
    if not setting or not setting.value:
        return None
    raw = setting.value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        logger.warning("Invalid watermark value for %s: %s", key, raw)
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def _save_watermark(
    db,
    *,
    seller_id: int,
    channel: str,
    watermark_iso: Optional[str],
) -> None:
    """Persist ingestion watermark after successful sync."""
    if not watermark_iso:
        return
    value = str(watermark_iso).strip()
    if not value:
        return

    key = _watermark_key(seller_id=seller_id, channel=channel)
    result = await db.execute(select(RuntimeSetting).where(RuntimeSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        db.add(RuntimeSetting(key=key, value=value))


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


@celery_app.task(name="app.tasks.sync.sync_all_seller_interactions")
def sync_all_seller_interactions():
    """
    Periodic task: Sync unified interactions for all active WB sellers.

    Runs via Celery Beat (separate cadence from chat sync).
    Triggers individual sync_seller_interactions tasks.
    """
    logger.info("Starting interactions sync for all sellers")

    async def _get_active_sellers():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Seller.id, Seller.marketplace)
                .where(
                    and_(
                        Seller.is_active == True,
                        Seller.api_key_encrypted != None,
                        Seller.marketplace == "wildberries",
                    )
                )
            )
            return result.all()

    try:
        sellers = run_async(_get_active_sellers())
        logger.info(f"Found {len(sellers)} active WB sellers for interactions sync")
        for seller_id, _ in sellers:
            sync_seller_interactions.delay(seller_id)
    except Exception as e:
        logger.error(f"Error in sync_all_seller_interactions: {e}")
        raise


@celery_app.task(
    name="app.tasks.sync.sync_seller_interactions",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def sync_seller_interactions(self, seller_id: int, force_full_sync: bool = False):
    """
    Sync unified interactions for a specific seller.

    Args:
        seller_id: Seller ID to sync.
        force_full_sync: If True, ignore saved watermarks and pull all records
            from the beginning. Useful for manual override / recovery.

    Pipeline:
    1. Pull reviews from WB feedbacks API -> interactions(channel=review)
    2. Pull questions from WB feedbacks API -> interactions(channel=question)
    3. Mirror existing chats table -> interactions(channel=chat)
    """
    logger.info(f"Syncing interactions for seller {seller_id}")

    # Per-seller lock: prevent concurrent sync tasks for the same seller.
    if not try_acquire_sync_lock(seller_id):
        logger.info(
            "Skipping interactions sync for seller %s: another sync is already running",
            seller_id,
        )
        return

    # Per-channel SyncMetrics for structured observability
    sync_started_at = _now_utc()

    async def _sync():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Seller).where(
                    and_(
                        Seller.id == seller_id,
                        Seller.is_active == True,
                    )
                )
            )
            seller = result.scalar_one_or_none()
            if not seller:
                logger.warning(f"Seller {seller_id} not found or inactive for interactions sync")
                return
            if not seller.api_key_encrypted:
                logger.warning(f"Seller {seller_id} has no API credentials for interactions sync")
                seller.sync_status = "error"
                seller.sync_error = _format_sync_error(
                    scope="interactions_sync",
                    message="missing_api_credentials",
                )
                await db.commit()
                return
            if seller.marketplace != "wildberries":
                logger.info(f"Skipping seller {seller_id}: marketplace={seller.marketplace}")
                seller.sync_status = "error"
                seller.sync_error = _format_sync_error(
                    scope="interactions_sync",
                    message=f"unsupported_marketplace={seller.marketplace}",
                )
                await db.commit()
                return

            seller.sync_status = "syncing"
            seller.sync_error = None
            await db.commit()

            channel_errors: list[str] = []
            reviews_stats = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
            questions_stats = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}
            chats_stats = {"fetched": 0, "created": 0, "updated": 0, "skipped": 0}

            # --- Load watermarks for incremental sync ---
            review_watermark = None
            question_watermark = None
            if not force_full_sync:
                review_watermark = await _load_watermark(
                    db, seller_id=seller_id, channel="review",
                )
                question_watermark = await _load_watermark(
                    db, seller_id=seller_id, channel="question",
                )
                if review_watermark:
                    logger.info(
                        "Incremental review sync for seller=%s from watermark=%s",
                        seller_id,
                        review_watermark.isoformat(),
                    )
                if question_watermark:
                    logger.info(
                        "Incremental question sync for seller=%s from watermark=%s",
                        seller_id,
                        question_watermark.isoformat(),
                    )

            # --- Reviews channel ---
            review_metrics = SyncMetrics(
                seller_id=seller_id, channel="review", started_at=_now_utc()
            )
            try:
                # Full sync (no watermark): use higher limit to catch all reviews.
                # Incremental sync: 500 per state is plenty for delta.
                review_limit = 1500 if review_watermark is None else 500
                reviews_result = await ingest_wb_reviews_to_interactions(
                    db=db,
                    seller_id=seller_id,
                    marketplace=seller.marketplace or "wildberries",
                    only_unanswered=False,
                    max_items=review_limit,
                    page_size=100,
                    since_watermark=review_watermark,
                )
                reviews_stats = reviews_result.as_dict()
                review_metrics.apply_ingest_stats(reviews_stats)
                review_metrics.finish()
                # Persist new watermark on success.
                if reviews_result.new_watermark:
                    await _save_watermark(
                        db,
                        seller_id=seller_id,
                        channel="review",
                        watermark_iso=reviews_result.new_watermark,
                    )
            except Exception as exc:
                logger.exception("Reviews ingest failed for seller=%s", seller_id)
                channel_errors.append(f"reviews:{exc}")
                review_metrics.finish(error=str(exc))
            review_metrics.log()
            sync_health_monitor.record_sync(review_metrics)

            # --- Questions channel ---
            question_metrics = SyncMetrics(
                seller_id=seller_id, channel="question", started_at=_now_utc()
            )
            try:
                question_limit = 1500 if question_watermark is None else 500
                questions_result = await ingest_wb_questions_to_interactions(
                    db=db,
                    seller_id=seller_id,
                    marketplace=seller.marketplace or "wildberries",
                    only_unanswered=False,
                    max_items=question_limit,
                    page_size=100,
                    since_watermark=question_watermark,
                )
                questions_stats = questions_result.as_dict()
                question_metrics.apply_ingest_stats(questions_stats)
                question_metrics.finish()
                # Persist new watermark on success.
                if questions_result.new_watermark:
                    await _save_watermark(
                        db,
                        seller_id=seller_id,
                        channel="question",
                        watermark_iso=questions_result.new_watermark,
                    )
            except Exception as exc:
                logger.exception("Questions ingest failed for seller=%s", seller_id)
                channel_errors.append(f"questions:{exc}")
                question_metrics.finish(error=str(exc))
            question_metrics.log()
            sync_health_monitor.record_sync(question_metrics)

            # --- Chats channel ---
            chat_metrics = SyncMetrics(
                seller_id=seller_id, channel="chat", started_at=_now_utc()
            )
            try:
                chats_stats = await ingest_chat_interactions(
                    db=db,
                    seller_id=seller_id,
                    max_items=500,
                    direct_wb_fetch=True,
                )
                chat_metrics.apply_ingest_stats(chats_stats)
                chat_metrics.finish()
            except Exception as exc:
                logger.exception("Chats ingest failed for seller=%s", seller_id)
                channel_errors.append(f"chats:{exc}")
                chat_metrics.finish(error=str(exc))
            chat_metrics.log()
            sync_health_monitor.record_sync(chat_metrics)

            # --- Aggregate metrics for structured log ---
            agg_metrics = SyncMetrics(
                seller_id=seller_id, channel="all", started_at=sync_started_at
            )
            agg_metrics.apply_ingest_stats(reviews_stats)
            agg_metrics.apply_ingest_stats(questions_stats)
            agg_metrics.apply_ingest_stats(chats_stats)
            # finish() first (sets duration), then override error counters
            # to avoid double-increment from finish(error=...).
            agg_metrics.finish()
            agg_metrics.errors = sum(
                m.errors for m in (review_metrics, question_metrics, chat_metrics)
            )
            if channel_errors:
                agg_metrics.error_detail = "; ".join(channel_errors)[:500]
            agg_metrics.log()
            sync_health_monitor.record_sync(agg_metrics)

            seller.last_sync_at = _now_utc()
            if channel_errors:
                seller.sync_status = "error"
                seller.sync_error = _format_sync_error(
                    scope="interactions_sync",
                    message="; ".join(channel_errors),
                    attempt=self.request.retries + 1,
                    max_attempts=MAX_TASK_RETRIES + 1,
                    will_retry=False,
                )
            else:
                seller.sync_status = "success"
                seller.sync_error = None
            logger.info(
                "Interactions sync seller=%s reviews=%s questions=%s chats=%s duration=%.1fs",
                seller_id,
                reviews_stats,
                questions_stats,
                chats_stats,
                agg_metrics.duration_seconds,
            )
            # Persist ingested interactions and final sync state.
            await db.commit()

    try:
        run_async(_sync())
    except Exception as e:
        logger.error(f"Interactions sync failed for seller {seller_id}: {e}")
        attempt = self.request.retries + 1
        will_retry = self.request.retries < MAX_TASK_RETRIES
        countdown = min(2 ** self.request.retries * 60, MAX_RETRY_BACKOFF_SECONDS)
        run_async(
            _set_seller_sync_state(
                seller_id=seller_id,
                sync_status="syncing" if will_retry else "error",
                sync_error=_format_sync_error(
                    scope="interactions_sync",
                    message=str(e),
                    attempt=attempt,
                    max_attempts=MAX_TASK_RETRIES + 1,
                    will_retry=will_retry,
                ),
                set_last_sync=not will_retry,
            )
        )
        if will_retry:
            raise self.retry(exc=e, countdown=countdown)
        raise
    finally:
        release_sync_lock(seller_id)


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
                    seller.sync_status = "error"
                    seller.sync_error = _format_sync_error(
                        scope="chats_sync",
                        message="missing_api_credentials",
                    )
                    await db.commit()
                    return

                # Update sync status to syncing
                seller.sync_status = "syncing"
                seller.sync_error = None
                await db.commit()

                # Load last successful cursor to keep sync incremental.
                last_cursor = await _load_sync_cursor(
                    db,
                    seller_id=seller.id,
                    marketplace=marketplace,
                )

                next_cursor: Optional[str] = None

                # Sync based on marketplace
                if marketplace == "wildberries":
                    wb_cursor: Optional[int] = None
                    if last_cursor:
                        try:
                            wb_cursor = int(last_cursor)
                        except (TypeError, ValueError):
                            logger.warning(
                                "Invalid WB cursor value for seller %s: %s",
                                seller.id,
                                last_cursor,
                            )
                    try:
                        wb_next_cursor = await _sync_wb(db, seller, wb_cursor)
                    except ValueError as exc:
                        # Non-retriable: token format is not compatible with Buyers Chat API (expects JWT).
                        seller.last_sync_at = _now_utc()
                        seller.sync_status = "error"
                        seller.sync_error = _format_sync_error(
                            scope="chats_sync",
                            message=f"wb_token_invalid: {str(exc)[:180]}",
                            attempt=self.request.retries + 1,
                            max_attempts=MAX_TASK_RETRIES + 1,
                            will_retry=False,
                        )
                        await db.commit()
                        logger.warning("WB token invalid for chat API seller=%s: %s", seller.id, exc)
                        return
                    except httpx.HTTPStatusError as exc:
                        status_code = getattr(getattr(exc, "response", None), "status_code", None)
                        # Non-retriable: invalid/expired/malformed token.
                        if status_code in {401, 403}:
                            seller.last_sync_at = _now_utc()
                            seller.sync_status = "error"
                            seller.sync_error = _format_sync_error(
                                scope="chats_sync",
                                message=f"wb_auth_failed status={status_code}",
                                attempt=self.request.retries + 1,
                                max_attempts=MAX_TASK_RETRIES + 1,
                                will_retry=False,
                            )
                            await db.commit()
                            logger.warning(
                                "WB auth failed for seller=%s status=%s (no retry)",
                                seller.id,
                                status_code,
                            )
                            return
                        raise
                    if wb_next_cursor is not None:
                        next_cursor = str(wb_next_cursor)
                elif marketplace == "ozon":
                    next_cursor = await _sync_ozon(db, seller, last_cursor)
                else:
                    logger.warning(f"Unknown marketplace: {marketplace}")
                    seller.sync_status = "error"
                    seller.sync_error = _format_sync_error(
                        scope="chats_sync",
                        message=f"unknown_marketplace={marketplace}",
                    )
                    await db.commit()
                    return

                if next_cursor and next_cursor != last_cursor:
                    await _save_sync_cursor(
                        db,
                        seller_id=seller.id,
                        marketplace=marketplace,
                        cursor=next_cursor,
                    )

                # Update last_sync_at and status
                seller.last_sync_at = _now_utc()
                seller.sync_status = "success"
                seller.sync_error = None
                await db.commit()

                logger.info(f"Successfully synced seller {seller_id}")

            except Exception as e:
                logger.error(f"Error syncing seller {seller_id}: {e}")
                # Update sync status to error
                try:
                    seller.sync_status = "error"
                    seller.sync_error = _format_sync_error(
                        scope="chats_sync",
                        message=str(e),
                        attempt=self.request.retries + 1,
                        max_attempts=MAX_TASK_RETRIES + 1,
                        will_retry=False,
                    )
                    await db.commit()
                except:
                    await db.rollback()
                raise

    try:
        run_async(_sync())
    except Exception as e:
        logger.error(f"Sync failed for seller {seller_id}: {e}")
        # Retry with exponential backoff
        attempt = self.request.retries + 1
        will_retry = self.request.retries < MAX_TASK_RETRIES
        countdown = min(2 ** self.request.retries * 30, MAX_RETRY_BACKOFF_SECONDS)
        run_async(
            _set_seller_sync_state(
                seller_id=seller_id,
                sync_status="syncing" if will_retry else "error",
                sync_error=_format_sync_error(
                    scope="chats_sync",
                    message=str(e),
                    attempt=attempt,
                    max_attempts=MAX_TASK_RETRIES + 1,
                    will_retry=will_retry,
                ),
                set_last_sync=not will_retry,
            )
        )
        if will_retry:
            raise self.retry(exc=e, countdown=countdown)
        raise


async def _sync_wb(db, seller: Seller, last_cursor: Optional[int] = None) -> Optional[int]:
    """Sync WB chats and messages with full cursor pagination."""
    api_token = decrypt_credentials(seller.api_key_encrypted)
    connector = WBConnector(api_token=api_token)

    # Fetch ALL pages of messages via cursor pagination
    all_messages = []
    cursor = last_cursor
    final_cursor = last_cursor
    max_pages = 20  # Safety limit to prevent infinite loops
    pages_fetched = 0

    for page in range(max_pages):
        result = await connector.fetch_messages(since_cursor=cursor)
        page_messages = result["messages"]
        next_cursor = result["next_cursor"]

        if not page_messages:
            break

        all_messages.extend(page_messages)
        pages_fetched += 1
        logger.info(f"Fetched page {pages_fetched}: {len(page_messages)} messages for seller {seller.id}")

        if next_cursor is not None:
            final_cursor = next_cursor

        if not result["has_more"] or not next_cursor:
            break

        cursor = next_cursor

    if not all_messages:
        logger.debug(f"No new messages for seller {seller.id}")
        return final_cursor

    logger.info(f"Fetched total {len(all_messages)} messages across {pages_fetched} pages for seller {seller.id}")

    # Group messages by chat
    chats_data = {}
    for msg in all_messages:
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
                "good_card": None,
            }

        chats_data[chat_id]["messages"].append(msg)

        # Capture goodCard from first message that has it (isNewChat event)
        if msg.get("good_card") and not chats_data[chat_id]["good_card"]:
            chats_data[chat_id]["good_card"] = msg["good_card"]

        # Update last message time
        if msg["created_at"] > chats_data[chat_id]["last_message_at"]:
            chats_data[chat_id]["last_message_at"] = msg["created_at"]
            chats_data[chat_id]["last_message_text"] = msg["text"][:500] if msg["text"] else ""

    # Upsert chats and messages, track which need AI analysis
    chats_needing_analysis = []
    for chat_id, chat_data in chats_data.items():
        db_chat_id = await _upsert_chat_and_messages(
            db,
            seller_id=seller.id,
            marketplace="wildberries",
            chat_data=chat_data
        )
        if db_chat_id:
            chats_needing_analysis.append(db_chat_id)

    await db.commit()

    # Fetch product names from WB CDN for chats missing product_name
    chats_needing_names = await db.execute(
        select(Chat).where(
            and_(
                Chat.seller_id == seller.id,
                Chat.product_id != None,
                Chat.product_name == None,
            )
        )
    )
    for chat in chats_needing_names.scalars().all():
        try:
            nm_id = int(chat.product_id)
            name = await fetch_product_name(nm_id)
            if name:
                chat.product_name = name
                logger.debug(f"Chat {chat.id}: product name = {name[:50]}")
        except (ValueError, TypeError):
            pass

    await db.commit()
    logger.info(f"Synced {len(chats_data)} chats for seller {seller.id}")

    # --- Inline AI analysis: analyze up to INLINE_ANALYSIS_CAP chats
    # right inside the sync cycle so they appear in UI with intent/priority/draft.
    # Remaining chats fall back to async Celery task.
    from app.services.ai_analyzer import analyze_chat_for_db

    INLINE_ANALYSIS_CAP = 10
    INLINE_ANALYSIS_TIMEOUT = 8.0  # seconds per chat

    all_to_analyze = list(chats_needing_analysis)

    # Also add chats without analysis (e.g. first-time sync)
    already_queued = set(chats_needing_analysis)
    result = await db.execute(
        select(Chat.id).where(
            and_(
                Chat.seller_id == seller.id,
                Chat.ai_analysis_json == None,
                Chat.chat_status != "closed",
            )
        ).limit(20)
    )
    chats_without_analysis = [row[0] for row in result.all() if row[0] not in already_queued]
    all_to_analyze.extend(chats_without_analysis)

    if all_to_analyze:
        inline_count = 0
        for chat_id in all_to_analyze:
            if inline_count < INLINE_ANALYSIS_CAP:
                try:
                    await asyncio.wait_for(
                        analyze_chat_for_db(chat_id, db),
                        timeout=INLINE_ANALYSIS_TIMEOUT,
                    )
                    inline_count += 1
                    logger.info(f"Inline AI analysis done for chat {chat_id}")
                except asyncio.TimeoutError:
                    logger.warning(f"Inline analysis timeout for chat {chat_id}, queuing async")
                    analyze_chat_with_ai.delay(chat_id)
                except Exception as e:
                    logger.warning(f"Inline analysis failed for chat {chat_id}: {e}, queuing async")
                    analyze_chat_with_ai.delay(chat_id)
            else:
                analyze_chat_with_ai.delay(chat_id)

        if inline_count:
            logger.info(f"Inline analyzed {inline_count}/{len(all_to_analyze)} chats for seller {seller.id}")

    return final_cursor


async def _sync_ozon(db, seller: Seller, last_cursor: Optional[str] = None) -> Optional[str]:
    """Sync Ozon chats and messages."""
    api_key = decrypt_credentials(seller.api_key_encrypted)
    connector = OzonConnector(client_id=seller.client_id, api_key=api_key)

    # Fetch updates
    result = await connector.get_updates(from_message_id=last_cursor)
    messages = result.get("messages", [])

    if not messages:
        logger.debug(f"No new messages for seller {seller.id}")
        return last_cursor

    logger.info(f"Fetched {len(messages)} messages for seller {seller.id}")

    # Group messages by chat
    chats_data = {}
    latest_cursor = last_cursor
    latest_cursor_ts: Optional[datetime] = None

    for msg in messages:
        chat_id = msg["chat_id"]
        created_at = datetime.fromisoformat(msg["created_at"].replace("Z", "+00:00"))

        if latest_cursor_ts is None or created_at > latest_cursor_ts:
            latest_cursor_ts = created_at
            latest_cursor = msg.get("id") or latest_cursor

        if chat_id not in chats_data:
            chats_data[chat_id] = {
                "external_chat_id": chat_id,
                "client_name": "",
                "client_id": msg.get("user", {}).get("id", ""),
                "messages": [],
                "is_new_chat": False,
                "last_message_at": created_at,
                "last_message_text": msg.get("data", {}).get("text", "")[:500],
            }

        # Convert Ozon message format
        chats_data[chat_id]["messages"].append({
            "external_message_id": msg["id"],
            "chat_id": chat_id,
            "author_type": "buyer" if msg.get("direction") == "income" else "seller",
            "text": msg.get("data", {}).get("text", ""),
            "attachments": msg.get("data", {}).get("attachments", []),
            "created_at": created_at,
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
    return latest_cursor


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

    # Extract goodCard product/order info
    good_card = chat_data.get("good_card")
    nm_id = good_card.get("nmID") if good_card else None
    order_rid = good_card.get("rid", "") if good_card else ""

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
            product_id=str(nm_id) if nm_id else None,
            product_article=str(nm_id) if nm_id else None,
            order_id=order_rid or None,
        )
        db.add(chat)
        await db.flush()  # Get chat.id
        logger.debug(f"Created new chat {chat.id} for {external_chat_id} (nmID={nm_id})")
    else:
        # Update existing chat metadata
        chat.last_message_at = chat_data["last_message_at"]
        chat.last_message_preview = chat_data.get("last_message_text", "")
        chat.customer_name = chat_data.get("client_name") or chat.customer_name
        # Fill product_id if missing (from goodCard)
        if nm_id and not chat.product_id:
            chat.product_id = str(nm_id)
            chat.product_article = str(nm_id)
        if order_rid and not chat.order_id:
            chat.order_id = order_rid

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

    # Invalidate stale AI analysis when new buyer messages arrive
    if new_buyer_messages > 0 and chat.ai_analysis_json is not None:
        chat.ai_analysis_json = None
        chat.ai_suggestion_text = None

    # CRITICAL: Recalculate chat_status based on ALL messages in the chat
    await _recalculate_chat_status(db, chat)

    logger.debug(f"Upserted {len(chat_data['messages'])} messages for chat {chat.id}")

    # Return chat.id if new buyer messages need analysis
    return chat.id if new_buyer_messages > 0 else None


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


@celery_app.task(
    name="app.tasks.sync.process_auto_responses",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def process_auto_responses(self):
    """
    Periodic task: Process auto-responses for eligible interactions.

    Runs every 3 minutes via Celery Beat.
    Finds new review/question interactions with:
    - status='open', needs_response=True, is_auto_response=False
    - rating >= 4 (safety guard)
    - channel in ('review', 'question')
    For each, runs the auto-response pipeline.
    """
    logger.info("Looking for interactions eligible for auto-response")

    async def _process():
        from app.services.auto_response import process_auto_response
        from app.services.sla_config import get_sla_config
        from app.services.interaction_drafts import generate_interaction_draft
        from app.services.ai_analyzer import AIAnalyzer
        from app.services.llm_runtime import get_llm_runtime_config

        async with AsyncSessionLocal() as db:
            # Find sellers with auto_response_enabled
            # We check all active sellers, then verify their config
            result = await db.execute(
                select(Seller).where(
                    and_(
                        Seller.is_active == True,
                        Seller.api_key_encrypted != None,
                    )
                )
            )
            sellers = result.scalars().all()

            if not sellers:
                logger.debug("No active sellers with credentials for auto-response")
                return

            total_processed = 0
            total_sent = 0

            for seller in sellers:
                try:
                    sla_config = await get_sla_config(db, seller.id)
                    if not sla_config.get("auto_response_enabled", False):
                        continue

                    allowed_intents = sla_config.get("auto_response_intents", [])
                    if not allowed_intents:
                        continue

                    # Find eligible interactions for this seller
                    from app.models.interaction import Interaction as InteractionModel
                    interactions_result = await db.execute(
                        select(InteractionModel).where(
                            and_(
                                InteractionModel.seller_id == seller.id,
                                InteractionModel.status == "open",
                                InteractionModel.needs_response == True,
                                InteractionModel.is_auto_response == False,
                                InteractionModel.rating >= 4,
                                InteractionModel.channel.in_(["review", "question"]),
                            )
                        ).limit(10)  # Process max 10 per seller per cycle
                    )
                    interactions = interactions_result.scalars().all()

                    if not interactions:
                        continue

                    logger.info(
                        "auto_response: found %d eligible interactions for seller=%s",
                        len(interactions), seller.id,
                    )

                    # Analyze each interaction and attempt auto-response
                    llm_runtime = await get_llm_runtime_config(db)
                    analyzer = AIAnalyzer(
                        provider=llm_runtime.provider,
                        model_name=llm_runtime.model_name,
                        enabled=llm_runtime.enabled,
                    )

                    for interaction in interactions:
                        total_processed += 1
                        try:
                            # Quick intent classification
                            message_text = interaction.text or interaction.subject or ""
                            messages = [
                                {
                                    "text": message_text,
                                    "author_type": "buyer",
                                    "created_at": interaction.occurred_at or datetime.now(timezone.utc),
                                }
                            ]
                            customer_name = None
                            if isinstance(interaction.extra_data, dict):
                                customer_name = interaction.extra_data.get("user_name")

                            analysis = await analyzer.analyze_chat(
                                messages=messages,
                                product_name=interaction.subject or "Товар",
                                customer_name=customer_name,
                                channel=interaction.channel or "review",
                                rating=interaction.rating,
                                sla_config=sla_config,
                            )

                            if not analysis:
                                continue

                            sent = await process_auto_response(
                                db=db,
                                interaction=interaction,
                                ai_result=analysis,
                                seller=seller,
                            )
                            if sent:
                                total_sent += 1

                        except Exception as exc:
                            logger.warning(
                                "auto_response: error processing interaction=%s seller=%s: %s",
                                interaction.id, seller.id, exc,
                            )
                            continue

                except Exception as exc:
                    logger.warning(
                        "auto_response: error processing seller=%s: %s",
                        seller.id, exc,
                    )
                    continue

            if total_processed > 0:
                logger.info(
                    "auto_response: processed=%d sent=%d",
                    total_processed, total_sent,
                )

    try:
        run_async(_process())
    except Exception as e:
        logger.error(f"Error in process_auto_responses: {e}")
        if self.request.retries < 1:
            raise self.retry(exc=e, countdown=30)


@celery_app.task(name="app.tasks.sync.analyze_pending_chats")
def analyze_pending_chats():
    """
    Periodic task: Analyze chats that need AI suggestions.

    Runs every 2 minutes via Celery Beat.
    Finds chats without AI analysis regardless of status.
    """
    logger.info("Looking for chats to analyze with AI")

    async def _find_and_analyze():
        async with AsyncSessionLocal() as db:
            # Find chats that need analysis:
            # - No AI analysis yet (ai_analysis_json is null)
            # - Not closed (skip fully resolved chats)
            result = await db.execute(
                select(Chat.id).where(
                    and_(
                        Chat.ai_analysis_json == None,
                        Chat.chat_status != "closed"
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
