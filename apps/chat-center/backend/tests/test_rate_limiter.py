"""Tests for WB API rate limiter and per-seller sync lock."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

import pytest

from app.services.rate_limiter import (
    WBRateLimiter,
    get_rate_limiter,
    release_sync_lock,
    reset_rate_limiter,
    try_acquire_sync_lock,
    _sync_locks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset global state before and after each test."""
    reset_rate_limiter()
    _sync_locks.clear()
    yield
    reset_rate_limiter()
    _sync_locks.clear()


# ---------------------------------------------------------------------------
# WBRateLimiter basic behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acquire_returns_immediately_when_bucket_has_tokens():
    """First call should not wait."""
    limiter = WBRateLimiter(max_requests_per_minute=60)
    waited = await limiter.acquire(seller_id=1)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_acquire_does_not_exceed_max_rpm():
    """Draining all tokens should force the next call to wait."""
    rpm = 6  # 6 tokens = 0.1 tokens/sec
    limiter = WBRateLimiter(max_requests_per_minute=rpm)

    # Drain all tokens.
    for _ in range(rpm):
        await limiter.acquire(seller_id=1)

    # Next call must wait.
    start = time.monotonic()
    waited = await limiter.acquire(seller_id=1)
    elapsed = time.monotonic() - start

    assert waited > 0
    assert elapsed >= 0.05  # Should have actually waited


@pytest.mark.asyncio
async def test_per_seller_isolation():
    """Draining seller A's bucket should not affect seller B."""
    rpm = 2
    limiter = WBRateLimiter(max_requests_per_minute=rpm)

    # Drain seller 1.
    for _ in range(rpm):
        await limiter.acquire(seller_id=1)

    # Seller 2 should still have tokens.
    waited = await limiter.acquire(seller_id=2)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_configure_seller_overrides_default():
    """Custom RPM for a specific seller should be respected."""
    limiter = WBRateLimiter(max_requests_per_minute=1000)
    limiter.configure_seller(seller_id=42, max_requests_per_minute=2)

    # Seller 42 should have 2 tokens.
    await limiter.acquire(seller_id=42)
    await limiter.acquire(seller_id=42)

    # Third call should wait.
    start = time.monotonic()
    await limiter.acquire(seller_id=42)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05


@pytest.mark.asyncio
async def test_configure_seller_recreates_bucket():
    """Reconfiguring a seller invalidates the old bucket."""
    limiter = WBRateLimiter(max_requests_per_minute=10)

    # Drain some tokens.
    for _ in range(5):
        await limiter.acquire(seller_id=1)

    # Reconfigure with higher limit -- bucket should reset.
    limiter.configure_seller(seller_id=1, max_requests_per_minute=100)
    waited = await limiter.acquire(seller_id=1)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_reset_single_seller():
    """Resetting a specific seller should not affect others."""
    limiter = WBRateLimiter(max_requests_per_minute=2)

    # Drain both sellers.
    for _ in range(2):
        await limiter.acquire(seller_id=1)
        await limiter.acquire(seller_id=2)

    # Reset seller 1 only.
    limiter.reset(seller_id=1)

    # Seller 1 should have tokens again.
    waited = await limiter.acquire(seller_id=1)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_reset_all():
    """Resetting all sellers should clear all buckets."""
    limiter = WBRateLimiter(max_requests_per_minute=2)

    for _ in range(2):
        await limiter.acquire(seller_id=1)

    limiter.reset()
    waited = await limiter.acquire(seller_id=1)
    assert waited == 0.0


@pytest.mark.asyncio
async def test_concurrent_access_is_safe():
    """Multiple concurrent acquire calls for the same seller should not corrupt state."""
    limiter = WBRateLimiter(max_requests_per_minute=60)

    async def burst():
        for _ in range(10):
            await limiter.acquire(seller_id=1)

    # Run 5 concurrent bursts (50 total).
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
# Per-seller sync lock
# ---------------------------------------------------------------------------


def test_sync_lock_acquire_and_release():
    """Basic lock acquire/release cycle."""
    assert try_acquire_sync_lock(1) is True
    assert try_acquire_sync_lock(1) is False  # Already held.
    release_sync_lock(1)
    assert try_acquire_sync_lock(1) is True  # Available again.
    release_sync_lock(1)


def test_sync_lock_per_seller_isolation():
    """Locking seller 1 should not block seller 2."""
    assert try_acquire_sync_lock(1) is True
    assert try_acquire_sync_lock(2) is True
    release_sync_lock(1)
    release_sync_lock(2)


def test_sync_lock_release_idempotent():
    """Releasing an already-released lock should not raise."""
    release_sync_lock(999)  # Never acquired -- should be no-op.


def test_sync_lock_double_acquire_returns_false():
    """Second acquire for same seller returns False."""
    try_acquire_sync_lock(1)
    result = try_acquire_sync_lock(1)
    assert result is False
    release_sync_lock(1)
