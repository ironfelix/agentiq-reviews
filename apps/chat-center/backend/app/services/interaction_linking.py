"""Cross-channel interaction linking (deterministic + probabilistic)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction

MIN_LINK_CONFIDENCE = 0.55
AUTO_ACTION_MIN_CONFIDENCE = 0.85
PRODUCT_THREAD_WINDOW_DAYS = 45


def _wb_channel_url(channel: str) -> str:
    if channel == "review":
        return "https://seller.wildberries.ru/communication/reviews"
    if channel == "question":
        return "https://seller.wildberries.ru/communication/questions"
    return "https://seller.wildberries.ru/communication/chats"


def _to_utc_aware(value: datetime) -> datetime:
    """Normalize datetime to UTC aware to avoid naive/aware arithmetic errors."""
    tzinfo = value.tzinfo
    if tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    try:
        if tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
    except Exception:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _normalize_text(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value


def _time_distance_hours(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    if not a or not b:
        return None
    a_utc = _to_utc_aware(a)
    b_utc = _to_utc_aware(b)
    return abs((a_utc - b_utc).total_seconds()) / 3600.0


def evaluate_link_action_policy(
    *,
    link_type: str,
    confidence: float,
) -> dict[str, Any]:
    """
    Guardrail policy:
    - Auto-actions are allowed only for deterministic links.
    - Probabilistic links are always assist-only.
    - Deterministic links also require confidence threshold.
    """
    normalized_confidence = max(0.0, min(1.0, float(confidence)))

    if link_type != "deterministic":
        return {
            "auto_action_allowed": False,
            "action_mode": "assist_only",
            "policy_reason": "probabilistic_link_assist_only",
        }

    if normalized_confidence < AUTO_ACTION_MIN_CONFIDENCE:
        return {
            "auto_action_allowed": False,
            "action_mode": "assist_only",
            "policy_reason": "deterministic_below_confidence_threshold",
        }

    return {
        "auto_action_allowed": True,
        "action_mode": "auto_allowed",
        "policy_reason": "deterministic_confidence_ok",
    }


def _normalize_name(value: Optional[str]) -> str:
    if not isinstance(value, str):
        return ""
    value = value.strip().lower()
    value = re.sub(r"[^\w\sа-яА-ЯёЁ-]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _extract_person_name(interaction: Interaction) -> str:
    if isinstance(interaction.extra_data, dict):
        for key in ("user_name", "customer_name", "name"):
            raw = interaction.extra_data.get(key)
            normalized = _normalize_name(raw if isinstance(raw, str) else None)
            if normalized:
                return normalized
    return ""


def _overlap_tokens(a: str, b: str) -> float:
    tokens_a = {token for token in re.split(r"\W+", a) if len(token) > 2}
    tokens_b = {token for token in re.split(r"\W+", b) if len(token) > 2}
    if not tokens_a or not tokens_b:
        return 0.0
    inter = len(tokens_a & tokens_b)
    union = len(tokens_a | tokens_b)
    if union == 0:
        return 0.0
    return inter / union


def _build_candidate(current: Interaction, other: Interaction) -> Optional[dict[str, Any]]:
    score = 0.0
    signals: list[str] = []
    deterministic = False

    if current.order_id and other.order_id and current.order_id == other.order_id:
        score += 0.88
        signals.append("order_id_exact")
        deterministic = True

    if current.customer_id and other.customer_id and current.customer_id == other.customer_id:
        score += 0.68
        signals.append("customer_id_exact")
        deterministic = True

    if current.nm_id and other.nm_id and current.nm_id == other.nm_id:
        score += 0.34
        signals.append("nm_id_exact")

    if (
        current.product_article
        and other.product_article
        and current.product_article == other.product_article
    ):
        score += 0.28
        signals.append("product_article_exact")

    if current.occurred_at and other.occurred_at:
        current_at = _to_utc_aware(current.occurred_at)
        other_at = _to_utc_aware(other.occurred_at)
        delta_hours = abs((current_at - other_at).total_seconds()) / 3600.0
        if delta_hours <= 24:
            score += 0.16
            signals.append("time_window_24h")
        elif delta_hours <= 24 * 7:
            score += 0.10
            signals.append("time_window_7d")
        elif delta_hours <= 24 * 30:
            score += 0.05
            signals.append("time_window_30d")

    current_name = _extract_person_name(current)
    other_name = _extract_person_name(other)
    if current_name and other_name:
        if current_name == other_name:
            score += 0.12
            signals.append("name_match_probabilistic")
        elif current_name in other_name or other_name in current_name:
            score += 0.08
            signals.append("name_partial_match_probabilistic")

    text_current = _normalize_text(current.text)
    text_other = _normalize_text(other.text)
    if text_current and text_other:
        token_overlap = _overlap_tokens(text_current, text_other)
        if token_overlap >= 0.45:
            score += 0.10
            signals.append("semantic_overlap_high")
        elif token_overlap >= 0.25:
            score += 0.06
            signals.append("semantic_overlap_medium")

    if deterministic:
        score = max(score, 0.90)

    confidence = max(0.0, min(0.99, round(score, 3)))
    if confidence < MIN_LINK_CONFIDENCE:
        return None

    link_type = "deterministic" if deterministic else "probabilistic"
    policy = evaluate_link_action_policy(link_type=link_type, confidence=confidence)

    if "order_id_exact" in signals:
        explanation = "Детерминированная связка по order_id."
    elif "customer_id_exact" in signals:
        explanation = "Детерминированная связка по customer_id."
    elif "name_match_probabilistic" in signals or "name_partial_match_probabilistic" in signals:
        explanation = "Вероятностная связка по имени/ФИО с учетом контекста товара и времени."
    elif "nm_id_exact" in signals or "product_article_exact" in signals:
        explanation = "Связка по товарному контексту (nm_id/article) и временной близости."
    else:
        explanation = "Вероятностная связка по совокупности сигналов."

    return {
        "interaction_id": other.id,
        "channel": other.channel,
        "external_id": other.external_id,
        "confidence": confidence,
        "link_type": link_type,
        "auto_action_allowed": policy["auto_action_allowed"],
        "action_mode": policy["action_mode"],
        "policy_reason": policy["policy_reason"],
        "reasoning_signals": signals,
        "explanation": explanation,
    }


def _deterministic_match_reason(
    current: Interaction,
    other: Interaction,
    *,
    product_window_days: int = PRODUCT_THREAD_WINDOW_DAYS,
) -> Optional[tuple[str, float]]:
    if current.id == other.id:
        return ("current_interaction", 1.0)

    if current.order_id and other.order_id and current.order_id == other.order_id:
        return ("order_id_exact", 0.99)

    if current.customer_id and other.customer_id and current.customer_id == other.customer_id:
        return ("customer_id_exact", 0.95)

    delta_hours = _time_distance_hours(current.occurred_at, other.occurred_at)
    max_hours = product_window_days * 24

    if current.nm_id and other.nm_id and current.nm_id == other.nm_id:
        if delta_hours is None or delta_hours <= max_hours:
            return ("nm_id_time_window", 0.82)

    if (
        current.product_article
        and other.product_article
        and current.product_article == other.product_article
    ):
        if delta_hours is None or delta_hours <= max_hours:
            return ("article_time_window", 0.78)

    return None


def _build_timeline_query_conditions(current: Interaction) -> tuple[str, list[Any]]:
    product_conditions: list[Any] = []
    if current.nm_id:
        product_conditions.append(Interaction.nm_id == current.nm_id)
    if current.product_article:
        product_conditions.append(Interaction.product_article == current.product_article)

    if current.order_id:
        return ("customer_order", [Interaction.order_id == current.order_id, *product_conditions])
    if current.customer_id:
        return ("customer", [Interaction.customer_id == current.customer_id, *product_conditions])
    if product_conditions:
        return ("product", product_conditions)

    return ("single", [])


async def _fetch_interaction_candidates(
    db: AsyncSession,
    current: Interaction,
    *,
    max_candidates: int = 150,
) -> list[Interaction]:
    base_conditions = [
        Interaction.seller_id == current.seller_id,
        Interaction.marketplace == current.marketplace,
        Interaction.channel != current.channel,
        Interaction.id != current.id,
    ]

    anchor_conditions = []
    if current.order_id:
        anchor_conditions.append(Interaction.order_id == current.order_id)
    if current.customer_id:
        anchor_conditions.append(Interaction.customer_id == current.customer_id)
    if current.nm_id:
        anchor_conditions.append(Interaction.nm_id == current.nm_id)
    if current.product_article:
        anchor_conditions.append(Interaction.product_article == current.product_article)

    query = select(Interaction).where(and_(*base_conditions))
    if anchor_conditions:
        query = query.where(or_(*anchor_conditions))
    elif current.occurred_at:
        window_start = _to_utc_aware(current.occurred_at) - timedelta(days=30)
        query = query.where(Interaction.occurred_at >= window_start)

    query = (
        query.order_by(Interaction.occurred_at.desc().nullslast(), Interaction.created_at.desc())
        .limit(max_candidates)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_link_candidates_for_interaction(
    db: AsyncSession,
    interaction: Interaction,
    *,
    max_links: int = 5,
) -> list[dict[str, Any]]:
    """Compute and persist `extra_data.link_candidates` for one interaction."""
    candidates = await _fetch_interaction_candidates(db, interaction)
    scored: list[dict[str, Any]] = []
    for other in candidates:
        candidate = _build_candidate(interaction, other)
        if candidate:
            scored.append(candidate)

    scored.sort(key=lambda item: item["confidence"], reverse=True)
    top = scored[:max_links]

    metadata = interaction.extra_data if isinstance(interaction.extra_data, dict) else {}
    interaction.extra_data = {
        **metadata,
        "link_candidates": top,
        "link_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return top


async def refresh_link_candidates_for_interactions(
    db: AsyncSession,
    *,
    seller_id: int,
    interaction_ids: set[int],
    max_links: int = 5,
    refresh_reciprocal: bool = True,
) -> None:
    """Refresh link candidates for affected interactions after ingestion."""
    if not interaction_ids:
        return

    pending = set(interaction_ids)
    processed: set[int] = set()
    reciprocal_targets: set[int] = set()

    while pending:
        interaction_id = pending.pop()
        if interaction_id in processed:
            continue
        result = await db.execute(
            select(Interaction).where(
                and_(
                    Interaction.id == interaction_id,
                    Interaction.seller_id == seller_id,
                )
            )
        )
        interaction = result.scalar_one_or_none()
        if not interaction:
            processed.add(interaction_id)
            continue

        links = await update_link_candidates_for_interaction(db, interaction, max_links=max_links)
        processed.add(interaction_id)

        if refresh_reciprocal:
            for link in links:
                linked_id = link.get("interaction_id")
                if isinstance(linked_id, int) and linked_id not in processed:
                    reciprocal_targets.add(linked_id)

        if not pending and refresh_reciprocal and reciprocal_targets:
            pending = reciprocal_targets - processed
            reciprocal_targets.clear()


async def get_deterministic_thread_timeline(
    db: AsyncSession,
    *,
    interaction: Interaction,
    max_items: int = 100,
    product_window_days: int = PRODUCT_THREAD_WINDOW_DAYS,
) -> dict[str, Any]:
    """
    Build deterministic cross-channel timeline for one interaction.

    Thread levels:
    - customer_order: exact order_id
    - customer: exact customer_id
    - product: nm_id/article within time window
    - single: no deterministic keys, only current interaction
    """
    scope, key_conditions = _build_timeline_query_conditions(interaction)

    thread_key: dict[str, Optional[str]] = {
        "order_id": interaction.order_id,
        "customer_id": interaction.customer_id,
        "nm_id": interaction.nm_id,
        "product_article": interaction.product_article,
    }

    if scope == "single":
        policy = evaluate_link_action_policy(link_type="deterministic", confidence=1.0)
        return {
            "interaction_id": interaction.id,
            "thread_scope": scope,
            "thread_key": thread_key,
            "channels_present": [interaction.channel],
            "steps": [
                {
                    "interaction_id": interaction.id,
                    "channel": interaction.channel,
                    "external_id": interaction.external_id,
                    "occurred_at": interaction.occurred_at,
                    "status": interaction.status,
                    "priority": interaction.priority,
                    "needs_response": interaction.needs_response,
                    "subject": interaction.subject,
                    "match_reason": "current_interaction",
                    "confidence": 1.0,
                    "auto_action_allowed": policy["auto_action_allowed"],
                    "action_mode": policy["action_mode"],
                    "policy_reason": policy["policy_reason"],
                    "is_current": True,
                    "wb_url": _wb_channel_url(interaction.channel),
                    "last_reply_text": (
                        interaction.extra_data.get("last_reply_text")
                        if isinstance(interaction.extra_data, dict)
                        else None
                    ),
                    "last_ai_draft_text": (
                        interaction.extra_data.get("last_ai_draft", {}).get("text")
                        if isinstance(interaction.extra_data, dict)
                        and isinstance(interaction.extra_data.get("last_ai_draft"), dict)
                        else None
                    ),
                }
            ],
        }

    base_conditions = [
        Interaction.seller_id == interaction.seller_id,
        Interaction.marketplace == interaction.marketplace,
        or_(*key_conditions),
    ]

    query = select(Interaction).where(and_(*base_conditions))

    if scope == "product" and interaction.occurred_at:
        anchor = _to_utc_aware(interaction.occurred_at)
        window_start = anchor - timedelta(days=product_window_days)
        window_end = anchor + timedelta(days=product_window_days)
        query = query.where(
            and_(
                Interaction.occurred_at >= window_start,
                Interaction.occurred_at <= window_end,
            )
        )

    query = query.order_by(Interaction.occurred_at.asc().nullsfirst(), Interaction.created_at.asc()).limit(max_items)
    result = await db.execute(query)
    interactions = list(result.scalars().all())

    if not any(item.id == interaction.id for item in interactions):
        interactions.append(interaction)
        interactions.sort(key=lambda item: ((item.occurred_at or item.created_at), item.created_at))

    steps: list[dict[str, Any]] = []
    channels_present: set[str] = set()

    for item in interactions:
        match = _deterministic_match_reason(
            interaction,
            item,
            product_window_days=product_window_days,
        )
        if not match:
            continue
        match_reason, confidence = match
        policy = evaluate_link_action_policy(link_type="deterministic", confidence=confidence)
        channels_present.add(item.channel)
        steps.append(
            {
                "interaction_id": item.id,
                "channel": item.channel,
                "external_id": item.external_id,
                "occurred_at": item.occurred_at,
                "status": item.status,
                "priority": item.priority,
                "needs_response": item.needs_response,
                "subject": item.subject,
                "match_reason": match_reason,
                "confidence": confidence,
                "auto_action_allowed": policy["auto_action_allowed"],
                "action_mode": policy["action_mode"],
                "policy_reason": policy["policy_reason"],
                "is_current": item.id == interaction.id,
                "wb_url": _wb_channel_url(item.channel),
                "last_reply_text": (
                    item.extra_data.get("last_reply_text")
                    if isinstance(item.extra_data, dict)
                    else None
                ),
                "last_ai_draft_text": (
                    item.extra_data.get("last_ai_draft", {}).get("text")
                    if isinstance(item.extra_data, dict)
                    and isinstance(item.extra_data.get("last_ai_draft"), dict)
                    else None
                ),
            }
        )

    return {
        "interaction_id": interaction.id,
        "thread_scope": scope,
        "thread_key": thread_key,
        "channels_present": sorted(channels_present),
        "steps": steps,
    }
