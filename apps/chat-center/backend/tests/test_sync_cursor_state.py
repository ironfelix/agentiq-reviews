"""Tests for incremental sync cursor persistence."""

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_sync_cursor_state.db")

from app.database import Base
from app.tasks.sync import _load_sync_cursor, _save_sync_cursor

TEST_DB_PATH = Path("./test_sync_cursor_state.db")


@pytest.mark.asyncio
async def test_sync_cursor_roundtrip_and_namespace():
    db_url = "sqlite+aiosqlite:///./test_sync_cursor_state.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        assert await _load_sync_cursor(db, seller_id=7, marketplace="wildberries") is None

        await _save_sync_cursor(db, seller_id=7, marketplace="wildberries", cursor="101")
        await db.commit()
        assert await _load_sync_cursor(db, seller_id=7, marketplace="wildberries") == "101"

        await _save_sync_cursor(db, seller_id=7, marketplace="wildberries", cursor="205")
        await _save_sync_cursor(db, seller_id=7, marketplace="ozon", cursor="ozon-msg-42")
        await db.commit()

        assert await _load_sync_cursor(db, seller_id=7, marketplace="wildberries") == "205"
        assert await _load_sync_cursor(db, seller_id=7, marketplace="ozon") == "ozon-msg-42"

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
