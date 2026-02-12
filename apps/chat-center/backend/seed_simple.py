"""Seed script with real WB Chat API data from prototype"""
import asyncio, os, json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./chat_center_demo.db")


async def main():
    print(f"DB: {DATABASE_URL}")
    engine = create_async_engine(DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS messages"))
        await conn.execute(text("DROP TABLE IF EXISTS chats"))
        await conn.execute(text("DROP TABLE IF EXISTS sellers"))

        await conn.execute(text("""CREATE TABLE sellers (
            id INTEGER PRIMARY KEY, name VARCHAR(255), marketplace VARCHAR(50),
            client_id VARCHAR(255), api_key_encrypted TEXT, is_active BOOLEAN DEFAULT TRUE,
            last_sync_at TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))

        await conn.execute(text("""CREATE TABLE chats (
            id INTEGER PRIMARY KEY, seller_id INTEGER, marketplace VARCHAR(50),
            marketplace_chat_id VARCHAR(255), order_id VARCHAR(100), product_id VARCHAR(100),
            customer_name VARCHAR(255), customer_id VARCHAR(100),
            status VARCHAR(50) DEFAULT 'open',
            unread_count INTEGER DEFAULT 0,
            last_message_at TIMESTAMP, first_message_at TIMESTAMP,
            sla_deadline_at TIMESTAMP, sla_priority VARCHAR(20) DEFAULT 'normal',
            metadata TEXT,
            ai_suggestion_text TEXT,
            ai_analysis_json TEXT,
            last_message_preview TEXT,
            product_name VARCHAR(255),
            product_article VARCHAR(100),
            chat_status VARCHAR(50) DEFAULT 'waiting',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))

        await conn.execute(text("""CREATE TABLE messages (
            id INTEGER PRIMARY KEY, chat_id INTEGER,
            external_message_id VARCHAR(255) DEFAULT '',
            direction VARCHAR(20), text TEXT,
            attachments TEXT,
            author_type VARCHAR(20), author_id VARCHAR(100),
            status VARCHAR(20) DEFAULT 'sent',
            is_read BOOLEAN DEFAULT FALSE, read_at TIMESTAMP,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""))
        print("Tables created")

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        now = datetime.now(timezone.utc)

        await session.execute(text(
            "INSERT INTO sellers (id, name, marketplace, client_id) VALUES (1, 'Zegor Official', 'wildberries', 'zegor_wb_001')"
        ))

        # Real chat data from WB Chat API prototype
        chats_data = [
            {
                "id": 1, "name": "Алексей", "chat_id": "1:8354eff6-3771-83ce-7ed5-87cf3d94d0cb",
                "status": "open", "unread": 1, "priority": "urgent", "chat_status": "waiting",
                "product_name": "Кран", "product_article": None,
                "ai_suggestion": "Добрый вечер, Алексей. Приносим извинения за задержку доставки, это действительно неприятная ситуация. Для отмены заказа, пожалуйста, воспользуйтесь функцией в вашем личном кабинете Wildberries — это самый быстрый способ решения вопроса.",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Отмена заказа", "Доставка"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Признать проблему с доставкой, извиниться и проинформировать о процедуре отмены через ЛК WB."},
                "preview": "Доброго вечера, так как заказ задерживается уже на три дня...",
                "messages": [
                    {"type": "customer", "author": "Алексей", "time": "2025-09-24T17:50:00", "text": "Доброго вечера , так как заказ задерживается уже на три дня и продолжает задерживаться ч вынужден отказаться от вашего краника, не один нормальный человек не будет ждать больше недели задержки заказанного товара, ч уже давно купил в магазине и установил краник, так что разбирайтесь с валберис , вы теряете деньги из за доставки валберис"}
                ]
            },
            {
                "id": 2, "name": "Исакович Анна Витальевна", "chat_id": "1:2eef0aa2-b9a3-ac5a-7ff5-e6d32a0d7766",
                "status": "open", "unread": 2, "priority": "urgent", "chat_status": "waiting",
                "product_name": "Кран", "product_article": None,
                "ai_suggestion": "Добрый день, Анна Витальевна! Приносим извинения, что прислали не тот товар. Для возврата, пожалуйста, оформите заявку в личном кабинете Wildberries, указав причину «Прислали другой товар».",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Прислали не тот товар"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Признать проблему, извиниться и проинформировать о процедуре возврата через ЛК WB."},
                "preview": "Заказывала 2 крана",
                "messages": [
                    {"type": "customer", "author": "Исакович Анна Витальевна", "time": "2025-07-10T07:23:00", "text": "Добрый день,получила заказ оказались не те краны.Выписывала угловные,а пришли прямые большего размера.Как поменять.Все оплачено."},
                    {"type": "customer", "author": "Исакович Анна Витальевна", "time": "2025-07-10T07:25:00", "text": "Заказывала 2 крана"}
                ]
            },
            {
                "id": 3, "name": "Сергей", "chat_id": "1:58f218a2-27b9-ea32-2007-cfbbca7d7a7e",
                "status": "open", "unread": 1, "priority": "urgent", "chat_status": "waiting",
                "product_name": "Реле", "product_article": None,
                "ai_suggestion": "Добрый день, Сергей. Приносим извинения за доставленные неудобства. Для оформления возврата товара с дефектом, пожалуйста, воспользуйтесь функцией «Возврат» в вашем личном кабинете на Wildberries, указав причину «Брак».",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Брак / дефект", "Возврат"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Признать проблему, выразить сожаление и проинформировать о процедуре возврата через ЛК WB."},
                "preview": "хочу вернуть реле, потому что пришло сломаное",
                "messages": [
                    {"type": "customer", "author": "Сергей", "time": "2025-05-02T15:04:00", "text": "хочу вернуть реле, потому что пришло сломаное"}
                ]
            },
            {
                "id": 4, "name": "Олег", "chat_id": "1:d608796d-3dc5-3c7d-3b28-d07c2bde2d9f",
                "status": "open", "unread": 6, "priority": "urgent", "chat_status": "waiting",
                "product_name": None, "product_article": None,
                "ai_suggestion": "Здравствуйте, Олег! Приносим извинения за несоответствие товара. Для возврата, пожалуйста, оформите его в личном кабинете Wildberries, выбрав причину «Прислали другой товар».",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Прислали не тот товар", "Возврат"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Признать проблему с несоответствием товара и проинструктировать по возврату через ЛК WB."},
                "preview": "Артикул на упаковке другой?",
                "messages": [
                    {"type": "customer", "author": "Олег", "time": "2025-03-19T17:19:00", "text": "Здравствуйте! Хочу вернуть товар. Как это сделать?"},
                    {"type": "customer", "author": "Олег", "time": "2025-03-19T17:19:30", "text": "Как так получилось?"},
                    {"type": "customer", "author": "Олег", "time": "2025-03-19T17:20:00", "text": "Артикул на штрихкоде один"},
                    {"type": "customer", "author": "Олег", "time": "2025-03-19T17:20:30", "text": "Артикул на упаковке другой?"},
                    {"type": "customer", "author": "Олег", "time": "2025-03-19T17:21:00", "text": "Заказан с верхним забором привезли с нижним"}
                ]
            },
            {
                "id": 5, "name": "Курченко", "chat_id": "1:2afade85-5391-5123-f7e7-eb6fb3b22251",
                "status": "open", "unread": 1, "priority": "high", "chat_status": "waiting",
                "product_name": "Кран шаровой ВР/ВР 1/2", "product_article": "335542810",
                "ai_suggestion": "Здравствуйте! Статус вашего заказа проверен, он передан в службу доставки Wildberries. Точные сроки зависят от логистики маркетплейса. Вы можете отслеживать статус в личном кабинете.",
                "ai_analysis": {"sentiment": {"label": "Нейтральная", "negative": False}, "categories": ["Доставка", "Вопрос о товаре"], "urgency": {"label": "Средняя", "urgent": False}, "recommendation": "Ответить клиенту, проверив статус заказа. Не давать гарантий по срокам."},
                "preview": "Мне ждать заказ и сколько? Может перезаказать?",
                "messages": [
                    {"type": "customer", "author": "Курченко", "time": "2025-12-22T04:33:00", "text": "Здравствуйте! У меня вопрос по товару \"Кран шаровой ВР/ВР 1/2\" бабочка, артикул 335542810. Мне ждать заказ и сколько? Может перезаказать?"}
                ]
            },
            {
                "id": 6, "name": "Сергей", "chat_id": "1:7da54043-2358-9346-02ac-31b632a89243",
                "status": "open", "unread": 2, "priority": "normal", "chat_status": "waiting",
                "product_name": None, "product_article": None,
                "ai_suggestion": "Здравствуйте! Для уточнения информации по заказу, пожалуйста, сообщите номер заказа или артикул товара. Если заказ был оформлен по ошибке, его можно отменить в личном кабинете Wildberries.",
                "ai_analysis": {"sentiment": {"label": "Нейтральная", "negative": False}, "categories": ["Ошибочный заказ"], "urgency": {"label": "Средняя", "urgent": False}, "recommendation": "Уточнить детали заказа и объяснить, что отмена возможна через ЛК WB."},
                "preview": "Не заказывал",
                "messages": [
                    {"type": "customer", "author": "Сергей", "time": "2025-11-06T13:31:00", "text": "Не заказывал"},
                    {"type": "customer", "author": "Сергей", "time": "2025-11-06T13:33:00", "text": "Не заказывал"}
                ]
            },
            {
                "id": 7, "name": "Клиент", "chat_id": "1:b729b9a3-3b21-8b5a-082f-93d4a6ed9fcf",
                "status": "open", "unread": 1, "priority": "normal", "chat_status": "waiting",
                "product_name": None, "product_article": None,
                "ai_suggestion": "Здравствуйте! Информация о движении посылки обновляется в личном кабинете Wildberries. Там вы можете отслеживать актуальное местоположение товара.",
                "ai_analysis": {"sentiment": {"label": "Нейтральная", "negative": False}, "categories": ["Доставка"], "urgency": {"label": "Средняя", "urgent": False}, "recommendation": "Проверить статус заказа и проинформировать клиента."},
                "preview": "Где товар",
                "messages": [
                    {"type": "customer", "author": "Клиент", "time": "2025-09-14T10:48:00", "text": "Где товар"}
                ]
            },
            {
                "id": 8, "name": "Елена", "chat_id": "1:49f57983-d801-c46e-83db-0d019cf5e80a",
                "status": "open", "unread": 3, "priority": "high", "chat_status": "waiting",
                "product_name": "Гофра для унитаза 350 мм", "product_article": "233586811",
                "ai_suggestion": "Здравствуйте, Елена! Приносим извинения за задержку. Мы проверили информацию по вашему заказу: он был отгружен на склад Wildberries. Для уточнения сроков обратитесь в поддержку WB через раздел «Помощь» в личном кабинете.",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Доставка"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Немедленно ответить, признать задержку и предложить действия через поддержку WB."},
                "preview": "Слушайте! Имейте совесть! Где товар???",
                "messages": [
                    {"type": "customer", "author": "Елена", "time": "2025-04-27T09:18:00", "text": "Здравствуйте! У меня вопрос по товару \"Гофра для унитаза 350 мм\", должен прийти 27.04.25, но с 24 апреля стоит в одном статусе. Разберитесь, пожалуйста."},
                    {"type": "customer", "author": "Елена", "time": "2025-04-28T07:17:00", "text": "Здравствуйте! Где товар??? Очень нужен!!!"},
                    {"type": "customer", "author": "Елена", "time": "2025-04-29T02:57:00", "text": "Слушайте! Имейте совесть! Где товар???"}
                ]
            },
            {
                "id": 9, "name": "Игорь", "chat_id": "1:27b53dc2-fe3d-ff56-3cab-55564d5785da",
                "status": "open", "unread": 1, "priority": "high", "chat_status": "client-replied",
                "product_name": "Кран шаровой ВР/НР/НР 1/2", "product_article": "331463403",
                "ai_suggestion": "Чат обработан. Мониторинг.",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Доставка"], "urgency": {"label": "Высокая", "urgent": True}, "recommendation": "Клиент получил товар и поблагодарил. Дополнительных действий не требуется."},
                "preview": "Вчера кран доставили. Спасибо за участие.",
                "messages": [
                    {"type": "customer", "author": "Игорь", "time": "2025-04-17T18:54:00", "text": "Здравствуйте! У меня вопрос по товару \"Кран шаровой\", артикул 331463403"},
                    {"type": "customer", "author": "Игорь", "time": "2025-04-17T18:55:00", "text": "Прошу сообщить, когда привезут кран."},
                    {"type": "customer", "author": "Игорь", "time": "2025-04-18T09:26:00", "text": "К сожалению продавец молчит. Кран нужен вчера. Жду ответа."},
                    {"type": "seller", "author": "Продавец", "time": "2025-04-20T18:36:00", "text": "Здравствуйте, к сожалению не имеем возможности влиять на доставку. Мы отгружаем товар, а далее доставку регламентирует маркетплейс."},
                    {"type": "customer", "author": "Игорь", "time": "2025-04-21T09:18:00", "text": "Вчера кран доставили. Спасибо за участие."}
                ]
            },
            {
                "id": 10, "name": "Николай", "chat_id": "1:18e437c4-4117-fadc-a7f5-55dd2f62aca3",
                "status": "open", "unread": 0, "priority": "low", "chat_status": "responded",
                "product_name": None, "product_article": None,
                "ai_suggestion": "Чат обработан. Мониторинг.",
                "ai_analysis": {"sentiment": {"label": "Нейтральная", "negative": False}, "categories": ["Не подошёл товар", "Возврат"], "urgency": {"label": "Низкая", "urgent": False}, "recommendation": "Чат обработан. Продавец корректно проинструктировал клиента."},
                "preview": "Вы: Добрый день, оформите заявку на возврат, мы одобрим.",
                "messages": [
                    {"type": "customer", "author": "Николай", "time": "2025-11-01T04:53:00", "text": "Здравствуйту, товар исправен но не подошел, решил заказать весь комплект в сборе."},
                    {"type": "seller", "author": "Продавец", "time": "2025-11-01T07:16:00", "text": "Добрый день, оформите заявку на возврат, мы одобрим. Нужно чтобы упаковка была целая и товар не был в использовании."}
                ]
            },
            {
                "id": 11, "name": "Дмитрий", "chat_id": "1:f3d22b0a-1234-5678-9abc-def012345678",
                "status": "open", "unread": 0, "priority": "normal", "chat_status": "responded",
                "product_name": None, "product_article": None,
                "ai_suggestion": "Чат обработан. Мониторинг.",
                "ai_analysis": {"sentiment": {"label": "Негативная", "negative": True}, "categories": ["Доставка"], "urgency": {"label": "Средняя", "urgent": False}, "recommendation": "Продавец уже ответил. Дополнительных действий не требуется."},
                "preview": "Вы: Приносим свои извинения за задержку с отправкой.",
                "messages": [
                    {"type": "customer", "author": "Дмитрий", "time": "2025-10-12T19:33:00", "text": "Здравствуйте. Почему не отправляете заказ?"},
                    {"type": "seller", "author": "Продавец", "time": "2025-10-14T10:15:00", "text": "Дмитрий, здравствуйте. Приносим свои извинения за задержку с отправкой. Заказ отгружен и передан в службу доставки Wildberries."}
                ]
            },
            {
                "id": 12, "name": "Юлия", "chat_id": "1:62d1f2c5-4e75-d34c-1d76-75a18da7edd8",
                "status": "open", "unread": 2, "priority": "normal", "chat_status": "waiting",
                "product_name": "Шланг", "product_article": None,
                "ai_suggestion": "Здравствуйте! Для нового заказа выберите в нашем магазине шланг нужной вам длины и оформите его как обычный заказ. Характеристики указаны в карточке товара.",
                "ai_analysis": {"sentiment": {"label": "Нейтральная", "negative": False}, "categories": ["Вопрос о товаре", "Не подошёл товар"], "urgency": {"label": "Низкая", "urgent": False}, "recommendation": "Ответить на вопрос клиента, объяснив, как выбрать товар нужной длины."},
                "preview": "мы из Рязани",
                "messages": [
                    {"type": "customer", "author": "Юлия", "time": "2025-04-27T08:44:00", "text": "здравствуйте, купили у вас 9 шлангов, а оказалось не хватает длины, хотим перезаказать побольше. как лучше это сделать?"},
                    {"type": "customer", "author": "Юлия", "time": "2025-04-27T08:58:00", "text": "мы из Рязани"}
                ]
            },
        ]

        # Insert chats
        for c in chats_data:
            first_msg_time = c["messages"][0]["time"]
            last_msg_time = c["messages"][-1]["time"]
            await session.execute(text("""INSERT INTO chats (
                id, seller_id, marketplace, marketplace_chat_id, order_id, product_id,
                customer_name, customer_id, status, unread_count,
                last_message_at, first_message_at, sla_deadline_at, sla_priority,
                metadata, ai_suggestion_text, ai_analysis_json,
                last_message_preview, product_name, product_article, chat_status,
                created_at, updated_at
            ) VALUES (
                :id, 1, 'wildberries', :chat_id, NULL, :product_article,
                :name, NULL, :status, :unread,
                :last_msg, :first_msg, NULL, :priority,
                NULL, :ai_suggestion, :ai_analysis,
                :preview, :product_name, :product_article2, :chat_status,
                :now, :now
            )"""), {
                "id": c["id"], "chat_id": c["chat_id"], "name": c["name"],
                "status": c["status"], "unread": c["unread"], "priority": c["priority"],
                "last_msg": last_msg_time, "first_msg": first_msg_time,
                "ai_suggestion": c["ai_suggestion"],
                "ai_analysis": json.dumps(c["ai_analysis"], ensure_ascii=False),
                "preview": c["preview"],
                "product_name": c.get("product_name"),
                "product_article": c.get("product_article"),
                "product_article2": c.get("product_article"),
                "chat_status": c["chat_status"],
                "now": now
            })

        # Insert messages
        msg_id = 1
        for c in chats_data:
            for m in c["messages"]:
                direction = "incoming" if m["type"] == "customer" else "outgoing"
                author_type = "customer" if m["type"] == "customer" else "seller"
                await session.execute(text("""INSERT INTO messages (
                    id, chat_id, external_message_id, direction, text,
                    author_type, author_id, status, is_read, sent_at, created_at
                ) VALUES (
                    :id, :chat_id, :ext_id, :direction, :text,
                    :author_type, NULL, 'sent', :is_read, :sent_at, :now
                )"""), {
                    "id": msg_id, "chat_id": c["id"],
                    "ext_id": f"msg_{msg_id}",
                    "direction": direction, "text": m["text"],
                    "author_type": author_type,
                    "is_read": direction == "outgoing",
                    "sent_at": m["time"], "now": now
                })
                msg_id += 1

        await session.commit()

    await engine.dispose()
    total_msgs = sum(len(c["messages"]) for c in chats_data)
    print(f"Seeded 1 seller, {len(chats_data)} chats, {total_msgs} messages")
    print("Start: uvicorn app.main:app --reload --port 8001")

asyncio.run(main())
