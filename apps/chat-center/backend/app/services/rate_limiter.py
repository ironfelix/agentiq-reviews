"""Per-seller rate limiter for WB API calls.

Provides a lightweight in-process token-bucket limiter that prevents
exceeding WB API rate limits across all connector calls for a given seller.

No external dependencies (no Redis): works in both single-process (dev)
and multi-worker (prod Celery) modes.  In multi-worker mode each worker
maintains its own bucket, so the effective per-seller budget should be
divided by the number of workers via ``max_requests_per_minute``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default: 30 requests/minute per seller (WB typical limit).
_DEFAULT_RPM = 30


@dataclass
class _TokenBucket:
    """Simple token-bucket state for a single seller."""

    max_tokens: float
    refill_rate: float  # tokens per second
    tokens: float = field(init=False)
    last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def __post_init__(self) -> None:
        self.tokens = self.max_tokens
        self.last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self) -> float:
        """Wait until a token is available and consume it.

        Returns the number of seconds we waited (0.0 if no wait was needed).
        """
        async with self._lock:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            # Calculate wait time until we have 1 token.
            deficit = 1.0 - self.tokens
            wait_seconds = deficit / self.refill_rate

        # Sleep outside the lock so other coroutines can check their buckets.
        logger.debug("Rate limiter: waiting %.2fs for token", wait_seconds)
        await asyncio.sleep(wait_seconds)

        async with self._lock:
            self._refill()
            self.tokens = max(0.0, self.tokens - 1.0)
            return wait_seconds


class WBRateLimiter:
    """Per-seller rate limiter for WB API calls.

    Usage::

        limiter = get_rate_limiter()
        await limiter.acquire(seller_id)
        # ... make API call ...

    The limiter is designed to be used as a singleton via ``get_rate_limiter()``.
    """

    def __init__(self, max_requests_per_minute: int = _DEFAULT_RPM) -> None:
        self._default_rpm = max_requests_per_minute
        self._buckets: Dict[int, _TokenBucket] = {}
        self._seller_overrides: Dict[int, int] = {}  # seller_id -> custom RPM

    def configure_seller(self, seller_id: int, max_requests_per_minute: int) -> None:
        """Set a custom rate limit for a specific seller.

        If the bucket already exists it will be recreated with the new limit.
        """
        self._seller_overrides[seller_id] = max_requests_per_minute
        # Invalidate existing bucket so it gets recreated on next acquire.
        self._buckets.pop(seller_id, None)

    def _get_bucket(self, seller_id: int) -> _TokenBucket:
        if seller_id not in self._buckets:
            rpm = self._seller_overrides.get(seller_id, self._default_rpm)
            self._buckets[seller_id] = _TokenBucket(
                max_tokens=float(rpm),
                refill_rate=rpm / 60.0,
            )
        return self._buckets[seller_id]

    async def acquire(self, seller_id: int) -> float:
        """Wait until rate limit allows next request for *seller_id*.

        Returns the number of seconds we waited.
        """
        bucket = self._get_bucket(seller_id)
        waited = await bucket.acquire()
        if waited > 0:
            logger.info(
                "Rate limiter: seller=%s waited %.2fs before API call",
                seller_id,
                waited,
            )
        return waited

    def reset(self, seller_id: Optional[int] = None) -> None:
        """Reset bucket(s) -- mainly useful for testing."""
        if seller_id is not None:
            self._buckets.pop(seller_id, None)
        else:
            self._buckets.clear()


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
# ---------------------------------------------------------------------------

_sync_locks: Dict[int, bool] = {}


class SyncAlreadyRunning(Exception):
    """Raised when a sync task for a seller is already in progress."""

    def __init__(self, seller_id: int) -> None:
        self.seller_id = seller_id
        super().__init__(f"Sync already running for seller {seller_id}")


def try_acquire_sync_lock(seller_id: int) -> bool:
    """Non-blocking attempt to acquire the per-seller sync lock.

    Returns True if lock was acquired, False if another sync is already running.
    Thread-safe for Celery workers (uses a plain dict -- each worker process
    has its own copy, and ``worker_prefetch_multiplier=1`` ensures at most
    one task per worker at a time).
    """
    if _sync_locks.get(seller_id, False):
        return False
    _sync_locks[seller_id] = True
    return True


def release_sync_lock(seller_id: int) -> None:
    """Release the per-seller sync lock."""
    _sync_locks.pop(seller_id, None)
