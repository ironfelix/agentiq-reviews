"""CJM smoke: connect marketplace must not leave infinite 'syncing' when queue is unavailable."""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient

# Isolated sqlite DB for this test module.
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_cjm_connect_queue_failure.db"

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_connect_marketplace_queue_failure_sets_error(monkeypatch):
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        reg = await client.post(
            "/api/auth/register",
            json={
                "email": "cjm-queuefail@example.com",
                "password": "password123",
                "name": "CJM QueueFail",
                "marketplace": "wildberries",
            },
        )
        assert reg.status_code in (200, 201), reg.text
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Simulate Celery broker down / queue failure at the delay() call.
        import app.tasks.sync as sync_tasks

        def _raise_delay(*args, **kwargs):
            raise RuntimeError("broker down")

        monkeypatch.setattr(sync_tasks.sync_seller_chats, "delay", _raise_delay, raising=True)

        connect = await client.post(
            "/api/auth/connect-marketplace",
            headers=headers,
            json={"api_key": "integration-test-token"},
        )
        assert connect.status_code == 200, connect.text
        payload = connect.json()
        assert payload["has_api_credentials"] is True
        assert payload["sync_status"] == "error"
        assert payload["sync_error"]

