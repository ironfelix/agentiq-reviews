#!/usr/bin/env python3
"""Standalone test for Ozon Sandbox API - без зависимостей"""

import asyncio
import json
import sys

try:
    import httpx
except ImportError:
    print("❌ Установите httpx: pip install httpx")
    sys.exit(1)


# Ozon Sandbox credentials (public demo)
SANDBOX_CLIENT_ID = "836"
SANDBOX_API_KEY = "9753260e-2324-fde7-97f1-7848ed7ed097"
SANDBOX_BASE_URL = "http://cb-api.ozonru.me"


async def test_list_chats():
    """Test 1: Получить список чатов"""
    print("\n" + "="*60)
    print("TEST 1: POST /v1/chat/list - Получение списка чатов")
    print("="*60)

    url = f"{SANDBOX_BASE_URL}/v1/chat/list"
    headers = {
        "Client-Id": SANDBOX_CLIENT_ID,
        "Api-Key": SANDBOX_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "limit": 10,
        "offset": 0
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                chats = data.get("result", {}).get("chats", [])
                print(f"\n📊 Найдено чатов: {len(chats)}")

                if chats:
                    return chats[0].get("chat_id")
                return None
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                return None

        except Exception as e:
            print(f"❌ Exception: {e}")
            return None


async def test_chat_history(chat_id: str):
    """Test 2: Получить историю чата"""
    print("\n" + "="*60)
    print(f"TEST 2: POST /v1/chat/history - История чата {chat_id}")
    print("="*60)

    url = f"{SANDBOX_BASE_URL}/v1/chat/history"
    headers = {
        "Client-Id": SANDBOX_CLIENT_ID,
        "Api-Key": SANDBOX_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "chat_id": chat_id,
        "limit": 20
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                messages = data.get("result", {}).get("messages", [])
                print(f"\n📊 Найдено сообщений: {len(messages)}")
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"❌ Exception: {e}")
            return False


async def test_get_updates():
    """Test 3: Получить новые сообщения"""
    print("\n" + "="*60)
    print("TEST 3: POST /v1/chat/updates - Новые сообщения")
    print("="*60)

    url = f"{SANDBOX_BASE_URL}/v1/chat/updates"
    headers = {
        "Client-Id": SANDBOX_CLIENT_ID,
        "Api-Key": SANDBOX_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "limit": 10
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(json.dumps(data, indent=2, ensure_ascii=False))

                messages = data.get("result", {}).get("messages", [])
                print(f"\n📊 Новых сообщений: {len(messages)}")
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"❌ Exception: {e}")
            return False


async def test_send_message(chat_id: str):
    """Test 4: Отправить сообщение"""
    print("\n" + "="*60)
    print(f"TEST 4: POST /v1/chat/send/message - Отправка в {chat_id}")
    print("="*60)

    url = f"{SANDBOX_BASE_URL}/v1/chat/send/message"
    headers = {
        "Client-Id": SANDBOX_CLIENT_ID,
        "Api-Key": SANDBOX_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "chat_id": chat_id,
        "text": "Тестовое сообщение из AgentIQ Chat Center 🤖"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            print(f"Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                return True
            else:
                print(f"⚠️  Note: Send may be read-only in sandbox")
                print(f"Status: {response.status_code}")
                print(response.text)
                return False

        except Exception as e:
            print(f"⚠️  Exception: {e}")
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
        # Test 2: Chat history
        await test_chat_history(chat_id)

        # Test 4: Send message
        await test_send_message(chat_id)
    else:
        print("\n⚠️  No chats found in sandbox")

    # Test 3: Get updates
    await test_get_updates()

    print("\n" + "="*60)
    print("✅ Тесты завершены!")
    print("="*60)
    print("\nℹ️  Sandbox может возвращать пустые/тестовые данные.")
    print("Для реальных тестов используйте credentials из seller.ozon.ru")


if __name__ == "__main__":
    asyncio.run(main())
