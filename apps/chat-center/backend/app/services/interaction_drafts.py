"""AI draft generation for unified interactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import Chat
from app.models.interaction import Interaction
from app.models.message import Message
from app.services.ai_analyzer import AIAnalyzer, analyze_chat_for_db
from app.services.llm_runtime import get_llm_runtime_config


@dataclass
class DraftResult:
    text: str
    intent: Optional[str]
    sentiment: Optional[str]
    sla_priority: Optional[str]
    recommendation_reason: Optional[str]
    source: str

    def as_dict(self) -> Dict[str, Optional[str]]:
        return {
            "text": self.text,
            "intent": self.intent,
            "sentiment": self.sentiment,
            "sla_priority": self.sla_priority,
            "recommendation_reason": self.recommendation_reason,
            "source": self.source,
        }


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


async def generate_interaction_draft(
    *,
    db: AsyncSession,
    interaction: Interaction,
) -> DraftResult:
    """Generate AI draft for interaction channel."""
    if interaction.channel == "chat":
        chat = await _resolve_chat_for_interaction(db, interaction)
        if chat:
            analysis = await analyze_chat_for_db(chat.id, db)
            if analysis and analysis.get("recommendation"):
                return DraftResult(
                    text=analysis["recommendation"],
                    intent=analysis.get("intent"),
                    sentiment=analysis.get("sentiment"),
                    sla_priority=analysis.get("sla_priority"),
                    recommendation_reason=analysis.get("recommendation_reason"),
                    source="llm" if analysis.get("recommendation_reason") != "Fallback: LLM unavailable" else "fallback",
                )

    llm_runtime = await get_llm_runtime_config(db)
    analyzer = AIAnalyzer(
        provider=llm_runtime.provider,
        model_name=llm_runtime.model_name,
        enabled=llm_runtime.enabled,
    )
    messages = [
        {
            "text": interaction.text or interaction.subject or "",
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
    )

    if analysis and analysis.get("recommendation"):
        return DraftResult(
            text=analysis["recommendation"],
            intent=analysis.get("intent"),
            sentiment=analysis.get("sentiment"),
            sla_priority=analysis.get("sla_priority"),
            recommendation_reason=analysis.get("recommendation_reason"),
            source="llm" if analysis.get("recommendation_reason") != "Fallback: LLM unavailable" else "fallback",
        )

    return _fallback_draft(interaction)
