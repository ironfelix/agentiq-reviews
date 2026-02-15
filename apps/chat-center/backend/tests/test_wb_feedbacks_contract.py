"""
Contract tests for WBFeedbacksConnector.

All HTTP interactions are mocked at the httpx.AsyncClient level.
No real API calls are made.
"""

import json
import os
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, patch

import httpx
import pytest

os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_contract.db")

from app.services.wb_feedbacks_connector import WBFeedbacksConnector

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "wb_api"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


def _make_response(
    status_code: int = 200,
    json_data: Optional[dict] = None,
    text: str = "",
) -> httpx.Response:
    """Build a fake httpx.Response."""
    resp = httpx.Response(
        status_code=status_code,
        request=httpx.Request("GET", "https://feedbacks-api.wildberries.ru/test"),
    )
    if json_data is not None:
        resp._content = json.dumps(json_data).encode("utf-8")
        resp.headers["content-type"] = "application/json"
    else:
        resp._content = text.encode("utf-8")
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def connector() -> WBFeedbacksConnector:
    return WBFeedbacksConnector(api_token="test-token-abc123")


@pytest.fixture
def feedbacks_payload() -> dict:
    return _load_fixture("feedbacks_list.json")


@pytest.fixture
def error_401_payload() -> dict:
    return _load_fixture("error_401.json")


@pytest.fixture
def error_429_payload() -> dict:
    return _load_fixture("error_429.json")


# ---------------------------------------------------------------------------
# Tests: list_feedbacks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_feedbacks_parses_response(connector, feedbacks_payload):
    """200 OK -- connector returns the parsed dict with feedbacks list."""
    mock_response = _make_response(200, feedbacks_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.list_feedbacks()

    assert "data" in result
    feedbacks = result["data"]["feedbacks"]
    assert len(feedbacks) == 2

    fb1 = feedbacks[0]
    assert fb1["id"] == "fb-123456"
    assert fb1["productValuation"] == 5
    assert fb1["text"] == "Отличный товар, всё работает!"
    assert fb1["productDetails"]["nmId"] == 123456789

    fb2 = feedbacks[1]
    assert fb2["id"] == "fb-789012"
    assert fb2["productValuation"] == 1
    assert fb2["answerText"] == "Приносим извинения!"


@pytest.mark.asyncio
async def test_list_feedbacks_empty_response(connector):
    """Empty feedbacks list is returned correctly."""
    empty_payload = {"data": {"feedbacks": []}}
    mock_response = _make_response(200, empty_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.list_feedbacks()

    assert result["data"]["feedbacks"] == []


@pytest.mark.asyncio
async def test_list_feedbacks_pagination_params(connector, feedbacks_payload):
    """Verify skip/take/isAnswered/order params are sent correctly."""
    mock_response = _make_response(200, feedbacks_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await connector.list_feedbacks(skip=50, take=25, is_answered=True, nm_id=999)

    call_kwargs = instance.request.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["skip"] == 50
    assert params["take"] == 25
    assert params["isAnswered"] is True
    assert params["order"] == "dateDesc"
    assert params["nmId"] == 999


# ---------------------------------------------------------------------------
# Tests: answer_feedback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answer_feedback_success(connector):
    """204 No Content -- answer_feedback returns True."""
    mock_response = _make_response(204)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.answer_feedback(
            feedback_id="fb-123456",
            text="Спасибо за отзыв! Рады, что вам понравилось.",
        )

    assert result is True

    call_kwargs = instance.post.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["id"] == "fb-123456"
    assert "Спасибо за отзыв" in sent_json["text"]


# ---------------------------------------------------------------------------
# Tests: 401 auth retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_answer_feedback_401_retry(connector, error_401_payload):
    """First auth header gets 401, second succeeds with 204."""
    resp_401 = _make_response(401, error_401_payload)
    resp_204 = _make_response(204)

    # First call -> 401, second call -> 204
    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.post = AsyncMock(side_effect=[resp_401, resp_204])
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.answer_feedback(
            feedback_id="fb-789012",
            text="Приносим извинения за неудобства!",
        )

    assert result is True
    assert instance.post.call_count == 2

    # Verify different auth headers were used
    first_auth = instance.post.call_args_list[0].kwargs.get("headers", {}).get("Authorization")
    second_auth = instance.post.call_args_list[1].kwargs.get("headers", {}).get("Authorization")
    assert first_auth != second_auth


# ---------------------------------------------------------------------------
# Tests: 429 rate limit retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_feedbacks_429_retry(connector, feedbacks_payload, error_429_payload):
    """Rate limited (429) triggers exponential backoff, then succeeds."""
    resp_429 = _make_response(429, error_429_payload)
    # 429 is raised via raise_for_status(), so we need HTTPStatusError behavior.
    # The connector catches HTTPStatusError for 429, sleeps, and retries.
    # With _make_response, raise_for_status() will raise for 429.
    resp_200 = _make_response(200, feedbacks_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(side_effect=[resp_429, resp_200])
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await connector.list_feedbacks()

    assert "data" in result
    assert instance.request.call_count == 2
    # First retry sleeps 2^0 = 1 second
    mock_sleep.assert_called_once_with(1)


# ---------------------------------------------------------------------------
# Tests: timeout retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_feedbacks_timeout(connector, feedbacks_payload):
    """Timeout on first attempt, success on second."""
    resp_200 = _make_response(200, feedbacks_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(
            side_effect=[httpx.TimeoutException("timed out"), resp_200]
        )
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await connector.list_feedbacks()

    assert "data" in result
    assert instance.request.call_count == 2


@pytest.mark.asyncio
async def test_list_feedbacks_timeout_exhausted(connector):
    """All 3 attempts timeout -- exception is raised."""
    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(httpx.TimeoutException):
                await connector.list_feedbacks()

    # 3 attempts for first auth candidate
    assert instance.request.call_count == 3


# ---------------------------------------------------------------------------
# Tests: 502 server error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_feedbacks_502_raises(connector):
    """502 Bad Gateway -- raises HTTPStatusError immediately (no retry)."""
    resp_502 = _make_response(502, {"error": "Bad Gateway"})

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=resp_502)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(httpx.HTTPStatusError):
            await connector.list_feedbacks()

    # Only one attempt -- 502 is not retried
    assert instance.request.call_count == 1


# ---------------------------------------------------------------------------
# Tests: auth header candidates
# ---------------------------------------------------------------------------


def test_auth_header_candidates_raw_token():
    """Raw token produces [token, 'Bearer token']."""
    c = WBFeedbacksConnector(api_token="my-raw-token")
    candidates = c._auth_header_candidates()
    assert candidates == ["my-raw-token", "Bearer my-raw-token"]


def test_auth_header_candidates_bearer_prefix():
    """Token already with 'Bearer' prefix -- produces [original, raw]."""
    c = WBFeedbacksConnector(api_token="Bearer my-raw-token")
    candidates = c._auth_header_candidates()
    assert candidates == ["Bearer my-raw-token", "my-raw-token"]


def test_auth_header_candidates_bearer_case_insensitive():
    """'bearer' lowercase is also recognized."""
    c = WBFeedbacksConnector(api_token="bearer my-raw-token")
    candidates = c._auth_header_candidates()
    assert candidates == ["bearer my-raw-token", "my-raw-token"]


def test_auth_header_strips_whitespace():
    """Leading/trailing whitespace is stripped from token."""
    c = WBFeedbacksConnector(api_token="  my-token  ")
    assert c.api_token == "my-token"
