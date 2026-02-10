"""
Connectors для маркетплейсов (WB, Ozon, Яндекс Маркет).

Этот модуль содержит классы для интеграции с Chat API различных платформ.
"""

import requests
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict


class WildberriesConnector:
    """
    Connector для WB Chat API.

    Основан на реальных результатах тестирования (2026-02-09).

    Особенности:
    - Events API возвращает больше данных, чем описано в документации
    - /chats может быть пустым, даже если есть события
    - Timestamp присутствует (addTimestamp + addTime)
    - eventID можно использовать как уникальный идентификатор
    """

    BASE_URL = "https://buyer-chat-api.wildberries.ru"

    def __init__(self, credentials: Dict[str, str]):
        """
        Args:
            credentials: {"api_token": "your-token"}
        """
        self.token = credentials.get("api_token")
        if not self.token:
            raise ValueError("api_token is required in credentials")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def fetch_chats(self, since: Optional[datetime] = None) -> List[Dict]:
        """
        Получить список чатов.

        ВАЖНО: Endpoint /chats может возвращать пустой список,
        даже если есть активные чаты. Используйте fetch_messages_as_chats()
        для надежного построения списка чатов.

        Args:
            since: Фильтр по дате (опционально)

        Returns:
            List[Dict]: Список чатов
        """
        response = requests.get(
            f"{self.BASE_URL}/api/v1/seller/chats",
            headers=self.headers,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        chats = []

        for chat in data.get("chats", []):
            last_message_at = datetime.fromisoformat(
                chat["lastMessageTime"].replace("Z", "+00:00")
            )

            # Фильтрация на стороне клиента
            if since and last_message_at < since:
                continue

            chats.append({
                "external_chat_id": chat["chatID"],
                "client_name": chat.get("clientName", ""),
                "client_id": chat.get("clientID", ""),
                "status": "open",
                "unread_count": 0,  # WB не возвращает
                "last_message_at": last_message_at
            })

        return chats

    def fetch_messages(
        self,
        chat_id: Optional[str] = None,
        since_cursor: Optional[int] = None,
        limit: int = 50
    ) -> Dict:
        """
        Получить новые события (сообщения) с cursor pagination.

        Структура реального response (протестировано 2026-02-09):
        {
          "chatID": "1:UUID",
          "eventID": "UUID",              ← уникальный ID события
          "eventType": "message",
          "isNewChat": true,              ← флаг нового чата
          "addTimestamp": 1742404763767,  ← UNIX ms
          "addTime": "2025-03-19T17:19:23Z",
          "sender": "client" | "seller",
          "clientID": "",                 ← часто пустой
          "clientName": "Имя",
          "message": {
            "text": "...",
            "files": [{"fileName": "...", "downloadID": "..."}]
          }
        }

        Args:
            chat_id: Фильтр по конкретному чату (опционально)
            since_cursor: Cursor из предыдущего запроса
            limit: Лимит событий (не используется WB, всегда ~50)

        Returns:
            {
                "messages": List[Dict],
                "next_cursor": int,
                "has_more": bool
            }
        """
        params = {"next": since_cursor} if since_cursor else {}

        response = requests.get(
            f"{self.BASE_URL}/api/v1/seller/events",
            headers=self.headers,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", {})
        events = result.get("events", [])
        next_cursor = result.get("next")

        messages = []
        for event in events:
            # Фильтрация по chat_id (если указан)
            if chat_id and event.get("chatID") != chat_id:
                continue

            # Использовать eventID как уникальный идентификатор
            message_id = event.get("eventID", f"{event['chatID']}-{next_cursor}")

            # Timestamp из реального API (не из документации!)
            created_at = datetime.utcnow()
            if event.get("addTimestamp"):
                created_at = datetime.fromtimestamp(event["addTimestamp"] / 1000)
            elif event.get("addTime"):
                created_at = datetime.fromisoformat(event["addTime"].replace("Z", "+00:00"))

            messages.append({
                "external_message_id": message_id,
                "event_id": event.get("eventID", ""),
                "chat_id": event["chatID"],
                "author_type": "buyer" if event["sender"] == "client" else "seller",
                "text": event.get("message", {}).get("text", ""),
                "attachments": [
                    {
                        "type": "file",
                        "file_name": f.get("fileName", ""),
                        "download_id": f.get("downloadID", "")
                    }
                    for f in event.get("message", {}).get("files", [])
                ],
                "created_at": created_at,
                "is_new_chat": event.get("isNewChat", False),
                "event_type": event.get("eventType", "message"),
                "client_name": event.get("clientName", ""),
                "client_id": event.get("clientID", "")
            })

        return {
            "messages": messages,
            "next_cursor": next_cursor,
            "has_more": len(events) > 0  # Если есть события, возможно есть еще
        }

    def fetch_messages_as_chats(
        self,
        since_cursor: Optional[int] = None
    ) -> Dict:
        """
        Получить список чатов, построенный из событий.

        Более надежный метод, чем fetch_chats(), т.к. /chats может быть пустым.

        Returns:
            {
                "chats": List[Dict],  # Список уникальных чатов с последними сообщениями
                "next_cursor": int,
                "total_messages": int
            }
        """
        result = self.fetch_messages(since_cursor=since_cursor)
        messages = result["messages"]

        # Группировка по chatID
        chats_map = {}
        for msg in messages:
            chat_id = msg["chat_id"]

            if chat_id not in chats_map:
                chats_map[chat_id] = {
                    "external_chat_id": chat_id,
                    "client_name": msg.get("client_name", ""),
                    "client_id": msg.get("client_id", ""),
                    "status": "open",
                    "last_message_at": msg["created_at"],
                    "last_message_text": msg["text"][:100],
                    "unread_count": 0,  # Вычислять локально
                    "is_new_chat": msg.get("is_new_chat", False)
                }
            else:
                # Обновить последнее сообщение (если новее)
                if msg["created_at"] > chats_map[chat_id]["last_message_at"]:
                    chats_map[chat_id]["last_message_at"] = msg["created_at"]
                    chats_map[chat_id]["last_message_text"] = msg["text"][:100]

            # Подсчет непрочитанных (от buyer)
            if msg["author_type"] == "buyer":
                chats_map[chat_id]["unread_count"] += 1

        chats = sorted(
            chats_map.values(),
            key=lambda x: x["last_message_at"],
            reverse=True
        )

        return {
            "chats": chats,
            "next_cursor": result["next_cursor"],
            "total_messages": len(messages)
        }

    def send_message(
        self,
        chat_id: str,
        text: str,
        attachments: Optional[List[str]] = None
    ) -> Dict:
        """
        Отправить сообщение в чат.

        Args:
            chat_id: chatID (формат: "1:UUID")
            text: Текст сообщения (макс. 1000 символов)
            attachments: Пути к файлам (опционально)

        Returns:
            {
                "external_message_id": str,
                "created_at": datetime
            }

        Raises:
            ValueError: Если модерация WB отклонила сообщение
        """
        files = []
        data = {
            "replySign": chat_id,
            "message": text[:1000]  # Обрезать до 1000 символов
        }

        if attachments:
            for file_path in attachments:
                files.append(("file", open(file_path, "rb")))

        try:
            response = requests.post(
                f"{self.BASE_URL}/api/v1/seller/message",
                headers={"Authorization": f"Bearer {self.token}"},
                data=data,
                files=files if files else None,
                timeout=15
            )
            response.raise_for_status()

            result = response.json()

            # Проверка ошибок модерации
            if result.get("errors"):
                error_msg = result["errors"][0].get("message", "Unknown error")
                raise ValueError(f"WB moderation error: {error_msg}")

            add_time = result.get("result", {}).get("addTime", 0)
            return {
                "external_message_id": f"{chat_id}-{add_time}",
                "created_at": datetime.fromtimestamp(add_time / 1000) if add_time else datetime.utcnow()
            }
        finally:
            # Закрыть файлы
            for _, file_obj in files:
                file_obj.close()

    def download_file(self, download_id: str, output_path: str) -> bool:
        """
        Скачать файл из сообщения.

        Args:
            download_id: ID файла из message.files[].downloadID
            output_path: Путь для сохранения

        Returns:
            True если успешно
        """
        response = requests.get(
            f"{self.BASE_URL}/api/v1/seller/download/{download_id}",
            headers=self.headers,
            stream=True,
            timeout=30
        )
        response.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        return True

    def get_statistics(self, since_cursor: Optional[int] = None) -> Dict:
        """
        Получить статистику по чатам и сообщениям.

        Полезно для dashboard и мониторинга.

        Returns:
            {
                "total_chats": int,
                "new_chats": int,
                "total_messages": int,
                "messages_from_clients": int,
                "messages_from_seller": int,
                "unread_count": int
            }
        """
        result = self.fetch_messages(since_cursor=since_cursor)
        messages = result["messages"]

        # Подсчет уникальных чатов
        chat_ids = set(msg["chat_id"] for msg in messages)
        new_chats = sum(1 for msg in messages if msg.get("is_new_chat"))

        # Подсчет по типу автора
        client_msgs = sum(1 for msg in messages if msg["author_type"] == "buyer")
        seller_msgs = sum(1 for msg in messages if msg["author_type"] == "seller")

        return {
            "total_chats": len(chat_ids),
            "new_chats": new_chats,
            "total_messages": len(messages),
            "messages_from_clients": client_msgs,
            "messages_from_seller": seller_msgs,
            "unread_count": client_msgs,  # Упрощенно: все от клиента = непрочитано
            "next_cursor": result["next_cursor"]
        }


# Placeholder для будущих коннекторов
class OzonConnector:
    """Connector для Ozon Chat API (в разработке)."""
    pass


class YandexMarketConnector:
    """Connector для Яндекс.Маркет Chat API (в разработке)."""
    pass
