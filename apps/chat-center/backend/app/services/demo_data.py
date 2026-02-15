"""Demo data seeder for skip-onboarding flow.

Creates realistic WB interactions so the inbox looks "alive"
when a user clicks "Пропустить подключение".
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interaction import Interaction
from app.models.interaction_event import InteractionEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Demo content definitions
# ---------------------------------------------------------------------------

_DEMO_REVIEWS = [
    {
        "external_id_suffix": "demo_rev_1",
        "subject": "Кроссовки мужские Nike Air",
        "text": "Кроссовки развалились через неделю! Подошва отклеилась. Ужасное качество.",
        "rating": 1,
        "status": "open",
        "priority": "urgent",
        "needs_response": True,
        "nm_id": "283741560",
        "customer_id": "buyer_demo_1",
        "occurred_offset_hours": -6,
        "extra": {
            "is_demo": True,
            "user_name": "Алексей К.",
            "advantages": "",
            "disadvantages": "Подошва отклеилась через неделю",
        },
    },
    {
        "external_id_suffix": "demo_rev_2",
        "subject": "Кроссовки женские беговые",
        "text": "Размер не соответствует. Заказала 38, пришёл маломерка. Еле налезли.",
        "rating": 2,
        "status": "open",
        "priority": "high",
        "needs_response": True,
        "nm_id": "194520381",
        "customer_id": "buyer_demo_2",
        "occurred_offset_hours": -18,
        "extra": {
            "is_demo": True,
            "user_name": "Мария С.",
            "advantages": "Красивый дизайн",
            "disadvantages": "Маломерят на размер",
        },
    },
    {
        "external_id_suffix": "demo_rev_3",
        "subject": "Кроссовки унисекс повседневные",
        "text": "В целом нормальные, но цвет чуть отличается от фото. На фото ярче.",
        "rating": 4,
        "status": "open",
        "priority": "normal",
        "needs_response": True,
        "nm_id": "310482756",
        "customer_id": "buyer_demo_3",
        "occurred_offset_hours": -48,
        "extra": {
            "is_demo": True,
            "user_name": "Дмитрий Л.",
            "advantages": "Удобные, лёгкие",
            "disadvantages": "Цвет отличается от фото",
        },
    },
    {
        "external_id_suffix": "demo_rev_4",
        "subject": "Кроссовки спортивные летние",
        "text": "Отличные кроссовки! Удобные, красивые, рекомендую!",
        "rating": 5,
        "status": "responded",
        "priority": "low",
        "needs_response": False,
        "nm_id": "310482756",
        "customer_id": "buyer_demo_4",
        "occurred_offset_hours": -72,
        "extra": {
            "is_demo": True,
            "user_name": "Елена В.",
            "advantages": "Удобные, красивые, лёгкие",
            "disadvantages": "",
            "last_reply_text": "Спасибо за отзыв! Рады, что кроссовки понравились!",
            "last_reply_source": "agentiq",
        },
    },
    {
        "external_id_suffix": "demo_rev_5",
        "subject": "Кроссовки мужские для зала",
        "text": "Качество нормальное, но доставка 2 недели. Долго ждал.",
        "rating": 3,
        "status": "open",
        "priority": "normal",
        "needs_response": True,
        "nm_id": "283741560",
        "customer_id": "buyer_demo_5",
        "occurred_offset_hours": -96,
        "extra": {
            "is_demo": True,
            "user_name": "Иван П.",
            "advantages": "Нормальное качество за свою цену",
            "disadvantages": "Долгая доставка",
        },
    },
]

_DEMO_QUESTIONS = [
    {
        "external_id_suffix": "demo_q_1",
        "subject": "Кроссовки мужские Nike Air",
        "text": "Подскажите, есть ли размер 42 в чёрном цвете?",
        "status": "open",
        "priority": "high",
        "needs_response": True,
        "nm_id": "283741560",
        "customer_id": "buyer_demo_6",
        "occurred_offset_hours": -3,
        "extra": {
            "is_demo": True,
            "user_name": "Андрей М.",
            "question_intent": "availability",
            "priority_reason": "Pre-purchase: покупатель сейчас на карточке товара",
            "sla_target_minutes": 5,
        },
    },
    {
        "external_id_suffix": "demo_q_2",
        "subject": "Кроссовки женские беговые",
        "text": "Какой размер выбрать если нога 25.5 см? Обычно ношу 39.",
        "status": "open",
        "priority": "high",
        "needs_response": True,
        "nm_id": "194520381",
        "customer_id": "buyer_demo_7",
        "occurred_offset_hours": -8,
        "extra": {
            "is_demo": True,
            "user_name": "Ольга Р.",
            "question_intent": "sizing_fit",
            "priority_reason": "Pre-purchase: вопрос о размере, покупатель сравнивает варианты",
            "sla_target_minutes": 5,
        },
    },
    {
        "external_id_suffix": "demo_q_3",
        "subject": "Кроссовки унисекс повседневные",
        "text": "Подойдут ли для бега по асфальту? Или только для зала?",
        "status": "open",
        "priority": "high",
        "needs_response": True,
        "nm_id": "310482756",
        "customer_id": "buyer_demo_8",
        "occurred_offset_hours": -26,
        "extra": {
            "is_demo": True,
            "user_name": "Сергей Н.",
            "question_intent": "pre_purchase",
            "priority_reason": "Pre-purchase: покупатель выбирает товар",
            "sla_target_minutes": 5,
        },
    },
    {
        "external_id_suffix": "demo_q_4",
        "subject": "Кроссовки спортивные летние",
        "text": "Когда будет поступление новых цветов? Хочу синий.",
        "status": "open",
        "priority": "normal",
        "needs_response": True,
        "nm_id": "310482756",
        "customer_id": "buyer_demo_9",
        "occurred_offset_hours": -52,
        "extra": {
            "is_demo": True,
            "user_name": "Наталья Д.",
            "question_intent": "availability",
            "priority_reason": "Вопрос о наличии конкретного варианта",
            "sla_target_minutes": 60,
        },
    },
]

_DEMO_CHATS = [
    {
        "external_id_suffix": "demo_chat_1",
        "subject": "Чат: дефект товара",
        "text": "Здравствуйте, получила заказ, но один кроссовок с дефектом — царапина на подошве. Можно заменить?",
        "status": "open",
        "priority": "urgent",
        "needs_response": True,
        "nm_id": "283741560",
        "customer_id": "buyer_demo_10",
        "order_id": "WB-9182736450",
        "occurred_offset_hours": -2,
        "extra": {
            "is_demo": True,
            "user_name": "Татьяна А.",
        },
    },
    {
        "external_id_suffix": "demo_chat_2",
        "subject": "Чат: вопрос о размере",
        "text": "Добрый день! Подскажите, 41 размер — это по стельке 26.5 см?",
        "status": "responded",
        "priority": "normal",
        "needs_response": False,
        "nm_id": "194520381",
        "customer_id": "buyer_demo_11",
        "order_id": None,
        "occurred_offset_hours": -30,
        "extra": {
            "is_demo": True,
            "user_name": "Виктор Г.",
            "last_reply_text": "Добрый день! Да, 41 размер соответствует стельке 26.5 см. Если у вас нога широкая, рекомендуем взять на размер больше.",
            "last_reply_source": "agentiq",
        },
        # Simulate buyer reply after seller response
        "buyer_followup": "Спасибо, заказала!",
    },
    {
        "external_id_suffix": "demo_chat_3",
        "subject": "Чат: уточнение по доставке",
        "text": "Когда приедет заказ? Уже 5 дней жду.",
        "status": "responded",
        "priority": "normal",
        "needs_response": False,
        "nm_id": "310482756",
        "customer_id": "buyer_demo_12",
        "order_id": "WB-5647382910",
        "occurred_offset_hours": -55,
        "extra": {
            "is_demo": True,
            "user_name": "Кирилл Б.",
            "last_reply_text": "Добрый день! По трекингу ваш заказ уже в пункте выдачи. Проверьте статус в приложении WB.",
            "last_reply_source": "agentiq",
        },
    },
]


async def seed_demo_interactions(
    db: AsyncSession,
    seller_id: int,
) -> dict:
    """
    Create demo interactions for a seller so the inbox looks alive.

    Returns a summary dict with created/skipped counts.
    Idempotent: skips if demo interactions already exist for the seller.
    """

    # Check if demo data already exists for this seller
    existing = await db.execute(
        select(Interaction.id).where(
            Interaction.seller_id == seller_id,
            Interaction.external_id.like("demo_%"),
        ).limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Demo data already exists for seller=%s, skipping seed", seller_id)
        return {"created": 0, "skipped": 1, "message": "Demo data already seeded"}

    now = datetime.now(timezone.utc)
    created_count = 0
    events_count = 0

    # --- Reviews ---
    for rev in _DEMO_REVIEWS:
        occurred = now + timedelta(hours=rev["occurred_offset_hours"])
        sla_due = occurred + timedelta(hours=1) if rev["priority"] == "urgent" else None
        extra = {**rev["extra"]}
        if sla_due:
            extra["sla_due_at"] = sla_due.isoformat()

        interaction = Interaction(
            seller_id=seller_id,
            marketplace="wb",
            channel="review",
            external_id=rev["external_id_suffix"],
            customer_id=rev.get("customer_id"),
            nm_id=rev.get("nm_id"),
            subject=rev.get("subject"),
            text=rev["text"],
            rating=rev.get("rating"),
            status=rev["status"],
            priority=rev["priority"],
            needs_response=rev["needs_response"],
            source="demo",
            occurred_at=occurred,
            extra_data=extra,
        )
        db.add(interaction)
        created_count += 1

        # If the review has a reply, create an event
        if extra.get("last_reply_text"):
            await db.flush()  # get interaction.id
            event = InteractionEvent(
                interaction_id=interaction.id,
                seller_id=seller_id,
                channel="review",
                event_type="reply_sent",
                details={
                    "text": extra["last_reply_text"],
                    "source": "demo",
                    "is_demo": True,
                },
                created_at=occurred + timedelta(hours=1),
            )
            db.add(event)
            events_count += 1

    # --- Questions ---
    for q in _DEMO_QUESTIONS:
        occurred = now + timedelta(hours=q["occurred_offset_hours"])
        extra = {**q["extra"]}
        sla_target = extra.get("sla_target_minutes", 60)
        sla_due = occurred + timedelta(minutes=sla_target)
        extra["sla_due_at"] = sla_due.isoformat()

        interaction = Interaction(
            seller_id=seller_id,
            marketplace="wb",
            channel="question",
            external_id=q["external_id_suffix"],
            customer_id=q.get("customer_id"),
            nm_id=q.get("nm_id"),
            subject=q.get("subject"),
            text=q["text"],
            status=q["status"],
            priority=q["priority"],
            needs_response=q["needs_response"],
            source="demo",
            occurred_at=occurred,
            extra_data=extra,
        )
        db.add(interaction)
        created_count += 1

    # --- Chats ---
    for chat in _DEMO_CHATS:
        occurred = now + timedelta(hours=chat["occurred_offset_hours"])
        extra = {**chat["extra"]}
        if chat["priority"] == "urgent":
            sla_due = occurred + timedelta(minutes=30)
            extra["sla_due_at"] = sla_due.isoformat()

        interaction = Interaction(
            seller_id=seller_id,
            marketplace="wb",
            channel="chat",
            external_id=chat["external_id_suffix"],
            customer_id=chat.get("customer_id"),
            order_id=chat.get("order_id"),
            nm_id=chat.get("nm_id"),
            subject=chat.get("subject"),
            text=chat["text"],
            status=chat["status"],
            priority=chat["priority"],
            needs_response=chat["needs_response"],
            source="demo",
            occurred_at=occurred,
            extra_data=extra,
        )
        db.add(interaction)
        created_count += 1

        # If the chat has a reply, create an event
        if extra.get("last_reply_text"):
            await db.flush()
            event = InteractionEvent(
                interaction_id=interaction.id,
                seller_id=seller_id,
                channel="chat",
                event_type="reply_sent",
                details={
                    "text": extra["last_reply_text"],
                    "source": "demo",
                    "is_demo": True,
                },
                created_at=occurred + timedelta(hours=2),
            )
            db.add(event)
            events_count += 1

    await db.commit()
    logger.info(
        "Demo data seeded for seller=%s: %d interactions, %d events",
        seller_id, created_count, events_count,
    )

    return {
        "created": created_count,
        "events_created": events_count,
        "message": "Demo data seeded successfully",
    }
