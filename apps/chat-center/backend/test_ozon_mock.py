#!/usr/bin/env python3
"""Mock tests for OzonConnector - тестирование без реального API"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import json

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))


# Mock responses based on Ozon API documentation
MOCK_CHAT_LIST_RESPONSE = {
    "result": {
        "chats": [
            {
                "chat_id": "chat-12345",
                "chat_type": "Buyer_Seller",
                "chat_status": "opened",
                "created_at": "2026-02-07T10:00:00Z",
                "first_message_id": "msg-001",
                "last_message_created_at": "2026-02-08T15:30:00Z",
                "unread_count": 2
            },
            {
                "chat_id": "chat-67890",
                "chat_type": "Buyer_Seller",
                "chat_status": "opened",
                "created_at": "2026-02-06T14:20:00Z",
                "first_message_id": "msg-100",
                "last_message_created_at": "2026-02-08T12:15:00Z",
                "unread_count": 0
            }
        ],
        "total": 2
    }
}

MOCK_CHAT_HISTORY_RESPONSE = {
    "result": {
        "messages": [
            {
                "id": "msg-001",
                "chat_id": "chat-12345",
                "created_at": "2026-02-07T10:00:00Z",
                "data": {
                    "text": "Когда отправите мой заказ?",
                    "attachments": []
                },
                "direction": "income",
                "user": {
                    "id": "buyer-999",
                    "type": "Customer"
                }
            },
            {
                "id": "msg-002",
                "chat_id": "chat-12345",
                "created_at": "2026-02-07T11:30:00Z",
                "data": {
                    "text": "Здравствуйте! Заказ отправлен сегодня, трек-номер 123456789.",
                    "attachments": []
                },
                "direction": "outcome",
                "user": {
                    "id": "seller-123",
                    "type": "Seller"
                }
            }
        ],
        "total": 2
    }
}

MOCK_SEND_MESSAGE_RESPONSE = {
    "result": {
        "message_id": "msg-new-123",
        "created_at": "2026-02-08T16:45:00Z"
    }
}

MOCK_UPDATES_RESPONSE = {
    "result": {
        "messages": [
            {
                "id": "msg-new-001",
                "chat_id": "chat-12345",
                "created_at": "2026-02-08T16:00:00Z",
                "data": {
                    "text": "Новое сообщение от покупателя",
                    "attachments": []
                },
                "direction": "income",
                "user": {
                    "id": "buyer-999",
                    "type": "Customer"
                }
            }
        ],
        "total": 1,
        "last_message_id": "msg-new-001"
    }
}


async def test_list_chats_mock():
    """Test 1: list_chats() с mock response"""
    print("\n" + "="*60)
    print("TEST 1: list_chats() - Mock test")
    print("="*60)

    from app.services.ozon_connector import OzonConnector

    connector = OzonConnector("test-client-id", "test-api-key")

    # Mock httpx.AsyncClient
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CHAT_LIST_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        result = await connector.list_chats(limit=10, offset=0)

        print("✅ Success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        chats = result.get("result", {}).get("chats", [])
        assert len(chats) == 2, "Expected 2 chats"
        assert chats[0]["chat_id"] == "chat-12345"
        print(f"\n✓ Найдено чатов: {len(chats)}")
        print(f"✓ Первый chat_id: {chats[0]['chat_id']}")


async def test_chat_history_mock():
    """Test 2: get_chat_history() с mock response"""
    print("\n" + "="*60)
    print("TEST 2: get_chat_history() - Mock test")
    print("="*60)

    from app.services.ozon_connector import OzonConnector

    connector = OzonConnector("test-client-id", "test-api-key")

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_CHAT_HISTORY_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        result = await connector.get_chat_history("chat-12345", limit=50)

        print("✅ Success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        messages = result.get("result", {}).get("messages", [])
        assert len(messages) == 2, "Expected 2 messages"
        assert messages[0]["direction"] == "income"
        assert messages[1]["direction"] == "outcome"
        print(f"\n✓ Найдено сообщений: {len(messages)}")
        print(f"✓ Первое сообщение: {messages[0]['data']['text'][:50]}...")


async def test_send_message_mock():
    """Test 3: send_message() с mock response"""
    print("\n" + "="*60)
    print("TEST 3: send_message() - Mock test")
    print("="*60)

    from app.services.ozon_connector import OzonConnector

    connector = OzonConnector("test-client-id", "test-api-key")

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_SEND_MESSAGE_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        result = await connector.send_message(
            chat_id="chat-12345",
            text="Тестовое сообщение"
        )

        print("✅ Success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        message_id = result.get("result", {}).get("message_id")
        assert message_id == "msg-new-123"
        print(f"\n✓ Message ID: {message_id}")


async def test_get_updates_mock():
    """Test 4: get_updates() с mock response"""
    print("\n" + "="*60)
    print("TEST 4: get_updates() - Mock test")
    print("="*60)

    from app.services.ozon_connector import OzonConnector

    connector = OzonConnector("test-client-id", "test-api-key")

    with patch('httpx.AsyncClient') as mock_client:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_UPDATES_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.request = AsyncMock(
            return_value=mock_response
        )

        result = await connector.get_updates(limit=50)

        print("✅ Success!")
        print(json.dumps(result, indent=2, ensure_ascii=False))

        messages = result.get("result", {}).get("messages", [])
        last_id = result.get("result", {}).get("last_message_id")
        assert len(messages) == 1
        assert last_id == "msg-new-001"
        print(f"\n✓ Новых сообщений: {len(messages)}")
        print(f"✓ Last message ID: {last_id}")


async def main():
    """Запуск всех mock-тестов"""
    print("\n" + "🧪 "*30)
    print("AgentIQ Chat Center - OzonConnector Mock Tests")
    print("🧪 "*30)

    print("\nℹ️  Тестируем OzonConnector с mock responses (без реального API)")

    try:
        await test_list_chats_mock()
        await test_chat_history_mock()
        await test_send_message_mock()
        await test_get_updates_mock()

        print("\n" + "="*60)
        print("✅ Все тесты пройдены успешно!")
        print("="*60)
        print("\n📝 OzonConnector работает корректно:")
        print("  ✓ list_chats() - получение списка чатов")
        print("  ✓ get_chat_history() - история сообщений")
        print("  ✓ send_message() - отправка сообщений")
        print("  ✓ get_updates() - получение новых сообщений")
        print("\n💡 Для реальных тестов используйте credentials из seller.ozon.ru")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
