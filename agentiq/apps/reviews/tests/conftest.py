"""Pytest configuration and shared fixtures."""
import os
import pytest
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient
from fastapi import FastAPI

# Set test environment variables before importing app
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use separate DB for tests
os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token_123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
os.environ["SECRET_KEY"] = "test_secret_key_do_not_use_in_production"
os.environ["WBCON_TOKEN"] = "test_wbcon_token"
os.environ["DEEPSEEK_API_KEY"] = "test_deepseek_key"
os.environ["USE_LLM"] = "0"  # Disable LLM by default in tests
os.environ["FRONTEND_URL"] = "http://localhost:8000"
os.environ["TELEGRAM_BOT_USERNAME"] = "test_bot"

from backend.main import app
from backend.database import Base, get_session, User, Task, Report, InviteCode


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def test_client(test_db_session) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client with database session override."""

    async def override_get_session():
        yield test_db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(test_db_session) -> User:
    """Create test user with invite code."""
    # Create invite code
    invite_code = InviteCode(
        code="TEST-INVITE-2026",
        max_uses=100,
        used_count=1,
        created_by="pytest",
    )
    test_db_session.add(invite_code)
    await test_db_session.commit()
    await test_db_session.refresh(invite_code)

    # Create user
    user = User(
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User",
        auth_date=int(datetime.utcnow().timestamp()),
        invite_code_id=invite_code.id,
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_without_invite(test_db_session) -> User:
    """Create test user without invite code (for invite flow tests)."""
    user = User(
        telegram_id=987654321,
        username="new_user",
        first_name="New",
        last_name="User",
        auth_date=int(datetime.utcnow().timestamp()),
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest.fixture
async def test_task(test_db_session, test_user) -> Task:
    """Create test task."""
    task = Task(
        user_id=test_user.id,
        article_id=282955222,
        status="pending",
        progress=0,
    )
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(task)
    return task


@pytest.fixture
async def completed_task(test_db_session, test_user) -> Task:
    """Create completed test task with report."""
    task = Task(
        user_id=test_user.id,
        article_id=282955222,
        status="completed",
        progress=100,
        wbcon_task_id="01-test-task-id",
        completed_at=datetime.utcnow(),
    )
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(task)

    # Create report
    report_data = {
        "header": {
            "product_name": "Test Product",
            "category": "flashlight",
            "rating": 4.5,
            "feedback_count": 100,
        },
        "signal": {
            "scores": [{"label": "красный", "rating": 3.2, "count": 15}]
        },
        "communication": {
            "quality_score": 7,
            "verdict": "Test verdict",
        }
    }

    report = Report(
        task_id=task.id,
        article_id=task.article_id,
        category="flashlight",
        rating=4.5,
        feedback_count=100,
        target_variant="красный",
        data=str(report_data).replace("'", '"'),
    )
    test_db_session.add(report)
    await test_db_session.commit()
    await test_db_session.refresh(report)

    return task


@pytest.fixture
def sample_feedbacks():
    """Sample feedback data for testing."""
    return [
        {
            "fb_id": "1",
            "valuation": 1,
            "fb_text": "Фонарик очень тусклый, батарея быстро садится",
            "fb_created_at": "2026-01-15T10:30:00",
            "answer_text": "Спасибо за отзыв!",
            "answer_created_at": "2026-01-15T15:20:00",
            "color": "красный",
            "size": None,
        },
        {
            "fb_id": "2",
            "valuation": 5,
            "fb_text": "Отличный фонарик, все работает!",
            "fb_created_at": "2026-01-20T14:00:00",
            "answer_text": "Благодарим за отзыв!",
            "answer_created_at": "2026-01-20T16:00:00",
            "color": "белый",
            "size": None,
        },
        {
            "fb_id": "3",
            "valuation": 2,
            "fb_text": "Не соответствует описанию, яркость слабая",
            "fb_created_at": "2026-01-25T09:00:00",
            "answer_text": None,
            "answer_created_at": None,
            "color": "красный",
            "size": None,
        },
    ]


@pytest.fixture
def sample_wbcon_response():
    """Sample WBCON API response for testing."""
    return [
        {
            "feedback_count": 100,
            "rating": 4.3,
            "feedbacks": [
                {
                    "fb_id": "12345",
                    "valuation": 5,
                    "fb_text": "Отличный товар!",
                    "fb_created_at": "2026-01-15T10:30:00",
                    "answer_text": "Спасибо!",
                    "answer_created_at": "2026-01-15T15:20:00",
                    "color": "красный",
                    "size": None,
                },
            ],
        }
    ]


@pytest.fixture
def sample_wb_card():
    """Sample WB card API response."""
    return {
        "imt_name": "Тестовый фонарик LED",
        "description": "Яркий светодиодный фонарик",
        "subj_name": "Фонари",
        "options": "Цвет: красный; Материал: металл",
        "price": 1299.0,
    }


@pytest.fixture
def auth_headers(test_user):
    """Generate authentication headers with session token."""
    from backend.auth import create_session_token
    token = create_session_token(test_user.telegram_id)
    return {"Cookie": f"session_token={token}"}


@pytest.fixture
def mock_telegram_auth_data():
    """Mock Telegram auth callback data."""
    import hashlib
    import hmac
    from datetime import datetime, timezone

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    auth_date = int(datetime.now(timezone.utc).timestamp())

    data = {
        "id": "123456789",
        "first_name": "Test",
        "last_name": "User",
        "username": "test_user",
        "auth_date": str(auth_date),
    }

    # Generate valid hash
    check_items = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(check_items)
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hash_value = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    data["hash"] = hash_value
    return data
