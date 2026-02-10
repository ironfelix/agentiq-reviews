#!/usr/bin/env python3
"""
Быстрый тест WB Chat API.

Использование:
    python3 test_wb_chat.py YOUR_WB_TOKEN

Или через переменную окружения:
    export WB_TOKEN="your-token-here"
    python3 test_wb_chat.py
"""

import sys
import os
import requests
import json
from datetime import datetime

# Получить токен из аргумента или переменной окружения
if len(sys.argv) > 1:
    WB_TOKEN = sys.argv[1]
else:
    WB_TOKEN = os.getenv("WB_TOKEN")

if not WB_TOKEN:
    print("❌ Ошибка: укажите WB API токен")
    print("\nИспользование:")
    print("  python3 test_wb_chat.py YOUR_TOKEN")
    print("  или")
    print("  export WB_TOKEN='your-token'; python3 test_wb_chat.py")
    sys.exit(1)

BASE_URL = "https://buyer-chat-api.wildberries.ru"
HEADERS = {"Authorization": f"Bearer {WB_TOKEN}"}


def test_connection():
    """Тест 1: Проверка подключения."""
    print("\n" + "=" * 60)
    print("ТЕСТ 1: Проверка подключения к API")
    print("=" * 60)

    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/seller/chats",
            headers=HEADERS,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ Подключение успешно!")
            return True
        elif response.status_code == 401:
            print("❌ Ошибка авторизации: Неверный API token")
            return False
        else:
            print(f"❌ Ошибка: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка подключения: {e}")
        return False


def test_fetch_chats():
    """Тест 2: Получение списка чатов."""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Получение списка чатов")
    print("=" * 60)

    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/seller/chats",
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        chats = data.get("chats", [])

        print(f"✅ Получено чатов: {len(chats)}")

        if chats:
            print("\n📋 Пример первого чата:")
            chat = chats[0]
            print(f"  Chat ID:     {chat.get('chatID', 'N/A')}")
            print(f"  Client Name: {chat.get('clientName', 'N/A')}")
            print(f"  Client ID:   {chat.get('clientID', 'N/A')}")
            print(f"  Last Msg:    {chat.get('lastMessageTime', 'N/A')}")

            print("\n📄 Полный JSON:")
            print(json.dumps(chat, indent=2, ensure_ascii=False))

            # Проверить формат chatID
            chat_id = chat.get("chatID", "")
            if chat_id.startswith("1:") and len(chat_id) > 10:
                print("\n✅ Формат chatID корректный (1:UUID)")
            else:
                print(f"\n⚠️  Неожиданный формат chatID: {chat_id}")

            return chats
        else:
            print("\n⚠️  Нет активных чатов в аккаунте")
            return []

    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка: {e}")
        return None


