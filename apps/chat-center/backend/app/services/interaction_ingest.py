"""Ingestion services for unified interactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.interaction import Interaction
from app.services.interaction_linking import refresh_link_candidates_for_interactions
from app.services.wb_connector import get_wb_connector_for_seller
from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller
from app.services.wb_questions_connector import get_wb_questions_connector_for_seller


@dataclass
class IngestStats:
    """Simple ingestion stats for API responses."""

    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
        }


def _parse_iso_dt(value: Optional[str]) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        # Best-effort fallback for non-ISO strings (rare in WB payloads).
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S%z"):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except Exception:
                parsed = None
        if parsed is None:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc_dt(value: Optional[datetime]) -> Optional[datetime]:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_review_text(feedback: Dict[str, Any]) -> str:
    text = (feedback.get("text") or "").strip()
    pros = (feedback.get("pros") or "").strip()
    cons = (feedback.get("cons") or "").strip()

    parts = []
    if text:
        parts.append(text)
    if pros:
        parts.append(f"Плюсы: {pros}")
    if cons:
        parts.append(f"Минусы: {cons}")

    return "\n".join(parts).strip()


def _priority_for_review(rating: Optional[int], needs_response: bool) -> str:
    if not needs_response:
        return "low"
    if rating is None:
        return "normal"
    if rating <= 2:
        return "high"
    if rating == 3:
        return "normal"
    return "low"


PRESERVED_META_KEYS = {
    "last_ai_draft",
    "last_reply_text",
    "last_reply_source",
    "last_reply_at",
    "last_reply_outcome",
    "wb_sync_state",
    "link_candidates",
    "link_updated_at",
}


def _reply_pending_override(*, existing: Optional[Interaction], window_minutes: int = 180) -> bool:
    """
    If we have a local reply recorded (e.g. we sent it via AgentIQ),
    don't reopen the item immediately just because WB hasn't reflected it yet.

    This happens in practice due to moderation/propgation delays.
    """
    if not existing or not isinstance(existing.extra_data, dict):
        return False
    meta = existing.extra_data
    if meta.get("last_reply_source") != "agentiq":
        return False
    last_reply_at = _parse_iso_dt(meta.get("last_reply_at")) if isinstance(meta.get("last_reply_at"), str) else None
    if not last_reply_at:
        return False
    now = datetime.now(timezone.utc)
    if last_reply_at.tzinfo is None:
        last_reply_at = last_reply_at.replace(tzinfo=timezone.utc)
    age = (now - last_reply_at).total_seconds() / 60.0
    return age >= 0 and age <= float(window_minutes)


def _merge_extra_data(existing_meta: Optional[dict], new_meta: dict[str, Any]) -> dict[str, Any]:
    existing = existing_meta if isinstance(existing_meta, dict) else {}
    # New ingestion payload should not wipe UI/ops metadata (drafts, reply outcome, linking).
    merged: dict[str, Any] = dict(new_meta)
    for key in PRESERVED_META_KEYS:
        if key in existing:
            merged[key] = existing[key]
    return merged


def _question_intent(question_text: str) -> str:
    text = (question_text or "").lower()
    if any(token in text for token in ("размер", "рост", "вес", "обхват", "подойдет")):
        return "sizing_fit"
    if any(token in text for token in ("в наличии", "когда будет", "доставка", "срок", "наличие")):
        return "availability_delivery"
    if any(token in text for token in ("материал", "состав", "характерист", "совместим", "мощност", "объем")):
        return "spec_compatibility"
    if any(token in text for token in ("сертификат", "аллерг", "безопас", "гаранти")):
        return "compliance_safety"
    if any(token in text for token in ("брак", "не работает", "сломал", "возврат")):
        return "post_purchase_issue"
    return "general_question"


def _priority_for_question_with_intent(
    *,
    needs_response: bool,
    question_text: str,
    occurred_at: Optional[datetime],
) -> tuple[str, str, int]:
    if not needs_response:
        return "low", "answered", 24 * 60

    intent = _question_intent(question_text)
    base_priority = "high"
    sla_minutes = 4 * 60

    if intent in {"compliance_safety", "post_purchase_issue"}:
        base_priority = "urgent"
        sla_minutes = 60
    elif intent == "availability_delivery":
        base_priority = "high"
        sla_minutes = 2 * 60
    elif intent == "spec_compatibility":
        base_priority = "normal"
        sla_minutes = 8 * 60
    elif intent == "general_question":
        base_priority = "normal"
        sla_minutes = 8 * 60

    if occurred_at:
        now = datetime.now(timezone.utc)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        age_hours = (now - occurred_at).total_seconds() / 3600.0
        if age_hours >= 24:
            base_priority = "urgent"
        elif age_hours >= 8 and base_priority == "high":
            base_priority = "urgent"

    return base_priority, intent, sla_minutes


async def ingest_wb_reviews_to_interactions(
    *,
    db: AsyncSession,
    seller_id: int,
    marketplace: str = "wildberries",
    only_unanswered: bool = False,
    nm_id: Optional[int] = None,
    max_items: int = 300,
    page_size: int = 100,
) -> Dict[str, int]:
    """
    Pull reviews from WB API and upsert into unified interactions table.

    Notes:
    - Primary source only (`source=wb_api`)
    - No cross-channel identity linking here; only canonical review ingestion
    """
    connector = await get_wb_feedbacks_connector_for_seller(seller_id, db)
    stats = IngestStats()
    seen_ids: set[str] = set()
    touched_ids: set[int] = set()
    answer_states = [False] if only_unanswered else [False, True]

    for answer_state in answer_states:
        skip = 0
        while stats.fetched < max_items:
            take = min(page_size, max_items - stats.fetched)
            response = await connector.list_feedbacks(
                skip=skip,
                take=take,
                is_answered=answer_state,
                nm_id=nm_id,
                order="dateDesc",
            )

            data = response.get("data") or {}
            feedbacks = data.get("feedbacks") or []
            if not isinstance(feedbacks, list) or not feedbacks:
                break

            stats.fetched += len(feedbacks)

            for fb in feedbacks:
                external_id = str(fb.get("id") or "").strip()
                if not external_id:
                    stats.skipped += 1
                    continue
                if external_id in seen_ids:
                    stats.skipped += 1
                    continue
                seen_ids.add(external_id)

                product = fb.get("productDetails") or {}
                rating = fb.get("productValuation")
                answer_text = (fb.get("answerText") or "").strip()
                needs_response = not bool(answer_text)
                occurred_at = _parse_iso_dt(fb.get("createdDate"))
                answer_created_at = _parse_iso_dt(
                    fb.get("answerCreateDate")
                    or fb.get("answerCreatedDate")
                    or fb.get("answerDate")
                )

                subject = f"Отзыв {rating}★" if isinstance(rating, int) else "Отзыв"
                product_name = (product.get("productName") or "").strip()
                if product_name:
                    subject = f"{subject} · {product_name}"

                mapped_text = _build_review_text(fb)
                mapped_priority = _priority_for_review(rating if isinstance(rating, int) else None, needs_response)
                mapped_status = "open" if needs_response else "responded"

                result = await db.execute(
                    select(Interaction).where(
                        and_(
                            Interaction.seller_id == seller_id,
                            Interaction.marketplace == marketplace,
                            Interaction.channel == "review",
                            Interaction.external_id == external_id,
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                channel_meta = {
                    "user_name": fb.get("userName"),
                    "answer_state": fb.get("answerState"),
                    "was_viewed": fb.get("wasViewed"),
                    "wb_feedback_id": external_id,
                    "wb_answer_text": answer_text or None,
                    "wb_answer_created_at": answer_created_at.isoformat() if answer_created_at else None,
                }
                if answer_text:
                    channel_meta["last_reply_text"] = answer_text
                    channel_meta["last_reply_source"] = "wb_api"
                    if answer_created_at:
                        channel_meta["last_reply_at"] = answer_created_at.isoformat()
                    channel_meta["wb_sync_state"] = "confirmed"
                elif _reply_pending_override(existing=existing):
                    # Keep responded in UI while WB answer is pending visibility.
                    needs_response = False
                    mapped_status = "responded"
                    mapped_priority = "low"
                    channel_meta["wb_sync_state"] = "pending"
                payload = {
                    "customer_id": None,  # Name-only identity is intentionally not used as deterministic key
                    "order_id": str(fb.get("supplierProductID") or "") or None,
                    "nm_id": str(product.get("nmId") or "") or None,
                    "product_article": str(product.get("supplierArticle") or "") or None,
                    "subject": subject,
                    "text": mapped_text,
                    "rating": rating if isinstance(rating, int) else None,
                    "status": mapped_status,
                    "priority": mapped_priority,
                    "needs_response": needs_response,
                    "source": "wb_api",
                    "occurred_at": occurred_at,
                    "extra_data": channel_meta,
                }

                if existing:
                    payload["extra_data"] = _merge_extra_data(existing.extra_data, channel_meta)
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    stats.updated += 1
                    touched_ids.add(existing.id)
                else:
                    interaction = Interaction(
                        seller_id=seller_id,
                        marketplace=marketplace,
                        channel="review",
                        external_id=external_id,
                        **payload,
                    )
                    db.add(interaction)
                    await db.flush()
                    touched_ids.add(interaction.id)
                    stats.created += 1

            if len(feedbacks) < take:
                break
            skip += take

    await refresh_link_candidates_for_interactions(
        db=db,
        seller_id=seller_id,
        interaction_ids=touched_ids,
    )
    return stats.as_dict()


async def ingest_wb_questions_to_interactions(
    *,
    db: AsyncSession,
    seller_id: int,
    marketplace: str = "wildberries",
    only_unanswered: bool = False,
    nm_id: Optional[int] = None,
    max_items: int = 300,
    page_size: int = 100,
) -> Dict[str, int]:
    """
    Pull questions from WB API and upsert into unified interactions table.
    """
    connector = await get_wb_questions_connector_for_seller(seller_id, db)
    stats = IngestStats()
    seen_ids: set[str] = set()
    touched_ids: set[int] = set()
    answer_states = [False] if only_unanswered else [False, True]

    for answer_state in answer_states:
        skip = 0
        while stats.fetched < max_items:
            take = min(page_size, max_items - stats.fetched)
            response = await connector.list_questions(
                skip=skip,
                take=take,
                is_answered=answer_state,
                nm_id=nm_id,
                order="dateDesc",
            )

            data = response.get("data") or {}
            questions = data.get("questions") or []
            if not isinstance(questions, list) or not questions:
                break

            stats.fetched += len(questions)

            for q in questions:
                external_id = str(q.get("id") or "").strip()
                if not external_id:
                    stats.skipped += 1
                    continue
                if external_id in seen_ids:
                    stats.skipped += 1
                    continue
                seen_ids.add(external_id)

                answer = q.get("answer") or {}
                answer_text = (answer.get("text") or "").strip() if isinstance(answer, dict) else ""
                needs_response = not bool(answer_text)

                product = q.get("productDetails") or {}
                question_text = (q.get("text") or "").strip()
                occurred_at = _parse_iso_dt(q.get("createdDate"))
                answer_created_at = _parse_iso_dt(
                    answer.get("createDate") if isinstance(answer, dict) else None
                )

                subject = "Вопрос по товару"
                product_name = (product.get("productName") or "").strip()
                if product_name:
                    subject = f"{subject} · {product_name}"

                mapped_priority, intent, sla_target_minutes = _priority_for_question_with_intent(
                    needs_response=needs_response,
                    question_text=question_text,
                    occurred_at=occurred_at,
                )
                mapped_status = "open" if needs_response else "responded"
                sla_due_at = None
                if occurred_at and needs_response:
                    try:
                        sla_due_at = (occurred_at + timedelta(minutes=sla_target_minutes)).isoformat()
                    except Exception:
                        sla_due_at = None

                result = await db.execute(
                    select(Interaction).where(
                        and_(
                            Interaction.seller_id == seller_id,
                            Interaction.marketplace == marketplace,
                            Interaction.channel == "question",
                            Interaction.external_id == external_id,
                        )
                    )
                )
                existing = result.scalar_one_or_none()

                channel_meta = {
                    "state": q.get("state"),
                    "was_viewed": q.get("wasViewed"),
                    "is_warned": q.get("isWarned"),
                    "user_name": q.get("userName"),
                    "answer_editable": answer.get("editable") if isinstance(answer, dict) else None,
                    "answer_create_date": answer.get("createDate") if isinstance(answer, dict) else None,
                    "wb_answer_text": answer_text or None,
                    "wb_answer_created_at": answer_created_at.isoformat() if answer_created_at else None,
                    "question_intent": intent,
                    "priority_reason": intent,
                    "sla_target_minutes": sla_target_minutes,
                    "sla_due_at": sla_due_at,
                }
                if answer_text:
                    channel_meta["last_reply_text"] = answer_text
                    channel_meta["last_reply_source"] = "wb_api"
                    if answer_created_at:
                        channel_meta["last_reply_at"] = answer_created_at.isoformat()
                    channel_meta["wb_sync_state"] = "confirmed"
                elif _reply_pending_override(existing=existing):
                    needs_response = False
                    mapped_status = "responded"
                    mapped_priority = "low"
                    channel_meta["wb_sync_state"] = "pending"
                payload = {
                    "customer_id": None,
                    "order_id": None,
                    "nm_id": str(product.get("nmId") or "") or None,
                    "product_article": str(product.get("supplierArticle") or "") or None,
                    "subject": subject,
                    "text": question_text,
                    "rating": None,
                    "status": mapped_status,
                    "priority": mapped_priority,
                    "needs_response": needs_response,
                    "source": "wb_api",
                    "occurred_at": occurred_at,
                    "extra_data": channel_meta,
                }

                if existing:
                    payload["extra_data"] = _merge_extra_data(existing.extra_data, channel_meta)
                    for key, value in payload.items():
                        setattr(existing, key, value)
                    stats.updated += 1
                    touched_ids.add(existing.id)
                else:
                    interaction = Interaction(
                        seller_id=seller_id,
                        marketplace=marketplace,
                        channel="question",
                        external_id=external_id,
                        **payload,
                    )
                    db.add(interaction)
                    await db.flush()
                    touched_ids.add(interaction.id)
                    stats.created += 1

            if len(questions) < take:
                break
            skip += take

    await refresh_link_candidates_for_interactions(
        db=db,
        seller_id=seller_id,
        interaction_ids=touched_ids,
    )
    return stats.as_dict()


async def ingest_chat_interactions(
    *,
    db: AsyncSession,
    seller_id: int,
    max_items: int = 500,
    direct_wb_fetch: bool = False,
) -> Dict[str, int]:
    """
    Ingest existing chat threads into unified interactions.

    Uses already-synced chat table as source of truth for channel=chat.
    Optional direct WB fetch can be enabled for pilot environments where
    chat worker is not running yet.
    """
    stats = IngestStats()
    touched_ids: set[int] = set()

    result = await db.execute(
        select(Chat)
        .where(and_(Chat.seller_id == seller_id, Chat.marketplace == "wildberries"))
        .order_by(Chat.last_message_at.desc().nullslast(), Chat.updated_at.desc())
        .limit(max_items)
    )
    chats = result.scalars().all()
    stats.fetched = len(chats)

    if not chats and direct_wb_fetch:
        connector = await get_wb_connector_for_seller(seller_id, db)
        direct_payload = await connector.fetch_messages_as_chats()
        direct_chats = direct_payload.get("chats") or []

        stats.fetched = len(direct_chats)
        for wb_chat in direct_chats[:max_items]:
            external_chat_id = str(wb_chat.get("external_chat_id") or "").strip()
            if not external_chat_id:
                stats.skipped += 1
                continue

            unread_count = int(wb_chat.get("unread_count") or 0)
            needs_response = unread_count > 0
            mapped_status = "open" if needs_response else "responded"
            mapped_priority = "high" if unread_count > 0 else "normal"
            occurred_at = _as_utc_dt(wb_chat.get("last_message_at"))
            good_card = wb_chat.get("good_card") if isinstance(wb_chat.get("good_card"), dict) else {}
            nm_id = str(good_card.get("nmID") or "") or None
            order_id = str(good_card.get("rid") or "") or None

            customer_name = (wb_chat.get("client_name") or "").strip()
            subject = "Чат с покупателем"
            if customer_name:
                subject = f"{subject} · {customer_name}"

            existing_result = await db.execute(
                select(Interaction).where(
                    and_(
                        Interaction.seller_id == seller_id,
                        Interaction.channel == "chat",
                        Interaction.external_id == external_chat_id,
                    )
                )
            )
            existing = existing_result.scalar_one_or_none()

            channel_meta = {
                "customer_name": customer_name or None,
                "client_id": (wb_chat.get("client_id") or None),
                "unread_count": unread_count,
                "is_new_chat": bool(wb_chat.get("is_new_chat")),
                "good_card": good_card or None,
                "source_mode": "wb_events_direct",
            }
            payload = {
                "marketplace": "wildberries",
                "customer_id": (wb_chat.get("client_id") or None),
                "order_id": order_id,
                "nm_id": nm_id,
                "product_article": nm_id,
                "subject": subject,
                "text": (wb_chat.get("last_message_text") or "").strip(),
                "rating": None,
                "status": mapped_status,
                "priority": mapped_priority,
                "needs_response": needs_response,
                "source": "wb_api",
                "occurred_at": occurred_at,
                "extra_data": channel_meta,
            }

            if existing:
                payload["extra_data"] = _merge_extra_data(existing.extra_data, channel_meta)
                for key, value in payload.items():
                    setattr(existing, key, value)
                stats.updated += 1
                touched_ids.add(existing.id)
            else:
                interaction = Interaction(
                    seller_id=seller_id,
                    channel="chat",
                    external_id=external_chat_id,
                    **payload,
                )
                db.add(interaction)
                await db.flush()
                touched_ids.add(interaction.id)
                stats.created += 1

        await refresh_link_candidates_for_interactions(
            db=db,
            seller_id=seller_id,
            interaction_ids=touched_ids,
        )
        return stats.as_dict()

    for chat in chats:
        needs_response = chat.chat_status in {"waiting", "client-replied"}
        mapped_status = "open" if needs_response else "responded"
        mapped_priority = chat.sla_priority if chat.sla_priority else "normal"

        text = (chat.last_message_preview or "").strip()
        subject = "Чат с покупателем"
        if chat.customer_name:
            subject = f"{subject} · {chat.customer_name}"
        if chat.product_name:
            subject = f"{subject} · {chat.product_name}"

        existing_result = await db.execute(
            select(Interaction).where(
                and_(
                    Interaction.seller_id == seller_id,
                    Interaction.channel == "chat",
                    Interaction.external_id == chat.marketplace_chat_id,
                )
            )
        )
        existing = existing_result.scalar_one_or_none()

        channel_meta = {
            "chat_id": chat.id,
            "chat_status": chat.chat_status,
            "unread_count": chat.unread_count,
            "sla_priority": chat.sla_priority,
            "product_name": chat.product_name,
            "customer_name": chat.customer_name,
        }

        payload = {
            "marketplace": chat.marketplace,
            "customer_id": chat.customer_id,
            "order_id": chat.order_id,
            "nm_id": chat.product_article,
            "product_article": chat.product_article,
            "subject": subject,
            "text": text,
            "rating": None,
            "status": mapped_status,
            "priority": mapped_priority,
            "needs_response": needs_response,
            "source": "wb_api",
            "occurred_at": chat.last_message_at,
            "extra_data": channel_meta,
        }

        if existing:
            payload["extra_data"] = _merge_extra_data(existing.extra_data, channel_meta)
            for key, value in payload.items():
                setattr(existing, key, value)
            stats.updated += 1
            touched_ids.add(existing.id)
        else:
            interaction = Interaction(
                seller_id=seller_id,
                channel="chat",
                external_id=chat.marketplace_chat_id,
                **payload,
            )
            db.add(interaction)
            await db.flush()
            touched_ids.add(interaction.id)
            stats.created += 1

    await refresh_link_candidates_for_interactions(
        db=db,
        seller_id=seller_id,
        interaction_ids=touched_ids,
    )
    return stats.as_dict()
