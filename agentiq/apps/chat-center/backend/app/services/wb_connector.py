"""Wildberries Chat API connector - асинхронный клиент для работы с WB Chat API"""

import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class WBConnector:
    """
    Асинхронный коннектор для Wildberries Chat API v1.

    Особенности WB API (протестировано 2026-02-09):
    - Events API возвращает больше данных, чем описано в документации
    - /chats может быть пустым, даже если есть события → используй fetch_messages_as_chats()
    - eventID можно использовать как уникальный идентификатор
    - Cursor pagination через параметр `next`
    """

    BASE_URL = "https://buyer-chat-api.wildberries.ru"

    def __init__(self, api_token: str):
        """
        Initialize WB API connector.

        Args:
            api_token: WB API token from seller dashboard
        """
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[List] = None,
        timeout: float = 15.0
    ) -> Dict[str, Any]:
        """
        Make async HTTP request to WB API with retry logic.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., "/api/v1/seller/chats")
            params: Query parameters
            data: Form data (for POST)
            files: Files to upload
            timeout: Request timeout in seconds

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: On HTTP error
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(3):  # Retry up to 3 times
                try:
                    if files:
                        # Multipart form data for file uploads
                        response = await client.post(
                            url,
                            headers={"Authorization": f"Bearer {self.api_token}"},
                            data=data,
                            files=files
                        )
                    else:
                        response = await client.request(
                            method=method,
                            url=url,
                            headers=self.headers,
                            params=params,
                            json=data if method == "POST" and not files else None
                        )

                    response.raise_for_status()
                    return response.json()

                except httpx.HTTPStatusError as e:
                    logger.error(f"WB API error: {e.response.status_code} - {e.response.text}")
                    if e.response.status_code == 429:  # Rate limit
                        import asyncio
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    raise

                except httpx.TimeoutException:
                    logger.warning(f"WB API timeout, attempt {attempt + 1}/3")
                    if attempt == 2:
                        raise
                    import asyncio
                    await asyncio.sleep(1)
                    continue

                except Exception as e:
                    logger.error(f"WB API request failed: {e}")
                    raise

        raise RuntimeError("Max retries exceeded")

    async def fetch_chats(self, since: Optional[datetime] = None) -> List[Dict]:
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
        data = await self._request("GET", "/api/v1/seller/chats")
        chats = []

        for chat in data.get("chats", []):
            last_message_at = datetime.fromisoformat(
                chat["lastMessageTime"].replace("Z", "+00:00")
            )

            if since and last_message_at < since:
                continue

            # Extract goodCard (product + order data, present on every chat)
            good_card = chat.get("goodCard")

            chats.append({
                "external_chat_id": chat["chatID"],
                "client_name": chat.get("clientName", ""),
                "client_id": chat.get("clientID", ""),
                "status": "open",
                "unread_count": 0,
                "last_message_at": last_message_at,
                "good_card": good_card,
            })

        return chats

    async def fetch_messages(
        self,
        chat_id: Optional[str] = None,
        since_cursor: Optional[int] = None,
        limit: int = 50
    ) -> Dict:
        """
        Получить новые события (сообщения) с cursor pagination.

        Структура реального response:
        {
          "chatID": "1:UUID",
          "eventID": "UUID",              ← уникальный ID события
          "eventType": "message",
          "isNewChat": true,              ← флаг нового чата
          "addTimestamp": 1742404763767,  ← UNIX ms
          "addTime": "2025-03-19T17:19:23Z",
          "sender": "client" | "seller",
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

        data = await self._request("GET", "/api/v1/seller/events", params=params)

        result = data.get("result", {})
        events = result.get("events", [])
        next_cursor = result.get("next")

        messages = []
        for event in events:
            if chat_id and event.get("chatID") != chat_id:
                continue

            message_id = event.get("eventID", f"{event['chatID']}-{next_cursor}")

            created_at = datetime.utcnow()
            if event.get("addTimestamp"):
                created_at = datetime.fromtimestamp(event["addTimestamp"] / 1000)
            elif event.get("addTime"):
                created_at = datetime.fromisoformat(event["addTime"].replace("Z", "+00:00"))

            # Extract text and attachments (real API uses message.attachments, not message.files)
            msg_data = event.get("message", {})
            raw_text = msg_data.get("text", "")
            att = msg_data.get("attachments", {})

            # Images from attachments.images[] (real API) or files[] (legacy)
            images = [
                {"type": "image", "url": img.get("url", "")}
                for img in att.get("images", [])
            ]
            files = [
                {"type": "file", "file_name": f.get("fileName", ""), "download_id": f.get("downloadID", "")}
                for f in msg_data.get("files", [])
            ]
            attachments = images or files

            # Extract goodCard (product + order info)
            good_card = att.get("goodCard")

            # Normalize text for empty messages with attachments
            text = raw_text.strip() if raw_text else ""
            if not text and attachments:
                count = len(attachments)
                text = "[Изображение]" if count == 1 else f"[{count} изображений]"

            messages.append({
                "external_message_id": message_id,
                "event_id": event.get("eventID", ""),
                "chat_id": event["chatID"],
                "author_type": "buyer" if event["sender"] == "client" else "seller",
                "text": text,
                "attachments": attachments,
                "created_at": created_at,
                "is_new_chat": event.get("isNewChat", False),
                "event_type": event.get("eventType", "message"),
                "client_name": event.get("clientName", ""),
                "client_id": event.get("clientID", ""),
                "good_card": good_card,
            })

        return {
            "messages": messages,
            "next_cursor": next_cursor,
            "has_more": len(events) > 0
        }

    async def fetch_messages_as_chats(
        self,
        since_cursor: Optional[int] = None
    ) -> Dict:
        """
        Получить список чатов, построенный из событий.

        Более надежный метод, чем fetch_chats(), т.к. /chats может быть пустым.

        Returns:
            {
                "chats": List[Dict],
                "next_cursor": int,
                "total_messages": int
            }
        """
        result = await self.fetch_messages(since_cursor=since_cursor)
        messages = result["messages"]

        chats_map: Dict[str, Dict] = {}
        for msg in messages:
            chat_id = msg["chat_id"]

            if chat_id not in chats_map:
                chats_map[chat_id] = {
                    "external_chat_id": chat_id,
                    "client_name": msg.get("client_name", ""),
                    "client_id": msg.get("client_id", ""),
                    "status": "open",
                    "last_message_at": msg["created_at"],
                    "last_message_text": msg["text"][:100] if msg["text"] else "",
                    "unread_count": 0,
                    "is_new_chat": msg.get("is_new_chat", False)
                }
            else:
                if msg["created_at"] > chats_map[chat_id]["last_message_at"]:
                    chats_map[chat_id]["last_message_at"] = msg["created_at"]
                    chats_map[chat_id]["last_message_text"] = msg["text"][:100] if msg["text"] else ""

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

    async def send_message(
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
        data = {
            "replySign": chat_id,
            "message": text[:1000]
        }

        files = None
        if attachments:
            files = []
            for file_path in attachments:
                with open(file_path, "rb") as f:
                    files.append(("file", (file_path, f.read())))

        result = await self._request(
            "POST",
            "/api/v1/seller/message",
            data=data,
            files=files
        )

        if result.get("errors"):
            error_msg = result["errors"][0].get("message", "Unknown error")
            raise ValueError(f"WB moderation error: {error_msg}")

        add_time = result.get("result", {}).get("addTime", 0)
        return {
            "external_message_id": f"{chat_id}-{add_time}",
            "created_at": datetime.fromtimestamp(add_time / 1000) if add_time else datetime.utcnow()
        }

    async def download_file(self, download_id: str) -> bytes:
        """
        Скачать файл из сообщения.

        Args:
            download_id: ID файла из message.files[].downloadID

        Returns:
            File content as bytes
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.BASE_URL}/api/v1/seller/download/{download_id}",
                headers=self.headers
            )
            response.raise_for_status()
            return response.content

    async def get_statistics(self, since_cursor: Optional[int] = None) -> Dict:
        """
        Получить статистику по чатам и сообщениям.

        Returns:
            {
                "total_chats": int,
                "new_chats": int,
                "total_messages": int,
                "messages_from_clients": int,
                "messages_from_seller": int,
                "unread_count": int,
                "next_cursor": int
            }
        """
        result = await self.fetch_messages(since_cursor=since_cursor)
        messages = result["messages"]

        chat_ids = set(msg["chat_id"] for msg in messages)
        new_chats = sum(1 for msg in messages if msg.get("is_new_chat"))
        client_msgs = sum(1 for msg in messages if msg["author_type"] == "buyer")
        seller_msgs = sum(1 for msg in messages if msg["author_type"] == "seller")

        return {
            "total_chats": len(chat_ids),
            "new_chats": new_chats,
            "total_messages": len(messages),
            "messages_from_clients": client_msgs,
            "messages_from_seller": seller_msgs,
            "unread_count": client_msgs,
            "next_cursor": result["next_cursor"]
        }


def _get_basket_number(nm_id: int) -> str:
    """Get WB CDN basket number by nmID."""
    vol = nm_id // 100000
    ranges = [
        (143, "01"), (287, "02"), (431, "03"), (719, "04"), (1007, "05"),
        (1061, "06"), (1115, "07"), (1169, "08"), (1313, "09"), (1601, "10"),
        (1655, "11"), (1919, "12"), (2045, "13"), (2189, "14"), (2405, "15"),
        (2621, "16"), (2837, "17"), (3053, "18"), (3269, "19"), (3485, "20"),
        (3701, "21"), (3917, "22"), (4133, "23"), (4349, "24"), (4565, "25"),
    ]
    for threshold, basket in ranges:
        if vol <= threshold:
            return basket
    return "26"


async def fetch_product_name(nm_id: int) -> Optional[str]:
    """
    Fetch product name from WB CDN API (no auth required).

    Args:
        nm_id: WB article number (nmID from goodCard)

    Returns:
        Product name (imt_name) or None
    """
    basket = _get_basket_number(nm_id)
    vol = nm_id // 100000
    part = nm_id // 1000
    url = f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/info/ru/card.json"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("imt_name", "")
            return None
    except Exception as e:
        logger.debug(f"Failed to fetch product name for nmID {nm_id}: {e}")
        return None


async def get_wb_connector_for_seller(seller_id: int, db_session) -> WBConnector:
    """
    Factory function to create WBConnector for a specific seller.

    Args:
        seller_id: Seller ID from database
        db_session: AsyncSession instance

    Returns:
        Configured WBConnector instance

    Raises:
        ValueError: If seller not found or credentials missing
    """
    from app.models.seller import Seller
    from app.services.encryption import decrypt_credentials
    from sqlalchemy import select

    result = await db_session.execute(
        select(Seller).where(Seller.id == seller_id, Seller.is_active == True)
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise ValueError(f"Seller {seller_id} not found or inactive")

    if not seller.api_key_encrypted:
        raise ValueError(f"Seller {seller_id} missing WB credentials")

    api_token = decrypt_credentials(seller.api_key_encrypted)

    return WBConnector(api_token=api_token)
