"""
Pytest configuration and fixtures for AgentIQ Chat Center API tests.
"""
import pytest
import httpx
from typing import Generator, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.database import Base


BASE_URL = "http://localhost:8001"


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture
def client() -> Generator[httpx.Client, None, None]:
    """Synchronous HTTP client for API testing."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
def test_user_data() -> dict:
    """Test user registration data."""
    import uuid
    unique_id = uuid.uuid4().hex[:8]
    return {
        "email": f"test_{unique_id}@pytest.com",
        "password": "password123",
        "name": f"Test User {unique_id}",
        "marketplace": "wildberries"
    }


@pytest.fixture
def auth_token(client: httpx.Client, test_user_data: dict) -> str:
    """Get auth token by registering a test user."""
    response = client.post("/api/auth/register", json=test_user_data)
    if response.status_code in [200, 201]:
        return response.json()["access_token"]
    # If user exists, try login
    response = client.post("/api/auth/login", json={
        "email": test_user_data["email"],
        "password": test_user_data["password"]
    })
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token: str) -> dict:
    """Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async database session fixture for unit tests.

    Uses SQLite in-memory database for fast isolated tests.
    """
    # Create in-memory SQLite database for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()
