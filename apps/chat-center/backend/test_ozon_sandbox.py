#!/usr/bin/env python3
"""Test script for Ozon Sandbox API - проверка работы OzonConnector"""

import asyncio
import sys
import json
from pathlib import Path

# Add app to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ozon_connector import OzonConnector


# Ozon Sandbox credentials (public demo)
SANDBOX_CLIENT_ID = "836"
SANDBOX_API_KEY = "9753260e-2324-fde7-97f1-7848ed7ed097"
SANDBOX_BASE_URL = "http://cb-api.ozonru.me"


async def test_list_chats():
    """Test 1: Получить список чатов"""
    print("\n" + "="*60)
    print("TEST 1: POST /v1/chat/list - Получение списка чатов")
    print("="*60)

    connector = OzonConnector(SANDBOX_CLIENT_ID, SANDBOX_API_KEY)
    # Override base URL for sandbox
    connector.BASE_URL = SANDBOX_BASE_URL

    try:
        response = await connector.list_chats(limit=10, offset=0)
        print("✅ Success!")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        # Extract chat IDs for next test
        chats = response.get("chats", [])
        print(f"\n📊 Найдено чатов: {len(chats)}")

        if chats:
            return chats[0].get("chat_id")  # Return first chat_id for next test
        return None

    except Exception as e:
        print(f"❌ Error: {e}")
        return None


async def test_chat_history(chat_id: str):
    """Test 2: Получить историю чата"""
    print("\n" + "="*60)
    print(f"TEST 2: POST /v1/chat/history - История чата {chat_id}")
    print("="*60)

    connector = OzonConnector(SANDBOX_CLIENT_ID, SANDBOX_API_KEY)
    connector.BASE_URL = SANDBOX_BASE_URL

    try:
        response = await connector.get_chat_history(chat_id=chat_id, limit=20)
        print("✅ Success!")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        messages = response.get("messages", [])
        print(f"\n📊 Найдено сообщений: {len(messages)}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_get_updates():
    """Test 3: Получить новые сообщения (updates)"""
    print("\n" + "="*60)
    print("TEST 3: POST /v1/chat/updates - Новые сообщения")
    print("="*60)

    connector = OzonConnector(SANDBOX_CLIENT_ID, SANDBOX_API_KEY)
    connector.BASE_URL = SANDBOX_BASE_URL

    try:
        response = await connector.get_updates(limit=10)
        print("✅ Success!")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        messages = response.get("messages", [])
        print(f"\n📊 Новых сообщений: {len(messages)}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_send_message(chat_id: str):
    """Test 4: Отправить сообщение (может не работать в sandbox)"""
    print("\n" + "="*60)
    print(f"TEST 4: POST /v1/chat/send/message - Отправка в чат {chat_id}")
    print("="*60)

    connector = OzonConnector(SANDBOX_CLIENT_ID, SANDBOX_API_KEY)
    connector.BASE_URL = SANDBOX_BASE_URL

    try:
        response = await connector.send_message(
            chat_id=chat_id,
            text="Тестовое сообщение из AgentIQ Chat Center 🤖"
        )
        print("✅ Success!")
        print(json.dumps(response, indent=2, ensure_ascii=False))

        return True

    except Exception as e:
        print(f"⚠️  Note: Send message may be read-only in sandbox")
        print(f"Error: {e}")
        return False


async def main():
    """Запуск всех тестов"""
    print("\n" + "🚀 "*30)
    print("AgentIQ Chat Center - Ozon Sandbox API Tests")
    print("🚀 "*30)

    print(f"\n📍 Sandbox URL: {SANDBOX_BASE_URL}")
    print(f"🔑 Client-Id: {SANDBOX_CLIENT_ID}")
    print(f"🔑 Api-Key: {SANDBOX_API_KEY[:20]}...")

    # Test 1: List chats
    chat_id = await test_list_chats()

    if chat_id:
        # Test 2: Chat history (only if we have a chat_id)
        await test_chat_history(chat_id)

        # Test 4: Send message (may fail in sandbox)
        await test_send_message(chat_id)
    else:
        print("\n⚠️  No chats found in sandbox, skipping chat-specific tests")

    # Test 3: Get updates (doesn't require chat_id)
    await test_get_updates()

    print("\n" + "="*60)
    print("✅ Тесты завершены!")
    print("="*60)
    print("\nℹ️  Примечание: Sandbox может возвращать пустые данные.")
    print("Для реальных тестов используйте production credentials из seller.ozon.ru")


if __name__ == "__main__":
    asyncio.run(main())
