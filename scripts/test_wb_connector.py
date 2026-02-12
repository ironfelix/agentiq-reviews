#!/usr/bin/env python3
"""
Тест улучшенного WildberriesConnector с cursor pagination.

Использование:
    python3 test_wb_connector.py YOUR_WB_TOKEN
"""

import sys
import os

# Добавить путь к backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'reviews'))

from backend.connectors import WildberriesConnector


def test_connector(token: str):
    """Протестировать все методы коннектора."""
    print("=" * 60)
    print("ТЕСТ УЛУЧШЕННОГО WildberriesConnector")
    print("=" * 60)

    # Инициализация
    connector = WildberriesConnector(credentials={"api_token": token})
    print("✅ Connector инициализирован\n")

    # Тест 1: Получить первую порцию событий
    print("ТЕСТ 1: fetch_messages() - первая порция")
    print("-" * 60)
    result1 = connector.fetch_messages()
    print(f"✅ Получено сообщений: {len(result1['messages'])}")
    print(f"   Next cursor: {result1['next_cursor']}")
    print(f"   Has more: {result1['has_more']}")

    if result1['messages']:
        first_msg = result1['messages'][0]
        print(f"\n   Пример сообщения:")
        print(f"     Event ID: {first_msg.get('event_id', 'N/A')}")
        print(f"     Chat ID: {first_msg['chat_id']}")
        print(f"     От: {first_msg['author_type']}")
        print(f"     Текст: {first_msg['text'][:80]}...")
        print(f"     Время: {first_msg['created_at']}")
        print(f"     Новый чат: {first_msg.get('is_new_chat', False)}")

    cursor1 = result1['next_cursor']

    # Тест 2: Получить вторую порцию с cursor
    print("\n\nТЕСТ 2: fetch_messages() - вторая порция с cursor")
    print("-" * 60)
    result2 = connector.fetch_messages(since_cursor=cursor1)
    print(f"✅ Получено сообщений: {len(result2['messages'])}")
    print(f"   Next cursor: {result2['next_cursor']}")
    print(f"   Has more: {result2['has_more']}")

    # Проверка дедупликации
    msg_ids_1 = {msg['external_message_id'] for msg in result1['messages']}
    msg_ids_2 = {msg['external_message_id'] for msg in result2['messages']}
    duplicates = msg_ids_1 & msg_ids_2

    if duplicates:
        print(f"\n   ⚠️ Найдены дубликаты: {len(duplicates)}")
    else:
        print(f"\n   ✅ Дубликатов нет (pagination работает корректно)")

    # Тест 3: Построить список чатов из событий
    print("\n\nТЕСТ 3: fetch_messages_as_chats() - список чатов")
    print("-" * 60)
    chats_result = connector.fetch_messages_as_chats()
    print(f"✅ Получено уникальных чатов: {len(chats_result['chats'])}")
    print(f"   Всего сообщений обработано: {chats_result['total_messages']}")

    if chats_result['chats']:
        print(f"\n   Топ-3 чата:")
        for i, chat in enumerate(chats_result['chats'][:3], 1):
            print(f"   {i}. {chat['client_name'] or 'Unknown'}")
            print(f"      Chat ID: {chat['external_chat_id']}")
            print(f"      Last msg: {chat['last_message_text']}")
            print(f"      Unread: {chat['unread_count']}")
            print(f"      New: {chat.get('is_new_chat', False)}")
            print()

    # Тест 4: Статистика
    print("\nТЕСТ 4: get_statistics() - агрегация")
    print("-" * 60)
    stats = connector.get_statistics()
    print(f"✅ Статистика:")
    print(f"   Всего чатов: {stats['total_chats']}")
    print(f"   Новые чаты: {stats['new_chats']}")
    print(f"   Всего сообщений: {stats['total_messages']}")
    print(f"   От клиентов: {stats['messages_from_clients']}")
    print(f"   От продавца: {stats['messages_from_seller']}")
    print(f"   Непрочитано (оценка): {stats['unread_count']}")

    # Тест 5: Сравнение fetch_chats() vs fetch_messages_as_chats()
    print("\n\nТЕСТ 5: Сравнение /chats vs /events")
    print("-" * 60)
    chats_endpoint = connector.fetch_chats()
    print(f"   /chats endpoint: {len(chats_endpoint)} чатов")
    print(f"   /events (как чаты): {len(chats_result['chats'])} чатов")

    if len(chats_endpoint) == 0 and len(chats_result['chats']) > 0:
        print(f"\n   ⚠️ Подтверждено: /chats пустой, но события есть!")
        print(f"      Рекомендация: использовать fetch_messages_as_chats()")
    elif len(chats_endpoint) > 0:
        print(f"\n   ✅ /chats возвращает данные")

    # Финал
    print("\n" + "=" * 60)
    print("ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
    print("=" * 60)
    print(f"\nРезультаты:")
    print(f"  ✅ Первая порция: {len(result1['messages'])} сообщений")
    print(f"  ✅ Вторая порция: {len(result2['messages'])} сообщений")
    print(f"  ✅ Всего чатов: {len(chats_result['chats'])}")
    print(f"  ✅ Cursor pagination: {'OK' if not duplicates else 'FAIL'}")
    print(f"\nNext cursor для продолжения: {result2['next_cursor']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 test_wb_connector.py YOUR_WB_TOKEN")
        sys.exit(1)

    token = sys.argv[1]
    test_connector(token)
