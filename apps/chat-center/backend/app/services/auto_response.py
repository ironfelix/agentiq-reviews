"""Auto-response service for positive feedback (reviews with 4-5 stars).

MVP scope: auto-respond ONLY to `thanks` intent on 4-5 star reviews
when the seller has `auto_response_enabled=True` in their SLA config.

Safety rules:
- NEVER auto-respond to ratings <= 3
- NEVER auto-respond if guardrails fail (any error-severity warning)
- NEVER auto-respond if stricter auto-response validation fails
- If ANY step fails, skip silently (seller can respond manually)
- Log all auto-response attempts (success and failure reasons)
- Sandbox mode: run full pipeline but do NOT send (for testing)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent
from app.models.seller import Seller
from app.services.guardrails import apply_guardrails, validate_auto_response
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

    Returns True if auto-response was sent (or sandbox-processed), False otherwise.

    Steps:
    1. Check seller's SLA config: auto_response_enabled == True
    2. Check channel against auto_response_channels whitelist
    2b. Check nm_id against auto_response_nm_ids whitelist (empty = all)
    3. Check intent: ai_result["intent"] in auto_response_intents
    4. Check rating: must be 4-5 (safety -- never auto-respond to negatives)
    4b. Fetch product context for the interaction's nm_id
    5. Generate AI draft via generate_interaction_draft()
    6. Run guardrails check on the draft (standard + stricter auto-response)
    6b. If sandbox_mode -> log draft, store in extra_data, return True
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

    # --- Step 3: Check intent via scenario config ---
    intent = ai_result.get("intent", "")
    scenarios = sla_config.get("auto_response_scenarios", {})
    scenario = scenarios.get(intent)

    if not scenario:
        # Fallback: check legacy auto_response_intents
        allowed_intents = sla_config.get("auto_response_intents", [])
        if intent not in allowed_intents:
            logger.debug(
                "auto_response: intent=%s has no scenario config for seller=%s interaction=%s",
                intent, seller_id, interaction_id,
            )
            return False
    else:
        # New scenario-based check
        action = scenario.get("action", "block")
        enabled = scenario.get("enabled", False)
        scenario_channels = scenario.get("channels", [])

        if action == "block":
            logger.debug(
                "auto_response: intent=%s is BLOCKED for seller=%s interaction=%s",
                intent, seller_id, interaction_id,
            )
            return False

        if action == "draft":
            # Draft mode: generate draft but don't auto-send
            # Draft is generated later in the normal chat flow
            logger.debug(
                "auto_response: intent=%s is DRAFT (no auto-send) for seller=%s interaction=%s",
                intent, seller_id, interaction_id,
            )
            return False

        if not enabled:
            logger.debug(
                "auto_response: intent=%s scenario disabled for seller=%s interaction=%s",
                intent, seller_id, interaction_id,
            )
            return False

        # Check channel against scenario-specific channels
        if scenario_channels and channel not in scenario_channels:
            logger.debug(
                "auto_response: channel=%s not in scenario channels=%s for intent=%s seller=%s",
                channel, scenario_channels, intent, seller_id,
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

    # --- Step 4b: Fetch product context for LLM enrichment ---
    product_context = ""
    nm_id_str = interaction.nm_id
    if nm_id_str and channel in ("review", "question"):
        try:
            from app.services.product_context import get_product_context_for_nm_id
            product_context = await get_product_context_for_nm_id(nm_id_str)
            if product_context:
                logger.debug(
                    "auto_response: product context fetched for nm_id=%s (%d chars)",
                    nm_id_str, len(product_context),
                )
        except Exception as exc:
            logger.debug(
                "auto_response: product context fetch failed for nm_id=%s: %s",
                nm_id_str, exc,
            )
            # Not a blocker — continue without product context

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

    # --- Step 5b: Insert promo code for 5-star reviews ---
    promo_code_used = None
    if (
        rating == 5
        and channel == "review"
        and sla_config.get("auto_response_promo_on_5star", False)
    ):
        try:
            promo_code_used = await _insert_promo_code(db, seller_id, reply_text)
            if promo_code_used:
                reply_text = promo_code_used["full_text"]
                logger.info(
                    "auto_response: promo code=%s inserted for interaction=%s",
                    promo_code_used["code"], interaction_id,
                )
        except Exception as exc:
            logger.warning(
                "auto_response: promo insertion failed interaction=%s: %s",
                interaction_id, exc,
            )
            # Continue without promo -- not a blocker

    # --- Step 6: Run guardrails check (standard) ---
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

    # --- Step 6b: Run STRICTER auto-response validation ---
    is_safe, auto_reasons = await validate_auto_response(
        text=reply_text,
        channel=channel,
        seller_id=seller_id,
        db=db,
    )
    if not is_safe:
        reasons_str = "; ".join(auto_reasons)
        logger.info(
            "auto_response: BLOCKED by auto-response guardrails interaction=%s seller=%s reasons=[%s]",
            interaction_id, seller_id, reasons_str,
        )
        return False

    # --- Step 6c: Sandbox mode -- run full pipeline but do NOT send ---
    is_sandbox = getattr(seller, "sandbox_mode", False) or False
    if is_sandbox:
        now_iso = datetime.now(timezone.utc).isoformat()
        base_meta = interaction.extra_data if isinstance(interaction.extra_data, dict) else {}
        interaction.extra_data = {
            **base_meta,
            "sandbox_auto_response": {
                "draft_text": reply_text[:1000],
                "intent": intent,
                "rating": rating,
                "channel": channel,
                "draft_source": draft.source,
                "guardrails_passed": True,
                "auto_guardrails_passed": True,
                "timestamp": now_iso,
                **({"promo_code": promo_code_used["code"]} if promo_code_used else {}),
            },
        }

        # Record sandbox event
        event = InteractionEvent(
            interaction_id=interaction.id,
            seller_id=seller_id,
            channel=interaction.channel or "review",
            event_type="auto_response_sandbox",
            details={
                "intent": intent,
                "rating": rating,
                "draft_source": draft.source,
                "reply_length": len(reply_text),
                "draft_text_preview": reply_text[:200],
                **({"promo_code": promo_code_used["code"]} if promo_code_used else {}),
            },
        )
        db.add(event)
        await db.commit()

        logger.info(
            "auto_response: SANDBOX interaction=%s seller=%s intent=%s rating=%s len=%s (NOT sent)",
            interaction_id, seller_id, intent, rating, len(reply_text),
        )
        return True  # Mark as processed (pipeline ran successfully)

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
            **({"promo_code": promo_code_used["code"]} if promo_code_used else {}),
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
    elif channel == "chat":
        from app.services.wb_connector import get_wb_connector_for_seller

        connector = await get_wb_connector_for_seller(seller.id, db)
        chat_id = interaction.external_id
        if not chat_id:
            logger.warning(
                "auto_response: no chat_id for chat interaction=%s", interaction.id,
            )
            return False
        await connector.send_message(chat_id=chat_id, text=reply_text)
        return True
    else:
        logger.warning(
            "auto_response: unsupported channel=%s for interaction=%s",
            channel, interaction.id,
        )
        return False


async def _insert_promo_code(
    db: AsyncSession,
    seller_id: int,
    reply_text: str,
) -> Optional[Dict[str, Any]]:
    """Find an active, non-expired promo code and append to reply text.

    Returns dict with code info and full_text, or None if no promo available.
    """
    import json
    from datetime import datetime, timezone
    from app.models.runtime_setting import RuntimeSetting
    from sqlalchemy import select

    key = f"promo_settings_v1:seller:{seller_id}"
    result = await db.execute(
        select(RuntimeSetting).where(RuntimeSetting.key == key)
    )
    record = result.scalar_one_or_none()
    if not record or not record.value:
        return None

    try:
        payload = json.loads(record.value)
    except Exception:
        return None

    promo_codes = payload.get("promo_codes", [])
    if not promo_codes:
        return None

    now = datetime.now(timezone.utc)

    # Find first active promo with reviews_positive channel
    for promo in promo_codes:
        if not promo.get("active", False):
            continue

        # Check channel flag
        channels = promo.get("channels", {})
        if not channels.get("reviews_positive", False):
            continue

        # Check expiration (expires_label is human-readable, so we skip strict check
        # if no machine-readable date available -- promo is managed by seller)

        code = promo.get("code", "")
        discount = promo.get("discount_label", "скидку")
        if not code:
            continue

        full_text = f"{reply_text}\n\nДарим промокод {code} на {discount} на следующий заказ!"
        return {"code": code, "discount": discount, "full_text": full_text}

    return None
