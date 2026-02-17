"""Per-seller rate limiter for WB API calls.

Redis-based sliding window rate limiter that works correctly across multiple
Celery workers. Each worker shares the same counters via Redis, preventing
the WB API rate from doubling/tripling with multiple workers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

import redis
import redis.asyncio

logger = logging.getLogger(__name__)

# Default: 30 requests/minute per seller (WB typical limit).
_DEFAULT_RPM = 30


class WBRateLimiter:
    """Per-seller rate limiter for WB API calls.

    Uses Redis sliding window (per-minute bucket) so all Celery workers
    share the same rate counters.

    Usage::

        limiter = get_rate_limiter()
        await limiter.acquire(seller_id)
        # ... make API call ...
    """

    def __init__(self, max_requests_per_minute: int = _DEFAULT_RPM) -> None:
        self._default_rpm = max_requests_per_minute
        self._seller_overrides: Dict[int, int] = {}
        self._async_redis: Optional[redis.asyncio.Redis] = None

    def _get_async_redis(self) -> redis.asyncio.Redis:
        if self._async_redis is None:
            from app.config import get_settings
            settings = get_settings()
            self._async_redis = redis.asyncio.Redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
        return self._async_redis

    def configure_seller(self, seller_id: int, max_requests_per_minute: int) -> None:
        """Set a custom rate limit for a specific seller."""
        self._seller_overrides[seller_id] = max_requests_per_minute

    async def acquire(self, seller_id: int) -> float:
        """Wait until rate limit allows next request for *seller_id*.

        Uses a 1-minute sliding window bucket in Redis (INCR + EXPIRE).
        Returns the number of seconds we waited.
        """
        rpm = self._seller_overrides.get(seller_id, self._default_rpm)
        r = self._get_async_redis()
        waited = 0.0

        while True:
            bucket_key = f"wb_rl:{seller_id}:{int(time.time() // 60)}"
            count = await r.incr(bucket_key)
            if count == 1:
                # First request in this bucket — set 2-min TTL so key auto-expires
                await r.expire(bucket_key, 120)

            if count <= rpm:
                # Token available
                break

            # Over limit — roll back and wait until next minute
            await r.decr(bucket_key)
            wait_seconds = 2.0
            logger.info(
                "Rate limiter: seller=%s over rpm=%s, waiting %.1fs",
                seller_id,
                rpm,
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)
            waited += wait_seconds

        if waited > 0:
            logger.info(
                "Rate limiter: seller=%s waited %.2fs before API call",
                seller_id,
                waited,
            )
        return waited

    def reset(self, seller_id: Optional[int] = None) -> None:
        """Reset bucket(s) — mainly useful for testing."""
        # In Redis mode we can't easily reset without a sync client;
        # acceptable for tests which typically use a fresh Redis DB.
        logger.debug("reset() called (seller_id=%s) — no-op in Redis mode", seller_id)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_instance: Optional[WBRateLimiter] = None


def get_rate_limiter() -> WBRateLimiter:
    """Return the module-level singleton rate limiter."""
    global _instance
    if _instance is None:
        _instance = WBRateLimiter(max_requests_per_minute=_DEFAULT_RPM)
    return _instance


def reset_rate_limiter() -> None:
    """Destroy the singleton (useful for tests)."""
    global _instance
    _instance = None


# ---------------------------------------------------------------------------
# Per-seller sync lock (prevents concurrent sync tasks for same seller)
# Uses Redis distributed lock so it works across multiple Celery workers.
# ---------------------------------------------------------------------------

_sync_redis: Optional[redis.Redis] = None
_active_locks: Dict[int, redis.lock.Lock] = {}


def _get_sync_redis() -> redis.Redis:
    global _sync_redis
    if _sync_redis is None:
        from app.config import get_settings
        settings = get_settings()
        _sync_redis = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_redis


class SyncAlreadyRunning(Exception):
    """Raised when a sync task for a seller is already in progress."""

    def __init__(self, seller_id: int) -> None:
        self.seller_id = seller_id
        super().__init__(f"Sync already running for seller {seller_id}")


def try_acquire_sync_lock(seller_id: int) -> bool:
    """Non-blocking attempt to acquire the per-seller sync lock.

    Returns True if lock was acquired, False if another sync is already running.
    Uses a Redis distributed lock (TTL=60s) so it works across multiple workers.
    """
    r = _get_sync_redis()
    lock = r.lock(f"wb_sync_lock:{seller_id}", timeout=60, blocking_timeout=0)
    acquired = lock.acquire(blocking=False)
    if acquired:
        _active_locks[seller_id] = lock
    return acquired


def release_sync_lock(seller_id: int) -> None:
    """Release the per-seller sync lock."""
    lock = _active_locks.pop(seller_id, None)
    if lock is not None:
        try:
            lock.release()
        except Exception as e:
            logger.warning("Failed to release sync lock for seller %s: %s", seller_id, e)
