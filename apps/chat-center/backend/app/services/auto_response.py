"""Auto-response service for positive feedback (reviews with 4-5 stars).

MVP scope: auto-respond ONLY to `thanks` intent on 4-5 star reviews
when the seller has `auto_response_enabled=True` in their SLA config.

Safety rules:
- NEVER auto-respond to ratings <= 3
- NEVER auto-respond if guardrails fail (any error-severity warning)
- If ANY step fails, skip silently (seller can respond manually)
- Log all auto-response attempts (success and failure reasons)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent
from app.models.seller import Seller
from app.services.guardrails import apply_guardrails
from app.services.interaction_drafts import generate_interaction_draft, DraftResult
from app.services.sla_config import get_sla_config

logger = logging.getLogger(__name__)

# Minimum rating for auto-response (safety guard)
MIN_AUTO_RESPONSE_RATING = 4


async def process_auto_response(
    db: AsyncSession,
    interaction: Interaction,
    ai_result: Dict[str, Any],
    seller: Seller,
) -> bool:
    """Check if interaction qualifies for auto-response and send it.

    Returns True if auto-response was sent, False otherwise.

    Steps:
    1. Check seller's SLA config: auto_response_enabled == True
    2. Check channel against auto_response_channels whitelist
    2b. Check nm_id against auto_response_nm_ids whitelist (empty = all)
    3. Check intent: ai_result["intent"] in auto_response_intents
    4. Check rating: must be 4-5 (safety -- never auto-respond to negatives)
    5. Generate AI draft via generate_interaction_draft()
    6. Run guardrails check on the draft
    7. If guardrails pass -> send reply via WB connector
    8. Mark interaction: is_auto_response=True, status='responded'
    9. Log the auto-response
    """
    interaction_id = interaction.id
    seller_id = seller.id

    # --- Step 1: Check seller's auto-response setting ---
    try:
        sla_config = await get_sla_config(db, seller_id)
    except Exception as exc:
        logger.warning(
            "auto_response: failed to read SLA config seller=%s interaction=%s: %s",
            seller_id, interaction_id, exc,
        )
        return False

    if not sla_config.get("auto_response_enabled", False):
        logger.debug(
            "auto_response: disabled for seller=%s, skipping interaction=%s",
            seller_id, interaction_id,
        )
        return False

    # --- Step 2: Check channel against allowed channels ---
    channel = interaction.channel or "review"
    allowed_channels = sla_config.get("auto_response_channels", ["review"])
    if channel not in allowed_channels:
        logger.debug(
            "auto_response: channel=%s not in allowed_channels=%s for seller=%s interaction=%s",
            channel, allowed_channels, seller_id, interaction_id,
        )
        return False

    # --- Step 2b: Check nm_id whitelist (empty = all articles) ---
    nm_id_whitelist = sla_config.get("auto_response_nm_ids", [])
    if nm_id_whitelist:
        interaction_nm_id = interaction.nm_id
        # nm_id is stored as String in DB; compare as int when possible
        nm_id_match = False
        if interaction_nm_id:
            try:
                nm_id_int = int(interaction_nm_id)
                nm_id_match = nm_id_int in nm_id_whitelist
            except (ValueError, TypeError):
                nm_id_match = False
        if not nm_id_match:
            logger.debug(
                "auto_response: nm_id=%s not in whitelist=%s for seller=%s interaction=%s",
                interaction_nm_id, nm_id_whitelist, seller_id, interaction_id,
            )
            return False

    # --- Step 3: Check intent ---
    intent = ai_result.get("intent", "")
    allowed_intents = sla_config.get("auto_response_intents", [])
    if intent not in allowed_intents:
        logger.debug(
            "auto_response: intent=%s not in allowed_intents=%s for seller=%s interaction=%s",
            intent, allowed_intents, seller_id, interaction_id,
        )
        return False

    # --- Step 4: Check rating (SAFETY -- never auto-respond to negatives) ---
    rating = interaction.rating
    if rating is None or rating < MIN_AUTO_RESPONSE_RATING:
        logger.info(
            "auto_response: BLOCKED -- rating=%s < %s for interaction=%s seller=%s (safety guard)",
            rating, MIN_AUTO_RESPONSE_RATING, interaction_id, seller_id,
        )
        return False

    # --- Step 5: Generate AI draft ---
    try:
        draft: DraftResult = await generate_interaction_draft(
            db=db,
            interaction=interaction,
        )
    except Exception as exc:
        logger.warning(
            "auto_response: draft generation failed interaction=%s seller=%s: %s",
            interaction_id, seller_id, exc,
        )
        return False

    if not draft or not draft.text or not draft.text.strip():
        logger.warning(
            "auto_response: empty draft for interaction=%s seller=%s",
            interaction_id, seller_id,
        )
        return False

    reply_text = draft.text.strip()

    # --- Step 6: Run guardrails check ---
    customer_text = interaction.text or ""
    _, warnings = apply_guardrails(reply_text, channel, customer_text)

    # Block auto-response if ANY error-severity warning
    error_warnings = [w for w in warnings if w.get("severity") == "error"]
    if error_warnings:
        warning_msgs = "; ".join(w.get("message", str(w)) for w in error_warnings)
        logger.info(
            "auto_response: BLOCKED by guardrails interaction=%s seller=%s warnings=[%s]",
            interaction_id, seller_id, warning_msgs,
        )
        return False

    # --- Step 7: Send reply via WB connector ---
    try:
        sent = await _send_reply(db, interaction, seller, reply_text)
    except Exception as exc:
        logger.warning(
            "auto_response: send failed interaction=%s seller=%s: %s",
            interaction_id, seller_id, exc,
        )
        return False

    if not sent:
        logger.warning(
            "auto_response: send returned False interaction=%s seller=%s",
            interaction_id, seller_id,
        )
        return False

    # --- Step 8: Mark interaction ---
    now_iso = datetime.now(timezone.utc).isoformat()
    interaction.is_auto_response = True
    interaction.status = "responded"
    interaction.needs_response = False
    interaction.priority = "low"

    base_meta = interaction.extra_data if isinstance(interaction.extra_data, dict) else {}
    interaction.extra_data = {
        **base_meta,
        "last_reply_text": reply_text[:500],
        "last_reply_source": "auto_response",
        "last_reply_at": now_iso,
        "auto_response_intent": intent,
        "auto_response_draft_source": draft.source,
        "last_ai_draft": draft.as_dict(),
    }

    # Record event for metrics
    event = InteractionEvent(
        interaction_id=interaction.id,
        seller_id=seller_id,
        channel=interaction.channel or "review",
        event_type="auto_response_sent",
        details={
            "intent": intent,
            "rating": rating,
            "draft_source": draft.source,
            "reply_length": len(reply_text),
        },
    )
    db.add(event)

    await db.commit()

    # --- Step 9: Log success ---
    logger.info(
        "auto_response: SUCCESS interaction=%s seller=%s intent=%s rating=%s len=%s source=%s",
        interaction_id, seller_id, intent, rating, len(reply_text), draft.source,
    )
    return True


async def _send_reply(
    db: AsyncSession,
    interaction: Interaction,
    seller: Seller,
    reply_text: str,
) -> bool:
    """Send reply to the marketplace for the given interaction.

    Returns True on success, False on failure.
    Raises on unexpected errors.
    """
    channel = interaction.channel or "review"

    if channel == "review":
        from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller

        connector = await get_wb_feedbacks_connector_for_seller(seller.id, db)
        return await connector.answer_feedback(
            feedback_id=interaction.external_id,
            text=reply_text,
        )
    elif channel == "question":
        from app.services.wb_questions_connector import get_wb_questions_connector_for_seller

        connector = await get_wb_questions_connector_for_seller(seller.id, db)
        state = "wbRu"
        if isinstance(interaction.extra_data, dict):
            raw_state = interaction.extra_data.get("state")
            if raw_state in {"wbRu", "none"}:
                state = raw_state
        await connector.patch_question(
            question_id=interaction.external_id,
            state=state,
            answer_text=reply_text,
        )
        return True
    else:
        logger.warning(
            "auto_response: unsupported channel=%s for interaction=%s",
            channel, interaction.id,
        )
        return False
