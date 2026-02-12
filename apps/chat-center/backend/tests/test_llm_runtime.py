"""Tests for DB-backed runtime LLM settings."""

import os
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_llm_runtime.db")

from app.database import Base
from app.services.llm_runtime import get_llm_runtime_config, set_llm_runtime_config

TEST_DB_PATH = Path("./test_llm_runtime.db")


@pytest.mark.asyncio
async def test_llm_runtime_defaults_and_update():
    db_url = "sqlite+aiosqlite:///./test_llm_runtime.db"
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        defaults = await get_llm_runtime_config(db)
        assert defaults.provider == "deepseek"
        assert defaults.model_name == "deepseek-chat"
        assert defaults.enabled is True

        await set_llm_runtime_config(
            db,
            provider="deepseek",
            model_name="deepseek-chat",
            enabled=False,
        )
        cfg = await get_llm_runtime_config(db)
        assert cfg.provider == "deepseek"
        assert cfg.model_name == "deepseek-chat"
        assert cfg.enabled is False

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
