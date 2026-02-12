"""Seed database with demo data for testing"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
from app.models.seller import Seller
from app.models.chat import Chat
from app.models.message import Message
from app.database import Base

settings = get_settings()


async def seed_data():
    """Seed demo data into database"""

    # Create engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Create demo seller
        seller = Seller(
            name="Demo Seller",
            marketplace="wildberries",
            client_id="demo_client_123",
            api_key_encrypted=b"demo_encrypted_key",  # In real app, this would be properly encrypted
            is_active=True
        )
        session.add(seller)
        await session.flush()

        print(f"✅ Created seller: {seller.name} (ID: {seller.id})")

        # Create demo chats
        now = datetime.now(timezone.utc)

        chats_data = [
            {
                "marketplace_chat_id": "wb_chat_001",
                "customer_name": "Иван Петров",
                "order_id": "WB-12345678",
                "product_id": "145123456",
                "status": "open",
                "unread_count": 2,
                "sla_priority": "urgent",
                "sla_deadline_at": now + timedelta(hours=1),
                "last_message_at": now - timedelta(minutes=15),
                "first_message_at": now - timedelta(hours=2),
            },
            {
                "marketplace_chat_id": "wb_chat_002",
                "customer_name": "Мария Сидорова",
                "order_id": "WB-87654321",
                "product_id": "145987654",
                "status": "open",
                "unread_count": 1,
                "sla_priority": "high",
                "sla_deadline_at": now + timedelta(hours=4),
                "last_message_at": now - timedelta(hours=1),
                "first_message_at": now - timedelta(hours=3),
            },
            {
                "marketplace_chat_id": "wb_chat_003",
                "customer_name": "Алексей Иванов",
                "order_id": "WB-11223344",
                "product_id": "145112233",
                "status": "open",
                "unread_count": 0,
                "sla_priority": "normal",
                "sla_deadline_at": now + timedelta(hours=24),
                "last_message_at": now - timedelta(hours=5),
                "first_message_at": now - timedelta(days=1),
            },
            {
                "marketplace_chat_id": "wb_chat_004",
                "customer_name": "Елена Смирнова",
                "order_id": "WB-99887766",
                "product_id": "145998877",
                "status": "open",
                "unread_count": 3,
                "sla_priority": "high",
                "sla_deadline_at": now + timedelta(hours=2),
                "last_message_at": now - timedelta(minutes=30),
                "first_message_at": now - timedelta(hours=4),
            },
            {
                "marketplace_chat_id": "wb_chat_005",
                "customer_name": "Дмитрий Кузнецов",
                "order_id": "WB-55443322",
                "product_id": "145554433",
                "status": "closed",
                "unread_count": 0,
                "sla_priority": "low",
                "sla_deadline_at": None,
                "last_message_at": now - timedelta(days=2),
                "first_message_at": now - timedelta(days=3),
            },
        ]

        chats = []
        for chat_data in chats_data:
            chat = Chat(
                seller_id=seller.id,
                marketplace="wildberries",
                **chat_data
            )
            session.add(chat)
            chats.append(chat)

        await session.flush()
        print(f"✅ Created {len(chats)} demo chats")

        # Create demo messages for each chat
        messages_data = [
            # Chat 1 - Urgent (брак/не работает)
            [
                {"direction": "incoming", "author": "Иван Петров", "text": "Здравствуйте! Получил фонарик, но он не включается. Зарядил полностью, но ничего не происходит.", "sent_at": now - timedelta(hours=2)},
                {"direction": "outgoing", "author": None, "text": "Иван, здравствуйте! Нам очень жаль — это нештатная ситуация. Оформите, пожалуйста, возврат через ЛК WB. Мы передали информацию в отдел качества для проверки партии.", "sent_at": now - timedelta(hours=1, minutes=45)},
                {"direction": "incoming", "author": "Иван Петров", "text": "Хорошо, спасибо. А как долго возврат денег?", "sent_at": now - timedelta(minutes=15)},
            ],
            # Chat 2 - High (задержка доставки)
            [
                {"direction": "incoming", "author": "Мария Сидорова", "text": "Где мой заказ? Жду уже неделю!", "sent_at": now - timedelta(hours=3)},
                {"direction": "outgoing", "author": None, "text": "Мария, здравствуйте! Понимаем — ожидание затянулось. Со своей стороны проверили: товар был передан в доставку 5 февраля. К сожалению, на сроки логистики мы повлиять не можем, но если заказ не поступит в ближайшие дни — напишите нам, поможем разобраться.", "sent_at": now - timedelta(hours=1)},
            ],
            # Chat 3 - Normal (вопрос по использованию)
            [
                {"direction": "incoming", "author": "Алексей Иванов", "text": "Подскажите, как подключить фонарик к зарядке? Какой кабель нужен?", "sent_at": now - timedelta(days=1)},
                {"direction": "outgoing", "author": None, "text": "Алексей, здравствуйте! Фонарик заряжается через USB Type-C кабель (в комплекте). Подключите к любому USB зарядному устройству или компьютеру. Индикатор зарядки расположен на кнопке и светится красным во время зарядки, зелёным — когда полностью заряжен.", "sent_at": now - timedelta(hours=5)},
                {"direction": "incoming", "author": "Алексей Иванов", "text": "Спасибо, разобрался!", "sent_at": now - timedelta(hours=4, minutes=50)},
            ],
            # Chat 4 - High (прислали не тот товар)
            [
                {"direction": "incoming", "author": "Елена Смирнова", "text": "Заказывала фонарик чёрный, а прислали синий!", "sent_at": now - timedelta(hours=4)},
                {"direction": "outgoing", "author": None, "text": "Елена, здравствуйте! Приносим извинения — такого не должно быть. Оформите, пожалуйста, возврат через ЛК WB с пометкой \"не соответствует описанию\" — это бесплатно. Мы передали информацию для проверки комплектации.", "sent_at": now - timedelta(hours=3, minutes=30)},
                {"direction": "incoming", "author": "Елена Смирнова", "text": "Хорошо, оформила возврат. Можно заказать снова чёрный?", "sent_at": now - timedelta(hours=1)},
                {"direction": "incoming", "author": "Елена Смирнова", "text": "Или у вас нет в наличии?", "sent_at": now - timedelta(minutes=30)},
            ],
            # Chat 5 - Closed (вопрос решён)
            [
                {"direction": "incoming", "author": "Дмитрий Кузнецов", "text": "Когда придёт заказ?", "sent_at": now - timedelta(days=3)},
                {"direction": "outgoing", "author": None, "text": "Дмитрий, здравствуйте! Проверили ваш заказ — со своей стороны товар отгружен и передан в службу доставки WB. Отслеживать статус удобнее всего в ЛК WB. Если возникнут вопросы — пишите!", "sent_at": now - timedelta(days=2, hours=20)},
                {"direction": "incoming", "author": "Дмитрий Кузнецов", "text": "Получил, спасибо!", "sent_at": now - timedelta(days=2)},
            ],
        ]

        total_messages = 0
        for chat, messages in zip(chats, messages_data):
            for msg_data in messages:
                message = Message(
                    chat_id=chat.id,
                    **msg_data
                )
                session.add(message)
                total_messages += 1

        await session.commit()
        print(f"✅ Created {total_messages} demo messages")

        print("\n🎉 Demo data seeded successfully!")
        print(f"\n📊 Summary:")
        print(f"   - Sellers: 1")
        print(f"   - Chats: {len(chats)}")
        print(f"   - Messages: {total_messages}")
        print(f"\n🚀 Start the backend:")
        print(f"   cd backend && uvicorn app.main:app --reload --port 8001")
        print(f"\n🌐 Start the frontend:")
        print(f"   cd frontend && npm run dev")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_data())
