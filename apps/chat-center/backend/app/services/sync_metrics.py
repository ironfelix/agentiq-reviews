"""Sync observability: structured metrics, health checks, alerting.

Provides:
- SyncMetrics dataclass for structured logging of each sync run
- SyncHealthMonitor with in-memory ring buffer for health checks
- Alert generation for ops-alerts integration (no external deps)
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ring buffer size per seller/channel pair
# ---------------------------------------------------------------------------
_RING_BUFFER_SIZE = 10


@dataclass
class SyncMetrics:
    """Structured metrics for a single sync run."""

    seller_id: int
    channel: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    error_detail: Optional[str] = None
    rate_limited: bool = False

    def finish(self, *, error: Optional[str] = None) -> None:
        """Mark sync run as finished, calculating duration."""
        self.finished_at = datetime.now(timezone.utc)
        self.duration_seconds = round(
            (self.finished_at - self.started_at).total_seconds(), 3
        )
        if error:
            self.errors += 1
            self.error_detail = str(error)[:500]

    def apply_ingest_stats(self, stats: Dict[str, int]) -> None:
        """Merge IngestStats dict (fetched/created/updated/skipped) into this metrics object."""
        self.fetched += int(stats.get("fetched", 0))
        self.created += int(stats.get("created", 0))
        self.updated += int(stats.get("updated", 0))
        self.skipped += int(stats.get("skipped", 0))

    def as_log_dict(self) -> Dict[str, Any]:
        """Serialize to dict suitable for structured JSON logging."""
        return {
            "event": "sync_run",
            "seller_id": self.seller_id,
            "channel": self.channel,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "fetched": self.fetched,
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "errors": self.errors,
            "error_detail": self.error_detail,
            "rate_limited": self.rate_limited,
        }

    def log(self) -> None:
        """Emit structured log entry at appropriate level."""
        log_data = self.as_log_dict()
        msg = json.dumps(log_data, ensure_ascii=False, default=str)
        if self.errors > 0:
            logger.error("sync_metrics: %s", msg)
        elif self.rate_limited:
            logger.warning("sync_metrics: %s", msg)
        else:
            logger.info("sync_metrics: %s", msg)


def _make_key(seller_id: int, channel: str = "all") -> str:
    return f"{seller_id}:{channel}"


class SyncHealthMonitor:
    """Track sync health across sellers using in-memory ring buffers.

    Thread-safe: uses a threading.Lock for concurrent Celery workers.
    Does NOT require Redis or any external dependency.
    """

    def __init__(self, buffer_size: int = _RING_BUFFER_SIZE) -> None:
        self._buffers: Dict[str, deque[SyncMetrics]] = {}
        self._lock = threading.Lock()
        self._buffer_size = buffer_size

    def record_sync(self, metrics: SyncMetrics) -> None:
        """Store sync run metrics in ring buffer."""
        key = _make_key(metrics.seller_id, metrics.channel)
        with self._lock:
            if key not in self._buffers:
                self._buffers[key] = deque(maxlen=self._buffer_size)
            self._buffers[key].append(metrics)

    def _get_buffer(self, seller_id: int, channel: str = "all") -> list[SyncMetrics]:
        key = _make_key(seller_id, channel)
        with self._lock:
            buf = self._buffers.get(key)
            if not buf:
                return []
            return list(buf)

    def _get_all_channel_buffers(self, seller_id: int) -> list[SyncMetrics]:
        """Get metrics from all channel buffers for a seller."""
        with self._lock:
            prefix = f"{seller_id}:"
            all_metrics: list[SyncMetrics] = []
            for key, buf in self._buffers.items():
                if key.startswith(prefix):
                    all_metrics.extend(buf)
            return all_metrics

    def check_sync_health(self, seller_id: int) -> Dict[str, Any]:
        """Check if sync is healthy for a seller.

        Checks across all channels for this seller:
        - Last sync age (> 5 min = warning, > 15 min = critical)
        - Error rate (> 20% of last N syncs = warning)
        - Rate limiting frequency
        - Zero-fetch anomaly (fetched=0 for 3+ consecutive syncs in a channel)
        """
        all_metrics = self._get_all_channel_buffers(seller_id)
        if not all_metrics:
            return {
                "seller_id": seller_id,
                "status": "unknown",
                "message": "No sync data recorded yet",
                "last_sync_age_seconds": None,
                "error_rate": 0.0,
                "rate_limited_recent": False,
                "zero_fetch_streak": 0,
            }

        now = datetime.now(timezone.utc)

        # Last sync age
        latest_finished = None
        for m in all_metrics:
            ts = m.finished_at or m.started_at
            if latest_finished is None or ts > latest_finished:
                latest_finished = ts

        last_sync_age_seconds: Optional[float] = None
        if latest_finished:
            last_sync_age_seconds = round((now - latest_finished).total_seconds(), 1)

        # Error rate across all channels
        total_runs = len(all_metrics)
        error_runs = sum(1 for m in all_metrics if m.errors > 0)
        error_rate = round(error_runs / total_runs, 4) if total_runs > 0 else 0.0

        # Rate limited in last 3 syncs (any channel)
        sorted_metrics = sorted(
            all_metrics,
            key=lambda m: m.finished_at or m.started_at,
            reverse=True,
        )
        recent_3 = sorted_metrics[:3]
        rate_limited_recent = any(m.rate_limited for m in recent_3)

        # Zero-fetch streak per channel
        max_zero_fetch_streak = 0
        with self._lock:
            prefix = f"{seller_id}:"
            for key, buf in self._buffers.items():
                if not key.startswith(prefix):
                    continue
                streak = 0
                for m in reversed(buf):
                    if m.fetched == 0 and m.errors == 0:
                        streak += 1
                    else:
                        break
                max_zero_fetch_streak = max(max_zero_fetch_streak, streak)

        # Determine overall status
        status = "healthy"
        message = "Sync is operating normally"

        if last_sync_age_seconds is not None and last_sync_age_seconds > 15 * 60:
            status = "critical"
            message = f"Last sync was {int(last_sync_age_seconds)}s ago (>15 min)"
        elif error_rate > 0.5:
            status = "critical"
            message = f"Error rate {round(error_rate * 100, 1)}% (>50%)"
        elif last_sync_age_seconds is not None and last_sync_age_seconds > 5 * 60:
            status = "warning"
            message = f"Last sync was {int(last_sync_age_seconds)}s ago (>5 min)"
        elif error_rate > 0.2:
            status = "warning"
            message = f"Error rate {round(error_rate * 100, 1)}% (>20%)"
        elif rate_limited_recent:
            status = "warning"
            message = "Rate limited in recent syncs"
        elif max_zero_fetch_streak >= 3:
            status = "warning"
            message = f"Zero records fetched for {max_zero_fetch_streak} consecutive syncs"

        return {
            "seller_id": seller_id,
            "status": status,
            "message": message,
            "last_sync_age_seconds": last_sync_age_seconds,
            "error_rate": error_rate,
            "rate_limited_recent": rate_limited_recent,
            "zero_fetch_streak": max_zero_fetch_streak,
        }

    def get_active_alerts(self, seller_id: int) -> list[Dict[str, Any]]:
        """Get current sync-related alerts for a seller.

        Returns alert dicts compatible with InteractionOpsAlert schema.
        """
        health = self.check_sync_health(seller_id)
        alerts: list[Dict[str, Any]] = []

        if health["status"] == "unknown":
            return alerts

        last_age = health.get("last_sync_age_seconds")
        error_rate = health.get("error_rate", 0.0)
        rate_limited = health.get("rate_limited_recent", False)
        zero_streak = health.get("zero_fetch_streak", 0)

        # Alert: sync_stale
        if last_age is not None and last_age > 15 * 60:
            minutes_ago = int(last_age / 60)
            alerts.append({
                "code": "sync_stale",
                "severity": "high",
                "title": "Синхронизация устарела",
                "message": f"Последний sync был {minutes_ago} мин назад (лимит 15 мин)",
            })

        # Alert: sync_errors
        if error_rate > 0.2:
            alerts.append({
                "code": "sync_errors",
                "severity": "high",
                "title": "Высокий процент ошибок синхронизации",
                "message": f"Error rate {round(error_rate * 100, 1)}% за последние sync (лимит 20%)",
            })

        # Alert: sync_rate_limited
        if rate_limited:
            alerts.append({
                "code": "sync_rate_limited",
                "severity": "medium",
                "title": "Rate limiting при синхронизации",
                "message": "Rate limit сработал в одном из последних 3 sync циклов",
            })

        # Alert: sync_zero_fetch
        if zero_streak >= 3:
            alerts.append({
                "code": "sync_zero_fetch",
                "severity": "medium",
                "title": "Нет данных при синхронизации",
                "message": f"0 записей получено {zero_streak} раз подряд",
            })

        return alerts

    def get_last_metrics(self, seller_id: int, channel: str = "all") -> Optional[SyncMetrics]:
        """Get the most recent SyncMetrics for a seller/channel."""
        buf = self._get_buffer(seller_id, channel)
        return buf[-1] if buf else None

    def clear(self, seller_id: Optional[int] = None) -> None:
        """Clear buffers. If seller_id given, only clear that seller's data."""
        with self._lock:
            if seller_id is None:
                self._buffers.clear()
            else:
                prefix = f"{seller_id}:"
                keys_to_remove = [k for k in self._buffers if k.startswith(prefix)]
                for k in keys_to_remove:
                    del self._buffers[k]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
sync_health_monitor = SyncHealthMonitor()
