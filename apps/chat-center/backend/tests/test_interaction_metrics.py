"""Tests for interaction quality metrics aggregation."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure app settings can be initialized for imported modules.
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_interaction_metrics.db")

from app.database import Base
from app.models.interaction import Interaction
from app.models.seller import Seller
from app.services.interaction_metrics import (
    get_ops_alerts,
    get_pilot_readiness,
    get_quality_history,
    get_quality_metrics,
    record_draft_event,
    record_reply_events,
)

TEST_DB_PATH = Path("./test_interaction_metrics.db")


@pytest.mark.asyncio
async def test_quality_metrics_accept_and_manual_paths():
    db_url = "sqlite+aiosqlite:///./test_interaction_metrics.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        seller = Seller(
            name="Metrics Test Seller",
            email="metrics-test@example.com",
            password_hash="x",
            marketplace="wildberries",
            is_active=True,
        )
        db.add(seller)
        await db.flush()

        accepted_interaction = Interaction(
            seller_id=seller.id,
            marketplace="wildberries",
            channel="review",
            external_id="rev-1",
            text="Отличный товар",
            status="open",
            priority="normal",
            needs_response=True,
            source="wb_api",
            extra_data={"last_ai_draft": {"text": "Спасибо за отзыв!", "source": "llm"}},
        )
        manual_interaction = Interaction(
            seller_id=seller.id,
            marketplace="wildberries",
            channel="question",
            external_id="q-1",
            text="Какая длина?",
            status="open",
            priority="high",
            needs_response=True,
            source="wb_api",
        )
        overdue_question = Interaction(
            seller_id=seller.id,
            marketplace="wildberries",
            channel="question",
            external_id="q-2",
            text="Когда будет в наличии?",
            status="open",
            priority="high",
            needs_response=True,
            source="wb_api",
            extra_data={
                "sla_due_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            },
        )
        db.add_all([accepted_interaction, manual_interaction, overdue_question])
        await db.flush()

        record_draft_event(
            db=db,
            interaction=accepted_interaction,
            source="llm",
            force_regenerate=False,
            cached=False,
        )
        record_reply_events(
            db=db,
            interaction=accepted_interaction,
            reply_text="Спасибо за отзыв!",
        )
        record_reply_events(
            db=db,
            interaction=manual_interaction,
            reply_text="Здравствуйте! Длина 120 см.",
        )

        accepted_interaction.status = "responded"
        accepted_interaction.needs_response = False
        manual_interaction.status = "responded"
        manual_interaction.needs_response = False

        await db.commit()

        metrics = await get_quality_metrics(
            db=db,
            seller_id=seller.id,
            days=30,
        )

        assert metrics["totals"]["replies_total"] == 2
        assert metrics["totals"]["draft_generated"] == 1
        assert metrics["totals"]["draft_accepted"] == 1
        assert metrics["totals"]["reply_manual"] == 1
        assert metrics["totals"]["accept_rate"] == 0.5
        assert metrics["totals"]["manual_rate"] == 0.5
        assert metrics["pipeline"]["interactions_total"] == 3
        assert metrics["pipeline"]["responded_total"] == 2

        history = await get_quality_history(
            db=db,
            seller_id=seller.id,
            days=7,
        )
        assert history["period_days"] == 7
        assert len(history["series"]) == 7
        assert any(point["replies_total"] == 2 for point in history["series"])

        ops_alerts = await get_ops_alerts(
            db=db,
            seller_id=seller.id,
        )
        assert ops_alerts["question_sla"]["overdue_total"] >= 1
        alert_codes = {item["code"] for item in ops_alerts["alerts"]}
        assert "sla_overdue_questions" in alert_codes

        readiness = await get_pilot_readiness(
            db=db,
            seller_id=seller.id,
            sync_status="success",
            last_sync_at=datetime.now(timezone.utc),
            sync_error=None,
        )
        assert readiness["decision"] in {"go", "no-go"}
        assert readiness["summary"]["total_checks"] >= 6
        assert any(item["code"] == "channel_coverage" for item in readiness["checks"])
        assert readiness["go_no_go"] is False
        assert "question_sla_overdue" in readiness["summary"]["blockers"]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_pilot_readiness_reply_activity_uses_source_baseline_when_no_reply_events():
    db_url = "sqlite+aiosqlite:///./test_interaction_metrics.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        seller = Seller(
            name="Metrics Baseline Seller",
            email="metrics-baseline@example.com",
            password_hash="x",
            marketplace="wildberries",
            is_active=True,
        )
        db.add(seller)
        await db.flush()

        now = datetime.now(timezone.utc)
        db.add_all(
            [
                Interaction(
                    seller_id=seller.id,
                    marketplace="wildberries",
                    channel="review",
                    external_id="rev-baseline-1",
                    text="Отзыв уже отвечен",
                    status="responded",
                    priority="low",
                    needs_response=False,
                    source="wb_api",
                    occurred_at=now - timedelta(days=2),
                ),
                Interaction(
                    seller_id=seller.id,
                    marketplace="wildberries",
                    channel="question",
                    external_id="q-baseline-1",
                    text="Вопрос уже отвечен",
                    status="responded",
                    priority="low",
                    needs_response=False,
                    source="wb_api",
                    occurred_at=now - timedelta(days=1),
                ),
            ]
        )
        await db.commit()

        readiness = await get_pilot_readiness(
            db=db,
            seller_id=seller.id,
            sync_status="success",
            last_sync_at=now,
            sync_error=None,
        )

        checks_by_code = {item["code"]: item for item in readiness["checks"]}
        reply_activity = checks_by_code["reply_activity"]
        assert reply_activity["status"] == "pass"
        assert "source есть" in reply_activity["details"]
        assert readiness["go_no_go"] is True

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
