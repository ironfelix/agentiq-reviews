"""Wildberries Questions API connector."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class WBQuestionsConnector:
    """Async connector for WB user-communication questions endpoints."""

    BASE_URL = "https://feedbacks-api.wildberries.ru"

    def __init__(self, api_token: str):
        self.api_token = api_token.strip()

    def _auth_header_candidates(self) -> list[str]:
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
                            "WB questions API error %s %s: %s",
                            status_code,
                            endpoint,
                            body,
                        )
                        if status_code == 429:
                            import asyncio

                            await asyncio.sleep(2 ** attempt)
                            continue
                        if status_code == 401:
                            break
                        raise

                    except httpx.TimeoutException as exc:
                        last_error = exc
                        logger.warning(
                            "WB questions timeout on %s attempt %s/3",
                            endpoint,
                            attempt + 1,
                        )
                        if attempt == 2:
                            raise
                        import asyncio

                        await asyncio.sleep(1)

                    except Exception as exc:
                        last_error = exc
                        logger.error("WB questions request failed %s: %s", endpoint, exc)
                        raise

            if last_error:
                raise last_error
            raise RuntimeError("WB questions request failed without explicit error")

    async def count_unanswered(self) -> Dict[str, Any]:
        """Get unanswered questions counters."""
        return await self._request("GET", "/api/v1/questions/count-unanswered")

    async def list_questions(
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

        return await self._request("GET", "/api/v1/questions", params=params)

    async def patch_question(
        self,
        *,
        question_id: str,
        state: str,
        answer_text: Optional[str] = None,
        was_viewed: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update question state and/or answer.

        Known valid patterns:
        - {"id": "...", "state": "wbRu", "wasViewed": true}
        - {"id": "...", "state": "wbRu", "answer": {"text": "..."}}
        """
        payload: Dict[str, Any] = {"id": question_id, "state": state}
        if was_viewed is not None:
            payload["wasViewed"] = was_viewed
        if answer_text is not None:
            payload["answer"] = {"text": answer_text}

        return await self._request("PATCH", "/api/v1/questions", json=payload)


async def get_wb_questions_connector_for_seller(seller_id: int, db_session) -> WBQuestionsConnector:
    """Factory for seller-specific questions connector."""
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
    return WBQuestionsConnector(api_token=api_token)