def test_fetch_events(cursor=None):
    """Тест 3: Получение событий (сообщений)."""
    print("\n" + "=" * 60)
    print(f"ТЕСТ 3: Получение событий (сообщений)")
    if cursor:
        print(f"  Cursor: {cursor}")
    print("=" * 60)

    try:
        params = {"next": cursor} if cursor else {}

        response = requests.get(
            f"{BASE_URL}/api/v1/seller/events",
            headers=HEADERS,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", {})
        events = result.get("events", [])
        next_cursor = result.get("next")

        print(f"✅ Получено событий: {len(events)}")
        print(f"Next cursor: {next_cursor}")

        if events:
            print("\n📋 Пример первого события:")
            event = events[0]
            print(f"  Chat ID: {event.get('chatID', 'N/A')}")
            print(f"  Sender:  {event.get('sender', 'N/A')}")

            message = event.get("message", {})
            text = message.get("text", "")
            files = message.get("files", [])

            print(f"  Text:    {text[:100]}..." if len(text) > 100 else f"  Text:    {text}")
            print(f"  Files:   {len(files)} файлов")

            print("\n📄 Полный JSON:")
            print(json.dumps(event, indent=2, ensure_ascii=False))

            # Статистика по отправителям
            senders = {}
            for e in events:
                sender = e.get("sender", "unknown")
                senders[sender] = senders.get(sender, 0) + 1

            print("\n📊 Статистика:")
            for sender, count in senders.items():
                emoji = "👤" if sender == "client" else "🏪" if sender == "seller" else "❓"
                print(f"  {emoji} {sender}: {count} сообщений")
        else:
            print("\n⚠️  Нет новых событий")

        return {"events": events, "next_cursor": next_cursor}

    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка: {e}")
        return None


def test_correlation(chats, events_data):
    """Тест 4: Корреляция чатов и сообщений."""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Корреляция чатов и сообщений")
    print("=" * 60)

    if not chats or not events_data or not events_data.get("events"):
        print("⚠️  Недостаточно данных для корреляции")
        return

    events = events_data["events"]

    # Создать мапу chatID → события
    chat_events_map = {}
    for event in events:
        chat_id = event.get("chatID")
        if chat_id not in chat_events_map:
            chat_events_map[chat_id] = []
        chat_events_map[chat_id].append(event)

    print(f"Чатов с сообщениями: {len(chat_events_map)}")
    print(f"Всего чатов: {len(chats)}")

    # Найти чаты без сообщений
    chat_ids = {chat["chatID"] for chat in chats}
    chats_without_messages = chat_ids - set(chat_events_map.keys())

    if chats_without_messages:
        print(f"\n⚠️  Чаты без сообщений в events: {len(chats_without_messages)}")
        print("   (Возможно, сообщения уже были прочитаны ранее)")

    # Показать пример связанного чата
    if chat_events_map:
        example_chat_id = list(chat_events_map.keys())[0]
        example_chat = next((c for c in chats if c["chatID"] == example_chat_id), None)

        if example_chat:
            print(f"\n✅ Пример связанного чата:")
            print(f"  Chat ID:      {example_chat_id}")
            print(f"  Client Name:  {example_chat.get('clientName', 'N/A')}")
            print(f"  Last Message: {example_chat.get('lastMessageTime', 'N/A')}")
            print(f"  События:      {len(chat_events_map[example_chat_id])} сообщений")

            # Показать первое сообщение
            first_msg = chat_events_map[example_chat_id][0]
            sender = first_msg.get("sender", "unknown")
            text = first_msg.get("message", {}).get("text", "")
            print(f"\n  Первое сообщение:")
            print(f"    От: {sender}")
            print(f"    Текст: {text[:100]}..." if len(text) > 100 else f"    Текст: {text}")


def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ WB CHAT API")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Base URL:  {BASE_URL}")
    print(f"Token:     {WB_TOKEN[:10]}...{WB_TOKEN[-10:] if len(WB_TOKEN) > 20 else ''}")

    # Тест 1: Подключение
    if not test_connection():
        print("\n❌ Тестирование остановлено: не удалось подключиться к API")
        sys.exit(1)

    # Тест 2: Получение чатов
    chats = test_fetch_chats()
    if chats is None:
        print("\n❌ Не удалось получить чаты")
        sys.exit(1)

    # Тест 3: Получение событий
    events_data = test_fetch_events()
    if events_data is None:
        print("\n❌ Не удалось получить события")
        sys.exit(1)

    # Тест 4: Корреляция
    if chats and events_data:
        test_correlation(chats, events_data)

    # Финальный отчёт
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    print(f"✅ Подключение:  OK")
    print(f"✅ Чаты:         {len(chats) if chats else 0} получено")
    print(f"✅ События:      {len(events_data.get('events', [])) if events_data else 0} получено")

    if events_data and events_data.get("next_cursor"):
        print(f"\n📌 Cursor для следующего запроса:")
        print(f"   {events_data['next_cursor']}")
        print(f"\n   Использование:")
        print(f"   curl -H 'Authorization: Bearer {WB_TOKEN[:10]}...' \\")
        print(f"        '{BASE_URL}/api/v1/seller/events?next={events_data['next_cursor']}'")

    print("\n✅ Все тесты завершены!")
    print("\nСледующие шаги:")
    print("  1. Сохраните cursor для инкрементальной синхронизации")
    print("  2. Проверьте документацию: docs/chat-center/WB_CHAT_TESTING_PLAN.md")
    print("  3. Интегрируйте в backend/connectors.py")


if __name__ == "__main__":
    main()
