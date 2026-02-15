"""Tests for incremental watermark-based sync for reviews and questions."""

import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_incremental_sync.db")

from app.database import Base
from app.services.interaction_ingest import (
    IngestStats,
    _WATERMARK_OVERLAP_SECONDS,
    ingest_wb_reviews_to_interactions,
    ingest_wb_questions_to_interactions,
)
from app.tasks.sync import (
    _load_watermark,
    _save_watermark,
    _watermark_key,
)

TEST_DB_PATH = Path("./test_incremental_sync.db")


def _dt(iso: str) -> datetime:
    """Parse an ISO string to UTC datetime."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def _make_feedback(
    *,
    fb_id: str,
    created_date: str,
    rating: int = 5,
    text: str = "Good product",
    answer_text: str = "",
) -> dict:
    """Build a minimal WB feedback payload."""
    fb = {
        "id": fb_id,
        "createdDate": created_date,
        "productValuation": rating,
        "text": text,
        "answerText": answer_text,
        "productDetails": {
            "productName": "Test Product",
            "nmId": 12345,
            "supplierArticle": "ART-001",
        },
        "userName": "TestUser",
        "answerState": "none",
        "wasViewed": True,
        "pros": "",
        "cons": "",
    }
    return fb


def _make_question(
    *,
    q_id: str,
    created_date: str,
    text: str = "What size should I pick?",
    answer_text: str = "",
) -> dict:
    """Build a minimal WB question payload."""
    answer = None
    if answer_text:
        answer = {"text": answer_text, "createDate": created_date, "editable": True}
    q = {
        "id": q_id,
        "createdDate": created_date,
        "text": text,
        "answer": answer,
        "productDetails": {
            "productName": "Test Product",
            "nmId": 12345,
            "supplierArticle": "ART-001",
        },
        "userName": "Buyer",
        "state": "wbRu",
        "wasViewed": False,
        "isWarned": False,
    }
    return q


# ─── Watermark persistence tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_watermark_roundtrip():
    """Watermark can be saved and loaded per (seller_id, channel)."""
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        # Initially no watermark.
        wm = await _load_watermark(db, seller_id=1, channel="review")
        assert wm is None

        # Save and load.
        await _save_watermark(
            db, seller_id=1, channel="review",
            watermark_iso="2026-02-14T10:00:00+00:00",
        )
        await db.commit()

        wm = await _load_watermark(db, seller_id=1, channel="review")
        assert wm is not None
        assert wm.tzinfo is not None  # Must be timezone-aware
        assert wm.year == 2026
        assert wm.month == 2
        assert wm.day == 14
        assert wm.hour == 10

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_watermark_namespace_isolation():
    """Watermarks for different channels do not interfere."""
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        await _save_watermark(
            db, seller_id=1, channel="review",
            watermark_iso="2026-02-14T08:00:00+00:00",
        )
        await _save_watermark(
            db, seller_id=1, channel="question",
            watermark_iso="2026-02-14T09:00:00+00:00",
        )
        await _save_watermark(
            db, seller_id=2, channel="review",
            watermark_iso="2026-02-14T07:00:00+00:00",
        )
        await db.commit()

        review_wm_1 = await _load_watermark(db, seller_id=1, channel="review")
        question_wm_1 = await _load_watermark(db, seller_id=1, channel="question")
        review_wm_2 = await _load_watermark(db, seller_id=2, channel="review")
        question_wm_2 = await _load_watermark(db, seller_id=2, channel="question")

        assert review_wm_1.hour == 8
        assert question_wm_1.hour == 9
        assert review_wm_2.hour == 7
        assert question_wm_2 is None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_watermark_update_overwrites():
    """Saving a new watermark overwrites the old one."""
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        await _save_watermark(
            db, seller_id=1, channel="review",
            watermark_iso="2026-02-14T08:00:00+00:00",
        )
        await db.commit()

        await _save_watermark(
            db, seller_id=1, channel="review",
            watermark_iso="2026-02-14T12:00:00+00:00",
        )
        await db.commit()

        wm = await _load_watermark(db, seller_id=1, channel="review")
        assert wm.hour == 12

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


def test_watermark_key_format():
    """Key follows sync_watermark:{channel}:{seller_id} pattern."""
    key = _watermark_key(seller_id=42, channel="review")
    assert key == "sync_watermark:review:42"

    key = _watermark_key(seller_id=7, channel="question")
    assert key == "sync_watermark:question:7"


@pytest.mark.asyncio
async def test_save_watermark_none_is_noop():
    """Saving None watermark does not write anything."""
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        await _save_watermark(db, seller_id=1, channel="review", watermark_iso=None)
        await _save_watermark(db, seller_id=1, channel="review", watermark_iso="")
        await _save_watermark(db, seller_id=1, channel="review", watermark_iso="  ")
        await db.commit()

        wm = await _load_watermark(db, seller_id=1, channel="review")
        assert wm is None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


# ─── IngestStats tests ────────────────────────────────────────────────────────

def test_ingest_stats_as_dict():
    """as_dict() returns only the 4 basic counters."""
    stats = IngestStats(
        fetched=10,
        created=5,
        updated=3,
        skipped=2,
        stopped_at_watermark=True,
        new_watermark="2026-02-14T10:00:00+00:00",
    )
    d = stats.as_dict()
    assert d == {"fetched": 10, "created": 5, "updated": 3, "skipped": 2}
    # Watermark fields are NOT in the dict (backward compat).
    assert "stopped_at_watermark" not in d
    assert "new_watermark" not in d


def test_ingest_stats_default():
    """Default IngestStats has zero counters and no watermark."""
    stats = IngestStats()
    assert stats.fetched == 0
    assert stats.stopped_at_watermark is False
    assert stats.new_watermark is None


# ─── Incremental review ingestion tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_review_ingest_stops_at_watermark():
    """
    When since_watermark is set, ingestion stops pagination when it hits
    records older than the watermark.
    """
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Prepare mock feedbacks: 3 records, ordered dateDesc.
    # Record 1: Feb 14 12:00 (newest)
    # Record 2: Feb 14 10:00
    # Record 3: Feb 13 08:00 (oldest -- should trigger watermark stop)
    feedbacks_page = [
        _make_feedback(fb_id="fb-1", created_date="2026-02-14T12:00:00+00:00"),
        _make_feedback(fb_id="fb-2", created_date="2026-02-14T10:00:00+00:00"),
        _make_feedback(fb_id="fb-3", created_date="2026-02-13T08:00:00+00:00"),
    ]

    mock_connector = AsyncMock()
    mock_connector.list_feedbacks.return_value = {
        "data": {"feedbacks": feedbacks_page}
    }

    # Watermark: Feb 14 09:00 -- record fb-3 (Feb 13 08:00) is older than
    # effective watermark (09:00 - 2s).
    watermark = _dt("2026-02-14T09:00:00+00:00")

    mock_get_connector = AsyncMock(return_value=mock_connector)

    async with session_factory() as db:
        with patch(
            "app.services.interaction_ingest.get_wb_feedbacks_connector_for_seller",
            mock_get_connector,
        ), patch(
            "app.services.interaction_ingest.get_rate_limiter",
        ) as mock_rl, patch(
            "app.services.interaction_ingest.refresh_link_candidates_for_interactions",
            new_callable=AsyncMock,
        ):
            mock_rl.return_value.acquire = AsyncMock()
            result = await ingest_wb_reviews_to_interactions(
                db=db,
                seller_id=1,
                marketplace="wildberries",
                max_items=300,
                page_size=100,
                since_watermark=watermark,
            )

        assert isinstance(result, IngestStats)
        # All 3 records should be processed (overlap zone includes fb-3).
        assert result.fetched == 3
        assert result.created == 3
        assert result.stopped_at_watermark is True
        # New watermark should be the newest record.
        assert result.new_watermark is not None
        assert "2026-02-14T12:00:00" in result.new_watermark

        # Only 1 API call should have been made (stopped after first page).
        assert mock_connector.list_feedbacks.call_count == 1

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_review_ingest_full_sync_when_no_watermark():
    """
    When since_watermark is None, ingestion paginates until all records
    are fetched (full sync behavior, backward compatible).
    """
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    feedbacks = [
        _make_feedback(fb_id="fb-1", created_date="2026-02-14T12:00:00+00:00"),
        _make_feedback(fb_id="fb-2", created_date="2026-01-01T08:00:00+00:00"),
    ]

    mock_connector = AsyncMock()
    mock_connector.list_feedbacks.return_value = {
        "data": {"feedbacks": feedbacks}
    }
    mock_get_connector = AsyncMock(return_value=mock_connector)

    async with session_factory() as db:
        with patch(
            "app.services.interaction_ingest.get_wb_feedbacks_connector_for_seller",
            mock_get_connector,
        ), patch(
            "app.services.interaction_ingest.get_rate_limiter",
        ) as mock_rl, patch(
            "app.services.interaction_ingest.refresh_link_candidates_for_interactions",
            new_callable=AsyncMock,
        ):
            mock_rl.return_value.acquire = AsyncMock()
            result = await ingest_wb_reviews_to_interactions(
                db=db,
                seller_id=1,
                marketplace="wildberries",
                max_items=300,
                page_size=100,
                since_watermark=None,  # Full sync
            )

        assert isinstance(result, IngestStats)
        # Full sync iterates answer_states=[False, True], fetching the same 2
        # feedbacks in each pass (stats.fetched counts raw API results before
        # dedup), so fetched=4.  Dedup via seen_ids means only 2 are created.
        assert result.fetched == 4
        assert result.created == 2
        assert result.stopped_at_watermark is False
        assert result.new_watermark is not None

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_question_ingest_stops_at_watermark():
    """
    When since_watermark is set, question ingestion stops at watermark.
    """
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    questions_page = [
        _make_question(q_id="q-1", created_date="2026-02-14T14:00:00+00:00"),
        _make_question(q_id="q-2", created_date="2026-02-14T06:00:00+00:00"),
    ]

    mock_connector = AsyncMock()
    mock_connector.list_questions.return_value = {
        "data": {"questions": questions_page}
    }
    mock_get_connector = AsyncMock(return_value=mock_connector)

    watermark = _dt("2026-02-14T10:00:00+00:00")

    async with session_factory() as db:
        with patch(
            "app.services.interaction_ingest.get_wb_questions_connector_for_seller",
            mock_get_connector,
        ), patch(
            "app.services.interaction_ingest.get_rate_limiter",
        ) as mock_rl, patch(
            "app.services.interaction_ingest.refresh_link_candidates_for_interactions",
            new_callable=AsyncMock,
        ), patch(
            "app.services.interaction_ingest.get_seller_setting",
            new_callable=AsyncMock,
            return_value=None,
        ):
            mock_rl.return_value.acquire = AsyncMock()
            result = await ingest_wb_questions_to_interactions(
                db=db,
                seller_id=1,
                marketplace="wildberries",
                max_items=300,
                page_size=100,
                since_watermark=watermark,
            )

        assert isinstance(result, IngestStats)
        assert result.fetched == 2
        assert result.created == 2
        assert result.stopped_at_watermark is True
        assert result.new_watermark is not None
        assert "2026-02-14T14:00:00" in result.new_watermark

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_watermark_overlap_buffer():
    """
    Records within the overlap buffer (WATERMARK_OVERLAP_SECONDS) are still
    processed even though they are near the watermark boundary.
    """
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Watermark at 10:00:00. Record at 09:59:59 (1 second before watermark).
    # Effective watermark = 10:00:00 - 2s = 09:59:58.
    # Record at 09:59:59 > 09:59:58 so it should NOT trigger watermark stop.
    feedbacks_page = [
        _make_feedback(fb_id="fb-1", created_date="2026-02-14T10:00:01+00:00"),
        _make_feedback(fb_id="fb-2", created_date="2026-02-14T09:59:59+00:00"),
    ]

    mock_connector = AsyncMock()
    mock_connector.list_feedbacks.return_value = {
        "data": {"feedbacks": feedbacks_page}
    }
    mock_get_connector = AsyncMock(return_value=mock_connector)

    watermark = _dt("2026-02-14T10:00:00+00:00")

    async with session_factory() as db:
        with patch(
            "app.services.interaction_ingest.get_wb_feedbacks_connector_for_seller",
            mock_get_connector,
        ), patch(
            "app.services.interaction_ingest.get_rate_limiter",
        ) as mock_rl, patch(
            "app.services.interaction_ingest.refresh_link_candidates_for_interactions",
            new_callable=AsyncMock,
        ):
            mock_rl.return_value.acquire = AsyncMock()
            result = await ingest_wb_reviews_to_interactions(
                db=db,
                seller_id=1,
                marketplace="wildberries",
                max_items=300,
                page_size=100,
                since_watermark=watermark,
            )

        # Both records are within overlap zone -- should NOT stop.
        assert result.stopped_at_watermark is False
        assert result.created == 2

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.mark.asyncio
async def test_new_watermark_tracks_max_occurred_at():
    """
    The new_watermark in stats reflects the max occurred_at across all
    fetched records, not the first or last.
    """
    db_url = "sqlite+aiosqlite:///./test_incremental_sync.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Records NOT strictly ordered (edge case: API returns mixed order).
    feedbacks_page = [
        _make_feedback(fb_id="fb-1", created_date="2026-02-14T09:00:00+00:00"),
        _make_feedback(fb_id="fb-2", created_date="2026-02-14T15:00:00+00:00"),  # newest
        _make_feedback(fb_id="fb-3", created_date="2026-02-14T11:00:00+00:00"),
    ]

    mock_connector = AsyncMock()
    mock_connector.list_feedbacks.return_value = {
        "data": {"feedbacks": feedbacks_page}
    }
    mock_get_connector = AsyncMock(return_value=mock_connector)

    async with session_factory() as db:
        with patch(
            "app.services.interaction_ingest.get_wb_feedbacks_connector_for_seller",
            mock_get_connector,
        ), patch(
            "app.services.interaction_ingest.get_rate_limiter",
        ) as mock_rl, patch(
            "app.services.interaction_ingest.refresh_link_candidates_for_interactions",
            new_callable=AsyncMock,
        ):
            mock_rl.return_value.acquire = AsyncMock()
            result = await ingest_wb_reviews_to_interactions(
                db=db,
                seller_id=1,
                marketplace="wildberries",
                max_items=300,
                page_size=100,
                since_watermark=None,
            )

        # new_watermark should be the max (15:00).
        assert result.new_watermark is not None
        assert "15:00:00" in result.new_watermark

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
