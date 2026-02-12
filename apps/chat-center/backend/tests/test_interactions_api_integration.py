"""Integration tests for unified interactions API endpoints."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

# Ensure settings are loaded for isolated test DB.
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_interactions_api.db"

from app.database import AsyncSessionLocal, Base, engine
from app.main import app
from app.models.chat import Chat
from app.models.interaction import Interaction
from app.models.seller import Seller
from app.services.interaction_drafts import DraftResult

TEST_DB_PATH = Path("./test_interactions_api.db")


class _FakeFeedbacksConnector:
    async def list_feedbacks(self, *, skip=0, take=100, is_answered=False, order="dateDesc", nm_id=None):
        if skip > 0:
            return {"data": {"feedbacks": []}}
        if is_answered:
            return {
                "data": {
                    "feedbacks": [
                        {
                            "id": "fb-2",
                            "text": "",
                            "pros": "Качественный",
                            "cons": "",
                            "productValuation": 5,
                            "answerText": "Спасибо за отзыв!",
                            "answerCreateDate": "2026-02-10T13:00:00Z",
                            "createdDate": "2026-02-09T10:00:00Z",
                            "userName": "Покупатель 2",
                            "answerState": "answered",
                            "wasViewed": True,
                            "supplierProductID": "order-2",
                            "productDetails": {
                                "nmId": 12345,
                                "supplierArticle": "A-1",
                                "productName": "Тестовый товар",
                            },
                        }
                    ]
                }
            }
        return {
            "data": {
                "feedbacks": [
                    {
                        "id": "fb-1",
                        "text": "Товар пришел с дефектом",
                        "pros": "",
                        "cons": "Скол",
                        "productValuation": 2,
                        "answerText": "",
                        "createdDate": "2026-02-10T10:00:00Z",
                        "userName": "Покупатель",
                        "answerState": "none",
                        "wasViewed": False,
                        "supplierProductID": "order-1",
                        "productDetails": {
                            "nmId": 12345,
                            "supplierArticle": "A-1",
                            "productName": "Тестовый товар",
                        },
                    }
                ]
            }
        }

    async def answer_feedback(self, *, feedback_id: str, text: str):
        return bool(feedback_id and text)


class _FakeQuestionsConnector:
    async def list_questions(self, *, skip=0, take=100, is_answered=False, order="dateDesc", nm_id=None):
        if skip > 0:
            return {"data": {"questions": []}}
        if is_answered:
            return {
                "data": {
                    "questions": [
                        {
                            "id": "q-2",
                            "text": "Есть ли гарантия?",
                            "createdDate": "2026-02-10T14:00:00Z",
                            "state": "wbRu",
                            "wasViewed": True,
                            "isWarned": False,
                            "userName": "Покупатель 2",
                            "answer": {"text": "Да, 12 месяцев.", "editable": True, "createDate": "2026-02-10T14:10:00Z"},
                            "productDetails": {
                                "nmId": 12345,
                                "supplierArticle": "A-1",
                                "productName": "Тестовый товар",
                            },
                        }
                    ]
                }
            }
        return {
            "data": {
                "questions": [
                    {
                        "id": "q-1",
                        "text": "Подойдет ли для ребенка 8 лет?",
                        "createdDate": "2026-02-10T11:00:00Z",
                        "state": "none",
                        "wasViewed": False,
                        "isWarned": False,
                        "answer": {"text": "", "editable": True, "createDate": None},
                        "productDetails": {
                            "nmId": 12345,
                            "supplierArticle": "A-1",
                            "productName": "Тестовый товар",
                        },
                    }
                ]
            }
        }

    async def patch_question(self, *, question_id: str, state: str, answer_text=None, was_viewed=None):
        return {"ok": bool(question_id and state and answer_text)}


class _FakeWBChatConnector:
    async def fetch_messages_as_chats(self, since_cursor=None):
        return {
            "chats": [
                {
                    "external_chat_id": "1:fake-chat-1",
                    "client_name": "Покупатель WB",
                    "client_id": "",
                    "status": "open",
                    "last_message_at": datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
                    "last_message_text": "Когда отправите заказ?",
                    "unread_count": 1,
                    "is_new_chat": True,
                    "good_card": {"nmID": 12345, "rid": "rid-1"},
                }
            ],
            "next_cursor": None,
            "total_messages": 1,
        }


class _DummyTask:
    def __init__(self):
        self.calls = []

    def delay(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return None


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def _cleanup_db_file():
    yield
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "integration-user@example.com",
            "password": "password123",
            "name": "Integration User",
            "marketplace": "wildberries",
        },
    )
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    connect = await client.post(
        "/api/auth/connect-marketplace",
        headers=headers,
        json={"api_key": "integration-test-token"},
    )
    assert connect.status_code == 200, connect.text
    return headers


def _patch_wb_connectors(monkeypatch):
    import app.api.interactions as interactions_api
    import app.services.interaction_ingest as interaction_ingest

    async def _fake_feedbacks_factory(*args, **kwargs):
        return _FakeFeedbacksConnector()

    async def _fake_questions_factory(*args, **kwargs):
        return _FakeQuestionsConnector()

    monkeypatch.setattr(interaction_ingest, "get_wb_feedbacks_connector_for_seller", _fake_feedbacks_factory)
    monkeypatch.setattr(interaction_ingest, "get_wb_questions_connector_for_seller", _fake_questions_factory)
    monkeypatch.setattr(interactions_api, "get_wb_feedbacks_connector_for_seller", _fake_feedbacks_factory)
    monkeypatch.setattr(interactions_api, "get_wb_questions_connector_for_seller", _fake_questions_factory)


@pytest.mark.asyncio
async def test_sync_reviews_questions_and_list(client: AsyncClient, auth_headers, monkeypatch):
    _patch_wb_connectors(monkeypatch)

    sync_reviews = await client.post("/api/interactions/sync/reviews", headers=auth_headers)
    assert sync_reviews.status_code == 200, sync_reviews.text
    assert sync_reviews.json()["created"] == 2

    sync_questions = await client.post("/api/interactions/sync/questions", headers=auth_headers)
    assert sync_questions.status_code == 200, sync_questions.text
    assert sync_questions.json()["created"] == 2

    listing = await client.get("/api/interactions", headers=auth_headers)
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["total"] == 4
    channels = {item["channel"] for item in payload["interactions"]}
    assert channels == {"review", "question"}
    review_id = next(item["id"] for item in payload["interactions"] if item["channel"] == "review")

    timeline = await client.get(f"/api/interactions/{review_id}/timeline", headers=auth_headers)
    assert timeline.status_code == 200, timeline.text
    timeline_payload = timeline.json()
    assert timeline_payload["thread_scope"] == "customer_order"
    assert {"review", "question"}.issubset(set(timeline_payload["channels_present"]))
    assert len(timeline_payload["steps"]) >= 2
    question_step = next(step for step in timeline_payload["steps"] if step["channel"] == "question")
    assert question_step["match_reason"] in {"order_id_exact", "nm_id_time_window", "article_time_window"}
    assert question_step["action_mode"] in {"assist_only", "auto_allowed"}
    assert question_step["wb_url"].startswith("https://seller.wildberries.ru/communication/")
    assert "is_current" in question_step

    async with AsyncSessionLocal() as db:
        questions_result = await db.execute(select(Interaction).where(Interaction.channel == "question"))
        questions = questions_result.scalars().all()
        assert len(questions) == 2
        assert any(q.priority in {"high", "urgent"} for q in questions)
        assert all(isinstance(q.extra_data, dict) for q in questions)
        assert any(q.extra_data.get("question_intent") is not None for q in questions)
        reviews_result = await db.execute(select(Interaction).where(Interaction.channel == "review"))
        reviews = reviews_result.scalars().all()
        assert len(reviews) == 2
        for review in reviews:
            assert review.occurred_at is not None
            assert isinstance(review.extra_data, dict)
        answered_review = next(item for item in reviews if item.external_id == "fb-2")
        assert answered_review.extra_data.get("last_reply_text") == "Спасибо за отзыв!"

        open_review = next(item for item in reviews if item.external_id == "fb-1")
        review_links = open_review.extra_data.get("link_candidates")
        assert isinstance(review_links, list)
        assert any(link.get("channel") == "question" for link in review_links)
        first_link = review_links[0]
        assert first_link.get("action_mode") in {"assist_only", "auto_allowed"}
        assert first_link.get("policy_reason") is not None

        questions_result = await db.execute(select(Interaction).where(Interaction.channel == "question"))
        questions = questions_result.scalars().all()
        assert len(questions) == 2
        for q in questions:
            assert q.occurred_at is not None
        answered_q = next(item for item in questions if item.external_id == "q-2")
        assert answered_q.extra_data.get("last_reply_text") == "Да, 12 месяцев."


@pytest.mark.asyncio
async def test_me_converts_stale_syncing_to_error(client: AsyncClient):
    reg = await client.post(
        "/api/auth/register",
        json={
            "email": "stale-sync@example.com",
            "password": "password123",
            "name": "Stale Sync User",
            "marketplace": "wildberries",
        },
    )
    assert reg.status_code in (200, 201), reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Seller).where(Seller.email == "stale-sync@example.com"))
        seller = result.scalar_one()
        seller.sync_status = "syncing"
        seller.sync_error = None
        seller.updated_at = datetime.now(timezone.utc) - timedelta(minutes=6)
        await db.commit()

    me = await client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200, me.text
    payload = me.json()
    assert payload["sync_status"] == "error"
    assert payload["sync_error"]


@pytest.mark.asyncio
async def test_draft_reply_and_quality_metrics(client: AsyncClient, auth_headers, monkeypatch):
    _patch_wb_connectors(monkeypatch)

    # Seed a review interaction via sync endpoint.
    sync_reviews = await client.post("/api/interactions/sync/reviews", headers=auth_headers)
    assert sync_reviews.status_code == 200, sync_reviews.text

    list_reviews = await client.get("/api/interactions", params={"channel": "review"}, headers=auth_headers)
    assert list_reviews.status_code == 200, list_reviews.text
    interaction_id = list_reviews.json()["interactions"][0]["id"]

    # Force deterministic draft response for this integration test.
    import app.api.interactions as interactions_api

    async def _fake_generate_interaction_draft(*, db, interaction):
        return DraftResult(
            text="Спасибо за отзыв! Уже проверяем ситуацию.",
            intent="complaint",
            sentiment="negative",
            sla_priority="high",
            recommendation_reason="Integration test draft",
            source="llm",
        )

    monkeypatch.setattr(interactions_api, "generate_interaction_draft", _fake_generate_interaction_draft)

    draft = await client.post(
        f"/api/interactions/{interaction_id}/ai-draft",
        headers=auth_headers,
        json={"force_regenerate": True},
    )
    assert draft.status_code == 200, draft.text
    draft_text = draft.json()["draft_text"]

    reply = await client.post(
        f"/api/interactions/{interaction_id}/reply",
        headers=auth_headers,
        json={"text": draft_text},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["interaction"]["status"] == "responded"

    metrics = await client.get("/api/interactions/metrics/quality", headers=auth_headers)
    assert metrics.status_code == 200, metrics.text
    totals = metrics.json()["totals"]
    assert totals["replies_total"] == 1
    assert totals["draft_accepted"] == 1
    assert totals["draft_edited"] == 0
    assert totals["reply_manual"] == 0

    history = await client.get("/api/interactions/metrics/quality-history", headers=auth_headers)
    assert history.status_code == 200, history.text
    series = history.json()["series"]
    assert isinstance(series, list)
    assert len(series) >= 1
    assert any(point["replies_total"] >= 1 for point in series)

    ops_alerts = await client.get("/api/interactions/metrics/ops-alerts", headers=auth_headers)
    assert ops_alerts.status_code == 200, ops_alerts.text
    ops_payload = ops_alerts.json()
    assert "question_sla" in ops_payload
    assert "quality_regression" in ops_payload
    assert "alerts" in ops_payload

    async with AsyncSessionLocal() as db:
        seller_result = await db.execute(
            select(Seller).where(Seller.email == "integration-user@example.com")
        )
        seller = seller_result.scalar_one()
        seller.sync_status = "success"
        seller.last_sync_at = datetime.now(timezone.utc)
        seller.sync_error = None
        await db.commit()

    pilot_readiness = await client.get("/api/interactions/metrics/pilot-readiness", headers=auth_headers)
    assert pilot_readiness.status_code == 200, pilot_readiness.text
    readiness_payload = pilot_readiness.json()
    assert "go_no_go" in readiness_payload
    assert "summary" in readiness_payload
    assert "checks" in readiness_payload
    codes = {item["code"] for item in readiness_payload["checks"]}
    assert {"sync_freshness", "channel_coverage", "question_sla_overdue"}.issubset(codes)


@pytest.mark.asyncio
async def test_sync_chats_creates_chat_interaction(client: AsyncClient, auth_headers):
    me = await client.get("/api/auth/me", headers=auth_headers)
    assert me.status_code == 200, me.text
    seller_id = me.json()["id"]

    async with AsyncSessionLocal() as db:
        db.add(
            Chat(
                seller_id=seller_id,
                marketplace="wildberries",
                marketplace_chat_id="chat-1",
                customer_name="Клиент",
                status="open",
                unread_count=1,
                sla_priority="high",
                chat_status="waiting",
                last_message_preview="Есть вопрос по доставке",
                product_name="Тестовый товар",
                product_article="A-1",
                last_message_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()

    sync_chats = await client.post("/api/interactions/sync/chats", headers=auth_headers)
    assert sync_chats.status_code == 200, sync_chats.text
    assert sync_chats.json()["created"] == 1

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Interaction).where(Interaction.channel == "chat"))
        chat_interaction = result.scalar_one_or_none()

    assert chat_interaction is not None
    assert chat_interaction.needs_response is True
    assert chat_interaction.external_id == "chat-1"


@pytest.mark.asyncio
async def test_sync_chats_direct_wb_fetch_when_local_empty(client: AsyncClient, auth_headers, monkeypatch):
    import app.services.interaction_ingest as interaction_ingest

    async def _fake_wb_factory(*args, **kwargs):
        return _FakeWBChatConnector()

    monkeypatch.setattr(interaction_ingest, "get_wb_connector_for_seller", _fake_wb_factory)

    sync_chats = await client.post(
        "/api/interactions/sync/chats",
        params={"direct_wb_fetch": "true"},
        headers=auth_headers,
    )
    assert sync_chats.status_code == 200, sync_chats.text
    assert sync_chats.json()["fetched"] == 1
    assert sync_chats.json()["created"] == 1

    listing = await client.get("/api/interactions", params={"channel": "chat"}, headers=auth_headers)
    assert listing.status_code == 200, listing.text
    payload = listing.json()
    assert payload["total"] == 1
    item = payload["interactions"][0]
    assert item["external_id"] == "1:fake-chat-1"
    assert item["nm_id"] == "12345"
    assert item["order_id"] == "rid-1"
    assert item["needs_response"] is True


@pytest.mark.asyncio
async def test_manual_sync_now_queues_background_tasks(client: AsyncClient, auth_headers, monkeypatch):
    import app.tasks.sync as sync_tasks

    chats_task = _DummyTask()
    interactions_task = _DummyTask()
    monkeypatch.setattr(sync_tasks, "sync_seller_chats", chats_task)
    monkeypatch.setattr(sync_tasks, "sync_seller_interactions", interactions_task)

    response = await client.post(
        "/api/auth/sync-now",
        headers=auth_headers,
        json={"include_interactions": True},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sync_status"] == "syncing"
    assert "chats" in payload["queued_scopes"]
    assert "interactions" in payload["queued_scopes"]
    assert len(chats_task.calls) == 1
    assert len(interactions_task.calls) == 1
