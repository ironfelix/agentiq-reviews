"""
Contract tests for WBQuestionsConnector.

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

from app.services.wb_questions_connector import WBQuestionsConnector

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
def connector() -> WBQuestionsConnector:
    return WBQuestionsConnector(api_token="test-questions-token")


@pytest.fixture
def questions_payload() -> dict:
    return _load_fixture("questions_list.json")


@pytest.fixture
def error_401_payload() -> dict:
    return _load_fixture("error_401.json")


@pytest.fixture
def error_429_payload() -> dict:
    return _load_fixture("error_429.json")


# ---------------------------------------------------------------------------
# Tests: list_questions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_questions_parses_response(connector, questions_payload):
    """200 OK -- connector parses questions list correctly."""
    mock_response = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.list_questions()

    assert "data" in result
    questions = result["data"]["questions"]
    assert len(questions) == 2

    q1 = questions[0]
    assert q1["id"] == "q-111222"
    assert q1["text"] == "Подскажите, какой размер при росте 170?"
    assert q1["answer"] is None
    assert q1["productDetails"]["nmId"] == 987654321

    q2 = questions[1]
    assert q2["id"] == "q-333444"
    assert q2["wasViewed"] is True


@pytest.mark.asyncio
async def test_list_questions_with_answers(connector, questions_payload):
    """Verify answer object is parsed correctly when present."""
    mock_response = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.list_questions()

    questions = result["data"]["questions"]
    answered_q = questions[1]
    assert answered_q["answer"] is not None
    assert answered_q["answer"]["text"] == "Да, синий цвет есть в наличии!"
    assert answered_q["answer"]["editable"] is True
    assert answered_q["answer"]["createDate"] == "2026-02-13T09:00:00Z"


@pytest.mark.asyncio
async def test_list_questions_pagination_params(connector, questions_payload):
    """Verify skip/take/isAnswered/order/nmId params are sent correctly."""
    mock_response = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await connector.list_questions(
            skip=20, take=50, is_answered=True, nm_id=555
        )

    call_kwargs = instance.request.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["skip"] == 20
    assert params["take"] == 50
    assert params["isAnswered"] is True
    assert params["order"] == "dateDesc"
    assert params["nmId"] == 555


# ---------------------------------------------------------------------------
# Tests: count_unanswered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_unanswered(connector):
    """GET /api/v1/questions/count-unanswered returns count dict."""
    count_payload = {"data": {"count": 42}}
    mock_response = _make_response(200, count_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.count_unanswered()

    assert result["data"]["count"] == 42

    call_kwargs = instance.request.call_args
    url = call_kwargs.kwargs.get("url") or call_kwargs[1].get("url")
    assert "/api/v1/questions/count-unanswered" in url


# ---------------------------------------------------------------------------
# Tests: patch_question (answer and wasViewed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_question_answer(connector):
    """PATCH with answer text sends correct payload."""
    mock_response = _make_response(200, {"data": "ok"})

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.patch_question(
            question_id="q-111222",
            state="wbRu",
            answer_text="Рекомендуем размер M при росте 170 см.",
        )

    assert result == {"data": "ok"}

    call_kwargs = instance.request.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["id"] == "q-111222"
    assert sent_json["state"] == "wbRu"
    assert sent_json["answer"]["text"] == "Рекомендуем размер M при росте 170 см."
    assert "wasViewed" not in sent_json

    method = call_kwargs.kwargs.get("method") or call_kwargs[0]
    assert method == "PATCH"


@pytest.mark.asyncio
async def test_patch_question_view(connector):
    """PATCH with wasViewed=True sends correct payload (no answer)."""
    mock_response = _make_response(200, {"data": "ok"})

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=mock_response)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        await connector.patch_question(
            question_id="q-333444",
            state="wbRu",
            was_viewed=True,
        )

    call_kwargs = instance.request.call_args
    sent_json = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
    assert sent_json["id"] == "q-333444"
    assert sent_json["wasViewed"] is True
    assert "answer" not in sent_json


# ---------------------------------------------------------------------------
# Tests: 429 rate limit retry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_questions_429_retry(connector, questions_payload, error_429_payload):
    """Rate limited (429) triggers retry with backoff, then succeeds."""
    resp_429 = _make_response(429, error_429_payload)
    resp_200 = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(side_effect=[resp_429, resp_200])
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await connector.list_questions()

    assert "data" in result
    assert instance.request.call_count == 2
    mock_sleep.assert_called_once_with(1)  # 2^0 = 1


@pytest.mark.asyncio
async def test_questions_429_triple_retry_then_success(connector, questions_payload, error_429_payload):
    """Three 429s then success -- backoff increases each time."""
    resp_429 = _make_response(429, error_429_payload)
    resp_200 = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(
            side_effect=[resp_429, resp_429, resp_200]
        )
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await connector.list_questions()

    assert "data" in result
    assert instance.request.call_count == 3
    # Backoff: 2^0=1, 2^1=2
    assert mock_sleep.call_args_list[0].args == (1,)
    assert mock_sleep.call_args_list[1].args == (2,)


# ---------------------------------------------------------------------------
# Tests: 401 auth fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_questions_401_auth_fallback(connector, questions_payload, error_401_payload):
    """First auth header gets 401, second succeeds."""
    resp_401 = _make_response(401, error_401_payload)
    resp_200 = _make_response(200, questions_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(side_effect=[resp_401, resp_200])
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        result = await connector.list_questions()

    assert "data" in result
    assert instance.request.call_count == 2

    # Different Authorization headers used on each call
    first_headers = instance.request.call_args_list[0].kwargs.get("headers", {})
    second_headers = instance.request.call_args_list[1].kwargs.get("headers", {})
    assert first_headers["Authorization"] != second_headers["Authorization"]


@pytest.mark.asyncio
async def test_questions_401_both_fail_raises(connector, error_401_payload):
    """Both auth candidates return 401 -- raises HTTPStatusError."""
    resp_401 = _make_response(401, error_401_payload)

    with patch("httpx.AsyncClient") as MockClient:
        instance = AsyncMock()
        instance.request = AsyncMock(return_value=resp_401)
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = instance

        with pytest.raises(httpx.HTTPStatusError):
            await connector.list_questions()

    # Two attempts: one per auth candidate
    assert instance.request.call_count == 2


# ---------------------------------------------------------------------------
# Tests: auth header candidates
# ---------------------------------------------------------------------------


def test_questions_auth_header_candidates_raw_token():
    """Raw token produces [token, 'Bearer token']."""
    c = WBQuestionsConnector(api_token="my-raw-token")
    candidates = c._auth_header_candidates()
    assert candidates == ["my-raw-token", "Bearer my-raw-token"]


def test_questions_auth_header_candidates_bearer_prefix():
    """Token with 'Bearer' prefix produces [original, raw]."""
    c = WBQuestionsConnector(api_token="Bearer my-raw-token")
    candidates = c._auth_header_candidates()
    assert candidates == ["Bearer my-raw-token", "my-raw-token"]
