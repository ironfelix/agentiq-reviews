"""Ozon Seller Chat API connector - асинхронный клиент для работы с Ozon Chat API"""

import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OzonConnector:
    """Асинхронный коннектор для Ozon Seller Chat API v1"""

    BASE_URL = "https://api-seller.ozon.ru"

    def __init__(self, client_id: str, api_key: str):
        """
        Initialize Ozon API connector.

        Args:
            client_id: Ozon Client-Id
            api_key: Ozon Api-Key
        """
        self.client_id = client_id
        self.api_key = api_key
        self.headers = {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json"
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        timeout: float = 30.0
    ) -> Dict[str, Any]:
        """
        Make async HTTP request to Ozon API.

        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint (e.g., "/v1/chat/list")
            json_data: Request body (for POST)
            timeout: Request timeout in seconds

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: On HTTP error
        """
        url = f"{self.BASE_URL}{endpoint}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    json=json_data
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Ozon API error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"Ozon API request failed: {e}")
                raise

    async def list_chats(
        self,
        chat_id_list: Optional[List[str]] = None,
        chat_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get list of chats. POST /v1/chat/list

        Args:
            chat_id_list: Filter by chat IDs (max 100)
            chat_status: Filter by status ('opened', 'closed')
            limit: Number of chats to return (max 100)
            offset: Pagination offset

        Returns:
            {
                "chats": [
                    {
                        "chat_id": "string",
                        "chat_status": "opened",
                        "chat_type": "Buyer_Seller",
                        "created_at": "2024-02-08T10:00:00Z",
                        "first_message_id": "string",
                        "last_message_created_at": "2024-02-08T10:30:00Z",
                        "unread_count": 2
                    }
                ],
                "total": 42
            }
        """
        payload: Dict[str, Any] = {
            "limit": limit,
            "offset": offset
        }

        if chat_id_list:
            payload["chat_id_list"] = chat_id_list
        if chat_status:
            payload["chat_status"] = chat_status

        return await self._request("POST", "/v1/chat/list", json_data=payload)

    async def get_chat_history(
        self,
        chat_id: str,
        from_message_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get chat message history. POST /v1/chat/history

        Args:
            chat_id: Chat identifier
            from_message_id: Get messages after this ID (for pagination)
            limit: Number of messages (max 100)

        Returns:
            {
                "messages": [
                    {
                        "id": "string",
                        "chat_id": "string",
                        "created_at": "2024-02-08T10:00:00Z",
                        "data": {
                            "text": "Hello!",
                            "attachments": [
                                {
                                    "id": "string",
                                    "name": "image.jpg",
                                    "url": "https://..."
                                }
                            ]
                        },
                        "direction": "income",
                        "user": {
                            "id": "string",
                            "type": "Customer"
                        }
                    }
                ],
                "total": 15
            }
        """
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "limit": limit
        }

        if from_message_id:
            payload["from_message_id"] = from_message_id

        return await self._request("POST", "/v1/chat/history", json_data=payload)

    async def send_message(
        self,
        chat_id: str,
        text: str
    ) -> Dict[str, Any]:
        """
        Send text message to chat. POST /v1/chat/send/message

        Args:
            chat_id: Chat identifier
            text: Message text

        Returns:
            {
                "message_id": "string",
                "created_at": "2024-02-08T10:35:00Z"
            }
        """
        payload = {
            "chat_id": chat_id,
            "text": text
        }

        return await self._request("POST", "/v1/chat/send/message", json_data=payload)

    async def send_file(
        self,
        chat_id: str,
        file_name: str,
        file_content_base64: str
    ) -> Dict[str, Any]:
        """
        Send file attachment to chat. POST /v1/chat/send/file

        Args:
            chat_id: Chat identifier
            file_name: File name with extension
            file_content_base64: Base64-encoded file content

        Returns:
            {
                "message_id": "string",
                "created_at": "2024-02-08T10:36:00Z"
            }
        """
        payload = {
            "chat_id": chat_id,
            "file_name": file_name,
            "content": file_content_base64
        }

        return await self._request("POST", "/v1/chat/send/file", json_data=payload)

    async def get_updates(
        self,
        chat_id_list: Optional[List[str]] = None,
        from_message_id: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get new messages across all or specific chats. POST /v1/chat/updates

        This is the primary method for incremental sync/polling.

        Args:
            chat_id_list: Filter by chat IDs (max 100)
            from_message_id: Get messages after this ID (for incremental sync)
            limit: Number of messages (max 100)

        Returns:
            {
                "messages": [
                    {
                        "id": "string",
                        "chat_id": "string",
                        "created_at": "2024-02-08T10:40:00Z",
                        "data": {
                            "text": "Message text",
                            "attachments": []
                        },
                        "direction": "income",
                        "user": {
                            "id": "string",
                            "type": "Customer"
                        }
                    }
                ],
                "total": 3,
                "last_message_id": "string"
            }
        """
        payload: Dict[str, Any] = {
            "limit": limit
        }

        if chat_id_list:
            payload["chat_id_list"] = chat_id_list
        if from_message_id:
            payload["from_message_id"] = from_message_id

        return await self._request("POST", "/v1/chat/updates", json_data=payload)


async def get_connector_for_seller(seller_id: int, db_session) -> OzonConnector:
    """
    Factory function to create OzonConnector for a specific seller.

    Args:
        seller_id: Seller ID from database
        db_session: AsyncSession instance

    Returns:
        Configured OzonConnector instance

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

    if not seller.client_id or not seller.api_key_encrypted:
        raise ValueError(f"Seller {seller_id} missing Ozon credentials")

    api_key = decrypt_credentials(seller.api_key_encrypted)

    return OzonConnector(
        client_id=seller.client_id,
        api_key=api_key
    )
