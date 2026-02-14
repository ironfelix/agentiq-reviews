"""AI draft generation for unified interactions."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.interaction import Interaction
from app.models.message import Message
from app.services.ai_analyzer import AIAnalyzer, analyze_chat_for_db, _get_seller_tone
from app.services.guardrails import apply_guardrails
from app.services.llm_runtime import get_llm_runtime_config
from app.services.product_context import (
    build_rating_context,
    get_product_context_for_nm_id,
)

logger = logging.getLogger(__name__)


@dataclass
class DraftResult:
    text: str
    intent: Optional[str]
    sentiment: Optional[str]
    sla_priority: Optional[str]
    recommendation_reason: Optional[str]
    source: str
    guardrail_warnings: List[Dict] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.guardrail_warnings is None:
            self.guardrail_warnings = []

    def as_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "text": self.text,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "sla_priority": self.sla_priority,
            "recommendation_reason": self.recommendation_reason,
            "source": self.source,
        }
        if self.guardrail_warnings:
            d["guardrail_warnings"] = self.guardrail_warnings
        return d


def _fallback_draft(interaction: Interaction) -> DraftResult:
    text = (interaction.text or "").lower()
    if interaction.channel == "review":
        if interaction.rating and interaction.rating <= 3:
            draft = "Здравствуйте! Спасибо за отзыв. Нам жаль, что товар не оправдал ожиданий. Уточните, пожалуйста, детали — постараемся помочь."
        else:
            draft = "Здравствуйте! Спасибо за отзыв и обратную связь. Если будут вопросы по товару, с радостью поможем."
    elif interaction.channel == "question":
        draft = "Здравствуйте! Спасибо за вопрос. Уточняем информацию по товару и сразу вернемся с точным ответом."
        if any(w in text for w in ["размер", "рост", "вес"]):
            draft = "Здравствуйте! Спасибо за вопрос. Подскажите, пожалуйста, ваши параметры (рост/вес), чтобы мы точно подсказали размер."
    else:
        draft = "Здравствуйте! Спасибо за обращение. Поможем разобраться и подскажем оптимальное решение."

    return DraftResult(
        text=draft,
        intent=None,
        sentiment=None,
        sla_priority=interaction.priority,
        recommendation_reason="Fallback draft",
        source="fallback",
    )


async def _resolve_chat_for_interaction(db: AsyncSession, interaction: Interaction) -> Optional[Chat]:
    chat_id: Optional[int] = None
    if isinstance(interaction.extra_data, dict):
        raw_chat_id = interaction.extra_data.get("chat_id")
        if isinstance(raw_chat_id, int):
            chat_id = raw_chat_id
        elif isinstance(raw_chat_id, str) and raw_chat_id.isdigit():
            chat_id = int(raw_chat_id)

    if chat_id is not None:
        result = await db.execute(
            select(Chat).where(and_(Chat.id == chat_id, Chat.seller_id == interaction.seller_id))
        )
        chat = result.scalar_one_or_none()
        if chat:
            return chat

    result = await db.execute(
        select(Chat).where(
            and_(
                Chat.seller_id == interaction.seller_id,
                Chat.marketplace_chat_id == interaction.external_id,
            )
        )
    )
    return result.scalar_one_or_none()


def _apply_guardrails_to_draft(draft: DraftResult, interaction: Interaction) -> DraftResult:
    """Run channel-specific guardrails on a completed draft.

    Guardrails are additive: they attach warnings but do NOT modify the text.
    """
    customer_text = interaction.text or ""
    channel = interaction.channel or "review"

    _, warnings = apply_guardrails(draft.text, channel, customer_text)
    draft.guardrail_warnings = warnings
    return draft


async def generate_interaction_draft(
    *,
    db: AsyncSession,
    interaction: Interaction,
) -> DraftResult:
    """Generate AI draft for interaction channel.

    Enriches the LLM prompt with:
    - Product card context (description, specs, compositions) from WB CDN
    - Rating-aware instructions (empathetic for negative, grateful for positive)
    """
    if interaction.channel == "chat":
        chat = await _resolve_chat_for_interaction(db, interaction)
        if chat:
            analysis = await analyze_chat_for_db(chat.id, db)
            if analysis and analysis.get("recommendation"):
                draft = DraftResult(
                    text=analysis["recommendation"],
                    intent=analysis.get("intent"),
                    sentiment=analysis.get("sentiment"),
                    sla_priority=analysis.get("sla_priority"),
                    recommendation_reason=analysis.get("recommendation_reason"),
                    source="llm" if analysis.get("recommendation_reason") != "Fallback: LLM unavailable" else "fallback",
                )
                return _apply_guardrails_to_draft(draft, interaction)

    # --- Product context enrichment ---
    # Fetch product card from WB CDN (cached, no auth, 5s timeout)
    product_context = ""
    channel = interaction.channel or "review"
    nm_id_str = interaction.nm_id if hasattr(interaction, "nm_id") else None

    if nm_id_str and channel in ("review", "question"):
        try:
            product_context = await get_product_context_for_nm_id(nm_id_str)
        except Exception as exc:
            logger.debug("Product context fetch failed for nm_id=%s: %s", nm_id_str, exc)

    # --- Rating-aware context ---
    rating_context = build_rating_context(interaction.rating, channel)

    # --- Seller tone preference ---
    tone = await _get_seller_tone(db, interaction.seller_id)

    llm_runtime = await get_llm_runtime_config(db)
    analyzer = AIAnalyzer(
        provider=llm_runtime.provider,
        model_name=llm_runtime.model_name,
        enabled=llm_runtime.enabled,
    )

    # Build message block with rating prefix for reviews
    message_text = interaction.text or interaction.subject or ""
    if channel == "review" and interaction.rating is not None:
        rating_stars = "*" * interaction.rating
        message_text = f"[{rating_stars} ({interaction.rating}/5)] {message_text}"

    messages = [
        {
            "text": message_text,
            "author_type": "buyer",
            "created_at": interaction.occurred_at or datetime.utcnow(),
        }
    ]
    customer_name = None
    if isinstance(interaction.extra_data, dict):
        customer_name = interaction.extra_data.get("user_name")

    analysis = await analyzer.analyze_chat(
        messages=messages,
        product_name=interaction.subject or "Товар",
        customer_name=customer_name,
        product_context=product_context,
        rating_context=rating_context,
        channel=channel,
        tone=tone,
        rating=interaction.rating,
    )

    if analysis and analysis.get("recommendation"):
        draft = DraftResult(
            text=analysis["recommendation"],
            intent=analysis.get("intent"),
            sentiment=analysis.get("sentiment"),
            sla_priority=analysis.get("sla_priority"),
            recommendation_reason=analysis.get("recommendation_reason"),
            source="llm" if analysis.get("recommendation_reason") != "Fallback: LLM unavailable" else "fallback",
        )
        return _apply_guardrails_to_draft(draft, interaction)

    draft = _fallback_draft(interaction)
    return _apply_guardrails_to_draft(draft, interaction)
