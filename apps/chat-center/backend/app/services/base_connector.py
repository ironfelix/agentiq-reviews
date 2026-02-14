"""Base connector interface for marketplace channel connectors.

This module defines the abstract base class that all marketplace connectors
(WB, Ozon) must implement. It provides a unified interface for:
- Listing items (chats, reviews, questions)
- Sending replies
- Marking items as read/viewed

Design principles:
- Not all connectors support all methods (e.g., mark_read may not exist)
- Methods that aren't applicable raise NotImplementedError by default
- Connectors are identified by (marketplace, channel) tuple
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseChannelConnector(ABC):
    """Abstract base class for marketplace channel connectors.

    Attributes:
        marketplace: Marketplace identifier ("wb", "ozon")
        channel: Communication channel ("chat", "review", "question")
    """

    marketplace: str
    channel: str

    @abstractmethod
    async def list_items(
        self,
        *,
        skip: int = 0,
        take: int = 100,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """List items (chats/reviews/questions) from the marketplace.

        Args:
            skip: Number of items to skip (pagination offset)
            take: Number of items to fetch (page size)
            **kwargs: Channel-specific filters (e.g., is_answered, nm_id, chat_id)

        Returns:
            Dict containing:
                - "data": List of items (structure varies by channel)
                - Optional pagination metadata (total, has_more, next_cursor, etc.)

        Raises:
            NotImplementedError: If the connector doesn't support listing
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement list_items"
        )

    async def send_reply(self, *, item_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Send a reply to an item (message, review answer, question answer).

        Args:
            item_id: External ID of the item (chat_id, feedback_id, question_id)
            text: Reply text content
            **kwargs: Channel-specific parameters (e.g., attachments, state)

        Returns:
            Dict containing:
                - Success indicator (e.g., {"success": True})
                - Optional external_message_id or similar

        Raises:
            NotImplementedError: If the connector doesn't support replies
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement send_reply"
        )

    async def mark_read(self, *, item_id: str, **kwargs: Any) -> bool:
        """Mark an item as read/viewed.

        Args:
            item_id: External ID of the item
            **kwargs: Channel-specific parameters (e.g., was_viewed)

        Returns:
            True if successful, False otherwise

        Raises:
            NotImplementedError: If the connector doesn't support mark_read
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement mark_read"
        )

    async def get_updates(
        self,
        *,
        since_cursor: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Get incremental updates (new items since last sync).

        This is an optional method for connectors that support cursor-based
        incremental sync (e.g., WB Chat API /events, Ozon /updates).

        Args:
            since_cursor: Cursor from previous sync (None = fetch from beginning)
            limit: Maximum number of items to fetch
            **kwargs: Channel-specific filters

        Returns:
            Dict containing:
                - "items": List of new items
                - "next_cursor": Cursor for next sync
                - "has_more": Boolean indicating if more items exist

        Raises:
            NotImplementedError: If the connector doesn't support incremental sync
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement get_updates"
        )
