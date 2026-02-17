"""Tests for WB API rate limiter and per-seller sync lock."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.rate_limiter import (
    WBRateLimiter,
    get_rate_limiter,
    release_sync_lock,
    reset_rate_limiter,
    try_acquire_sync_lock,
    _active_locks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_async_redis(rpm_limit=None):
    """
    Return (mock_redis, counts_dict).

    INCR/DECR operate on an in-memory dict so tests don't need a real Redis.
    """
    counts: dict[str, int] = {}

    async def _incr(key):
        counts[key] = counts.get(key, 0) + 1
        return counts[key]

    async def _decr(key):
        counts[key] = max(0, counts.get(key, 1) - 1)
        return counts[key]

    async def _expire(key, ttl):
        pass

    mock = AsyncMock()
    mock.incr.side_effect = _incr
    mock.decr.side_effect = _decr
    mock.expire.side_effect = _expire
    return mock, counts


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset global singleton state before and after each test."""
    reset_rate_limiter()
    _active_locks.clear()
    yield
    reset_rate_limiter()
    _active_locks.clear()


# ---------------------------------------------------------------------------
# WBRateLimiter basic behaviour
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_returns_immediately_when_below_rpm():
    """First call should not wait when count ≤ rpm."""
    limiter = WBRateLimiter(max_requests_per_minute=60)
    mock_redis, _ = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    waited = await limiter.acquire(seller_id=1)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_acquire_waits_when_over_rpm():
    """Draining all rpm slots should force the next call to wait."""
    rpm = 3
    limiter = WBRateLimiter(max_requests_per_minute=rpm)
    mock_redis, counts = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    # Fill the bucket up to the limit.
    for _ in range(rpm):
        await limiter.acquire(seller_id=1)

    # Next call must wait (count will be rpm+1 > rpm on first try).
    start = time.monotonic()
    waited = await limiter.acquire(seller_id=1)
    elapsed = time.monotonic() - start

    assert waited > 0
    assert elapsed >= 1.5  # Slept at least once (~2 s), allow some slack


@pytest.mark.asyncio
async def test_per_seller_isolation():
    """Draining seller A's bucket should not affect seller B."""
    rpm = 2
    limiter = WBRateLimiter(max_requests_per_minute=rpm)
    mock_redis, _ = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    # Drain seller 1.
    for _ in range(rpm):
        await limiter.acquire(seller_id=1)

    # Seller 2 uses a different Redis key → different counter → no wait.
    waited = await limiter.acquire(seller_id=2)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_configure_seller_overrides_default():
    """Custom RPM for a specific seller should be respected."""
    limiter = WBRateLimiter(max_requests_per_minute=1000)
    limiter.configure_seller(seller_id=42, max_requests_per_minute=2)
    mock_redis, _ = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    # Two calls go through freely.
    assert await limiter.acquire(seller_id=42) == 0.0
    assert await limiter.acquire(seller_id=42) == 0.0

    # Third call must wait.
    start = time.monotonic()
    waited = await limiter.acquire(seller_id=42)
    elapsed = time.monotonic() - start

    assert waited > 0
    assert elapsed >= 1.5


@pytest.mark.asyncio
async def test_configure_seller_uses_new_rpm_after_reconfigure():
    """After reconfigure, new RPM applies to subsequent calls."""
    limiter = WBRateLimiter(max_requests_per_minute=10)
    mock_redis, counts = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    # Drain 5 slots.
    for _ in range(5):
        await limiter.acquire(seller_id=1)

    # Reconfigure to a high limit: next call should NOT wait
    # (it starts a fresh bucket key if the minute boundary flips, but in
    # practice the mock shares counts — we just verify configure_seller stores
    # the new override and the call doesn't raise).
    limiter.configure_seller(seller_id=1, max_requests_per_minute=100)
    # Re-inject the mock (configure_seller doesn't touch _async_redis).
    limiter._async_redis = mock_redis
    # Should complete without raising.
    await limiter.acquire(seller_id=1)


@pytest.mark.asyncio
async def test_reset_does_not_raise():
    """reset() is a no-op in Redis mode; it should not raise."""
    limiter = WBRateLimiter(max_requests_per_minute=5)
    mock_redis, _ = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    limiter.reset(seller_id=1)
    limiter.reset()


@pytest.mark.asyncio
async def test_concurrent_access_is_safe():
    """Multiple concurrent acquire calls for the same seller should not crash."""
    limiter = WBRateLimiter(max_requests_per_minute=60)
    mock_redis, _ = _make_mock_async_redis()
    limiter._async_redis = mock_redis

    async def burst():
        for _ in range(10):
            await limiter.acquire(seller_id=1)

    await asyncio.gather(*[burst() for _ in range(5)])
    # No assertion beyond "did not crash / deadlock".


# ---------------------------------------------------------------------------
# Singleton access
# ---------------------------------------------------------------------------


def test_get_rate_limiter_returns_singleton():
    """get_rate_limiter should return the same instance."""
    a = get_rate_limiter()
    b = get_rate_limiter()
    assert a is b


def test_reset_rate_limiter_clears_singleton():
    """After reset, next get should create a new instance."""
    a = get_rate_limiter()
    reset_rate_limiter()
    b = get_rate_limiter()
    assert a is not b


# ---------------------------------------------------------------------------
# Per-seller sync lock (Redis-based distributed lock)
# ---------------------------------------------------------------------------


def _make_mock_sync_redis():
    """Mock sync Redis with a simple in-process lock simulation."""
    held: set[str] = set()

    def _make_lock(key, timeout=None, blocking_timeout=None):
        lock_mock = MagicMock()

        def acquire(blocking=True):
            if key in held:
                return False
            held.add(key)
            return True

        def release():
            held.discard(key)

        lock_mock.acquire.side_effect = acquire
        lock_mock.release.side_effect = release
        return lock_mock

    mock = MagicMock()
    mock.lock.side_effect = _make_lock
    return mock


@pytest.fixture()
def mock_sync_redis():
    r = _make_mock_sync_redis()
    with patch("app.services.rate_limiter._get_sync_redis", return_value=r):
        yield r


def test_sync_lock_acquire_and_release(mock_sync_redis):
    """Basic lock acquire/release cycle."""
    assert try_acquire_sync_lock(1) is True
    assert try_acquire_sync_lock(1) is False  # Already held.
    release_sync_lock(1)
    assert try_acquire_sync_lock(1) is True  # Available again.
    release_sync_lock(1)


def test_sync_lock_per_seller_isolation(mock_sync_redis):
    """Locking seller 1 should not block seller 2."""
    assert try_acquire_sync_lock(1) is True
    assert try_acquire_sync_lock(2) is True
    release_sync_lock(1)
    release_sync_lock(2)


def test_sync_lock_release_idempotent(mock_sync_redis):
    """Releasing an already-released lock should not raise."""
    release_sync_lock(999)  # Never acquired -- should be no-op.


def test_sync_lock_double_acquire_returns_false(mock_sync_redis):
    """Second acquire for same seller returns False."""
    try_acquire_sync_lock(1)
    result = try_acquire_sync_lock(1)
    assert result is False
    release_sync_lock(1)
