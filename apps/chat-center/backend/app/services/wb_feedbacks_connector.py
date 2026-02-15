"""Wildberries Feedbacks API connector (reviews)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from app.services.base_connector import BaseChannelConnector

logger = logging.getLogger(__name__)


class WBFeedbacksConnector(BaseChannelConnector):
    """
    Async connector for WB Questions & Reviews API (feedbacks group).

    Docs:
    - https://dev.wildberries.ru/openapi/user-communication
    """

    BASE_URL = "https://feedbacks-api.wildberries.ru"
    marketplace = "wildberries"
    channel = "review"

    def __init__(self, api_token: str):
        self.api_token = api_token.strip()

    def _auth_header_candidates(self) -> list[str]:
        """
        WB docs specify Authorization token.
        Some integrations historically used `Bearer <token>`.
        We keep both variants for compatibility and retry on 401.
        """
        token = self.api_token
        if token.lower().startswith("bearer "):
            raw = token[7:].strip()
            return [token, raw]
        return [token, f"Bearer {token}"]

    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"
        auth_candidates = self._auth_header_candidates()

        async with httpx.AsyncClient(timeout=timeout) as client:
            last_error: Optional[Exception] = None

            for auth_value in auth_candidates:
                headers = {
                    "Authorization": auth_value,
                    "Content-Type": "application/json",
                }

                for attempt in range(3):
                    try:
                        response = await client.request(
                            method=method,
                            url=url,
                            headers=headers,
                            params=params,
                            json=json,
                        )

                        if response.status_code == 401 and auth_value != auth_candidates[-1]:
                            # Try another auth header variant.
                            break

                        response.raise_for_status()
                        payload = response.json()
                        if isinstance(payload, dict):
                            return payload
                        return {"data": payload}

                    except httpx.HTTPStatusError as exc:
                        last_error = exc
                        status_code = exc.response.status_code
                        body = exc.response.text[:500]
                        logger.error(
                            "WB feedbacks API error %s %s: %s",
                            status_code,
                            endpoint,
                            body,
                        )
                        if status_code == 429:
                            import asyncio

                            await asyncio.sleep(2 ** attempt)
                            continue
                        if status_code == 401:
                            # Try next auth candidate.
                            break
                        raise

                    except httpx.TimeoutException as exc:
                        last_error = exc
                        logger.warning(
                            "WB feedbacks timeout on %s attempt %s/3",
                            endpoint,
                            attempt + 1,
                        )
                        if attempt == 2:
                            raise
                        import asyncio

                        await asyncio.sleep(1)

                    except Exception as exc:
                        last_error = exc
                        logger.error("WB feedbacks request failed %s: %s", endpoint, exc)
                        raise

            if last_error:
                raise last_error
            raise RuntimeError("WB feedbacks request failed without explicit error")

    async def list_items(
        self,
        *,
        skip: int = 0,
        take: int = 100,
        is_answered: bool = False,
        order: str = "dateDesc",
        nm_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """List feedbacks (reviews) from WB API.

        This is the BaseChannelConnector interface implementation.
        For backwards compatibility, list_feedbacks() is also available.
        """
        return await self.list_feedbacks(
            skip=skip,
            take=take,
            is_answered=is_answered,
            order=order,
            nm_id=nm_id,
        )

    async def list_feedbacks(
        self,
        *,
        skip: int = 0,
        take: int = 100,
        is_answered: bool = False,
        order: str = "dateDesc",
        nm_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "skip": skip,
            "take": take,
            "order": order,
            "isAnswered": is_answered,
        }
        if nm_id is not None:
            params["nmId"] = nm_id

        return await self._request("GET", "/api/v1/feedbacks", params=params)

    async def send_reply(self, *, item_id: str, text: str, **kwargs: Any) -> Dict[str, Any]:
        """Send reply to a feedback (review).

        This is the BaseChannelConnector interface implementation.
        For backwards compatibility, answer_feedback() is also available.
        """
        success = await self.answer_feedback(feedback_id=item_id, text=text)
        return {"success": success}

    async def answer_feedback(self, *, feedback_id: str, text: str) -> bool:
        """
        Reply to a feedback (review).

        Endpoint behavior:
        - 204: success
        - 4xx/5xx: error
        """
        payload = {"id": feedback_id, "text": text}
        url = f"{self.BASE_URL}/api/v1/feedbacks/answer"
        auth_candidates = self._auth_header_candidates()

        async with httpx.AsyncClient(timeout=20.0) as client:
            last_error: Optional[Exception] = None
            for auth_value in auth_candidates:
                headers = {
                    "Authorization": auth_value,
                    "Content-Type": "application/json",
                }
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code == 401 and auth_value != auth_candidates[-1]:
                        continue
                    response.raise_for_status()
                    return response.status_code in (200, 201, 202, 204)
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if exc.response.status_code == 401:
                        continue
                    raise
            if last_error:
                raise last_error
            raise RuntimeError("WB feedbacks answer request failed without explicit error")


async def get_wb_feedbacks_connector_for_seller(seller_id: int, db_session) -> WBFeedbacksConnector:
    """Factory for seller-specific feedbacks connector."""
    from sqlalchemy import select

    from app.models.seller import Seller
    from app.services.encryption import decrypt_credentials

    result = await db_session.execute(
        select(Seller).where(Seller.id == seller_id, Seller.is_active.is_(True))
    )
    seller = result.scalar_one_or_none()

    if not seller:
        raise ValueError(f"Seller {seller_id} not found or inactive")

    if not seller.api_key_encrypted:
        raise ValueError(f"Seller {seller_id} missing WB credentials")

    api_token = decrypt_credentials(seller.api_key_encrypted)
    return WBFeedbacksConnector(api_token=api_token)
