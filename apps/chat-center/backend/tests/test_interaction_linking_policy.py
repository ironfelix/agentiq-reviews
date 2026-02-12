"""Tests for link action guardrails (deterministic vs probabilistic)."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.interaction import Interaction
from app.models.seller import Seller
from app.services.interaction_linking import (
    evaluate_link_action_policy,
    update_link_candidates_for_interaction,
)

TEST_DB_PATH = Path("./test_interaction_linking_policy.db")


def test_evaluate_link_action_policy_rules():
    deterministic_ok = evaluate_link_action_policy(link_type="deterministic", confidence=0.9)
    assert deterministic_ok["action_mode"] == "auto_allowed"
    assert deterministic_ok["auto_action_allowed"] is True

    deterministic_low = evaluate_link_action_policy(link_type="deterministic", confidence=0.7)
    assert deterministic_low["action_mode"] == "assist_only"
    assert deterministic_low["auto_action_allowed"] is False

    probabilistic = evaluate_link_action_policy(link_type="probabilistic", confidence=0.99)
    assert probabilistic["action_mode"] == "assist_only"
    assert probabilistic["auto_action_allowed"] is False


@pytest.mark.asyncio
async def test_probabilistic_links_are_assist_only():
    db_url = "sqlite+aiosqlite:///./test_interaction_linking_policy.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        seller = Seller(
            name="Linking Test Seller",
            email="linking-policy@example.com",
            password_hash="x",
            marketplace="wildberries",
            is_active=True,
        )
        db.add(seller)
        await db.flush()

        now = datetime.now(timezone.utc)
        review = Interaction(
            seller_id=seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="rev-policy-1",
            customer_id=None,
            order_id=None,
            nm_id="12345",
            product_article="A-1",
            text="Товар приехал со сколом на корпусе",
            status="open",
            priority="high",
            needs_response=True,
            source="wb_api",
            occurred_at=now - timedelta(hours=2),
            extra_data={"user_name": "Иван П."},
        )
        question = Interaction(
            seller_id=seller.id,
            marketplace="wildberries",
            channel="question",
            external_id="q-policy-1",
            customer_id=None,
            order_id=None,
            nm_id="12345",
            product_article="A-1",
            text="Есть скол на корпусе, как оформить замену?",
            status="open",
            priority="high",
            needs_response=True,
            source="wb_api",
            occurred_at=now - timedelta(hours=1),
            extra_data={"user_name": "Иван П."},
        )
        db.add_all([review, question])
        await db.flush()

        candidates = await update_link_candidates_for_interaction(db, review, max_links=5)
        assert len(candidates) >= 1
        top = candidates[0]
        assert top["link_type"] == "probabilistic"
        assert top["action_mode"] == "assist_only"
        assert top["auto_action_allowed"] is False

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

