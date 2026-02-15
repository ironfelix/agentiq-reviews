"""Tests for sync observability: SyncMetrics, SyncHealthMonitor, alert generation."""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from app.services.sync_metrics import SyncMetrics, SyncHealthMonitor


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _make_metrics(
    seller_id: int = 1,
    channel: str = "review",
    fetched: int = 50,
    created: int = 10,
    updated: int = 40,
    skipped: int = 0,
    errors: int = 0,
    error_detail: Optional[str] = None,
    rate_limited: bool = False,
    age_seconds: float = 0.0,
) -> SyncMetrics:
    """Build a completed SyncMetrics instance.

    ``age_seconds`` controls how far in the past *both* ``started_at`` and
    ``finished_at`` are placed.  This is important for stale-sync detection
    which compares ``finished_at`` against ``datetime.now()``.

    Note: ``errors`` and ``error_detail`` are set explicitly on the dataclass
    AFTER calling ``finish()`` to avoid double-counting (finish increments
    errors when error is truthy).
    """
    started = _now() - timedelta(seconds=age_seconds + 2.0)
    m = SyncMetrics(
        seller_id=seller_id,
        channel=channel,
        started_at=started,
        fetched=fetched,
        created=created,
        updated=updated,
        skipped=skipped,
        rate_limited=rate_limited,
    )
    # finish() without error to set finished_at/duration
    m.finish()
    # Override finished_at to reflect the desired age so that
    # check_sync_health() stale detection works correctly in tests.
    if age_seconds > 0:
        m.finished_at = _now() - timedelta(seconds=age_seconds)
    # Then set error state directly to avoid double-increment
    m.errors = errors
    m.error_detail = error_detail
    return m


# ===========================================================================
# SyncMetrics dataclass tests
# ===========================================================================

class TestSyncMetrics:

    def test_finish_calculates_duration(self):
        m = SyncMetrics(seller_id=1, channel="review", started_at=_now() - timedelta(seconds=5))
        m.finish()
        assert m.finished_at is not None
        assert m.duration_seconds >= 4.5  # at least ~5 seconds

    def test_finish_with_error(self):
        m = SyncMetrics(seller_id=1, channel="question", started_at=_now())
        m.finish(error="Connection timeout")
        assert m.errors == 1
        assert m.error_detail == "Connection timeout"

    def test_finish_truncates_long_error(self):
        long_error = "x" * 1000
        m = SyncMetrics(seller_id=1, channel="chat", started_at=_now())
        m.finish(error=long_error)
        assert len(m.error_detail) == 500

    def test_apply_ingest_stats(self):
        m = SyncMetrics(seller_id=1, channel="review", started_at=_now())
        m.apply_ingest_stats({"fetched": 100, "created": 20, "updated": 75, "skipped": 5})
        assert m.fetched == 100
        assert m.created == 20
        assert m.updated == 75
        assert m.skipped == 5

    def test_apply_ingest_stats_accumulates(self):
        m = SyncMetrics(seller_id=1, channel="all", started_at=_now())
        m.apply_ingest_stats({"fetched": 50, "created": 10, "updated": 40, "skipped": 0})
        m.apply_ingest_stats({"fetched": 30, "created": 5, "updated": 20, "skipped": 5})
        assert m.fetched == 80
        assert m.created == 15
        assert m.updated == 60
        assert m.skipped == 5

    def test_as_log_dict_structure(self):
        m = _make_metrics(seller_id=42, channel="question", fetched=123)
        log_dict = m.as_log_dict()
        assert log_dict["event"] == "sync_run"
        assert log_dict["seller_id"] == 42
        assert log_dict["channel"] == "question"
        assert log_dict["fetched"] == 123
        assert "started_at" in log_dict
        assert "finished_at" in log_dict
        assert "duration_seconds" in log_dict

    def test_as_log_dict_is_json_serializable(self):
        m = _make_metrics()
        log_dict = m.as_log_dict()
        serialized = json.dumps(log_dict, ensure_ascii=False, default=str)
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["event"] == "sync_run"

    def test_log_does_not_raise(self):
        """Ensure .log() does not raise even without a handler."""
        m = _make_metrics()
        m.log()  # Should not raise

        m_error = _make_metrics(errors=1, error_detail="fail")
        m_error.log()

        m_rl = _make_metrics(rate_limited=True)
        m_rl.log()


# ===========================================================================
# SyncHealthMonitor tests
# ===========================================================================

class TestSyncHealthMonitor:

    def test_empty_monitor_returns_unknown(self):
        monitor = SyncHealthMonitor()
        health = monitor.check_sync_health(seller_id=999)
        assert health["status"] == "unknown"
        assert health["last_sync_age_seconds"] is None

    def test_record_and_check_healthy(self):
        monitor = SyncHealthMonitor()
        m = _make_metrics(seller_id=1, channel="review")
        monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=1)
        assert health["status"] == "healthy"
        assert health["error_rate"] == 0.0
        assert health["rate_limited_recent"] is False
        assert health["zero_fetch_streak"] == 0

    def test_stale_sync_warning(self):
        monitor = SyncHealthMonitor()
        m = _make_metrics(seller_id=1, channel="review", age_seconds=6 * 60)
        monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=1)
        assert health["status"] == "warning"
        assert "5 min" in health["message"]

    def test_stale_sync_critical(self):
        monitor = SyncHealthMonitor()
        m = _make_metrics(seller_id=1, channel="review", age_seconds=20 * 60)
        monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=1)
        assert health["status"] == "critical"
        assert "15 min" in health["message"]

    def test_high_error_rate_warning(self):
        monitor = SyncHealthMonitor()
        # 3 out of 10 syncs have errors -> 30% > 20%
        for i in range(10):
            m = _make_metrics(
                seller_id=2,
                channel="question",
                errors=1 if i < 3 else 0,
                error_detail="fail" if i < 3 else None,
            )
            monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=2)
        assert health["status"] == "warning"
        assert health["error_rate"] > 0.2

    def test_high_error_rate_critical(self):
        monitor = SyncHealthMonitor()
        # 6 out of 10 syncs have errors -> 60% > 50%
        for i in range(10):
            m = _make_metrics(
                seller_id=3,
                channel="review",
                errors=1 if i < 6 else 0,
                error_detail="fail" if i < 6 else None,
            )
            monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=3)
        assert health["status"] == "critical"

    def test_rate_limited_warning(self):
        monitor = SyncHealthMonitor()
        m = _make_metrics(seller_id=4, channel="review", rate_limited=True)
        monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=4)
        assert health["status"] == "warning"
        assert health["rate_limited_recent"] is True

    def test_zero_fetch_streak(self):
        monitor = SyncHealthMonitor()
        # 4 consecutive zero-fetch syncs in review channel
        for _ in range(4):
            m = _make_metrics(
                seller_id=5,
                channel="review",
                fetched=0,
                created=0,
                updated=0,
            )
            monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=5)
        assert health["zero_fetch_streak"] >= 3
        assert health["status"] == "warning"

    def test_zero_fetch_streak_broken_by_normal_sync(self):
        monitor = SyncHealthMonitor()
        # 2 zero-fetch, then 1 normal, then 1 zero-fetch = streak of 1
        for fetched_count in [0, 0, 50, 0]:
            m = _make_metrics(
                seller_id=6,
                channel="review",
                fetched=fetched_count,
                created=fetched_count,
                updated=0,
            )
            monitor.record_sync(m)
        health = monitor.check_sync_health(seller_id=6)
        assert health["zero_fetch_streak"] == 1
        assert health["status"] == "healthy"

    def test_ring_buffer_evicts_old_entries(self):
        monitor = SyncHealthMonitor(buffer_size=5)
        # Add 8 metrics, only last 5 should be kept
        for i in range(8):
            m = _make_metrics(
                seller_id=7,
                channel="review",
                fetched=i * 10,
            )
            monitor.record_sync(m)
        buf = monitor._get_buffer(7, "review")
        assert len(buf) == 5
        # Oldest should have fetched=30 (index 3)
        assert buf[0].fetched == 30

    def test_multiple_sellers_isolated(self):
        monitor = SyncHealthMonitor()
        m1 = _make_metrics(seller_id=10, channel="review")
        m2 = _make_metrics(seller_id=20, channel="review", errors=1, error_detail="fail")
        monitor.record_sync(m1)
        monitor.record_sync(m2)

        h1 = monitor.check_sync_health(10)
        h2 = monitor.check_sync_health(20)
        assert h1["status"] == "healthy"
        assert h2["error_rate"] == 1.0

    def test_multiple_channels_combined(self):
        monitor = SyncHealthMonitor()
        # All channels for same seller
        for ch in ("review", "question", "chat"):
            m = _make_metrics(seller_id=11, channel=ch, fetched=50)
            monitor.record_sync(m)
        health = monitor.check_sync_health(11)
        assert health["status"] == "healthy"
        assert health["error_rate"] == 0.0

    def test_get_last_metrics(self):
        monitor = SyncHealthMonitor()
        m1 = _make_metrics(seller_id=12, channel="review", fetched=10)
        m2 = _make_metrics(seller_id=12, channel="review", fetched=20)
        monitor.record_sync(m1)
        monitor.record_sync(m2)
        last = monitor.get_last_metrics(12, "review")
        assert last is not None
        assert last.fetched == 20

    def test_get_last_metrics_none_when_empty(self):
        monitor = SyncHealthMonitor()
        assert monitor.get_last_metrics(999, "review") is None

    def test_clear_all(self):
        monitor = SyncHealthMonitor()
        monitor.record_sync(_make_metrics(seller_id=1, channel="review"))
        monitor.record_sync(_make_metrics(seller_id=2, channel="question"))
        monitor.clear()
        assert monitor.check_sync_health(1)["status"] == "unknown"
        assert monitor.check_sync_health(2)["status"] == "unknown"

    def test_clear_seller(self):
        monitor = SyncHealthMonitor()
        monitor.record_sync(_make_metrics(seller_id=1, channel="review"))
        monitor.record_sync(_make_metrics(seller_id=2, channel="question"))
        monitor.clear(seller_id=1)
        assert monitor.check_sync_health(1)["status"] == "unknown"
        assert monitor.check_sync_health(2)["status"] == "healthy"


# ===========================================================================
# Alert generation tests
# ===========================================================================

class TestSyncAlerts:

    def test_no_alerts_when_healthy(self):
        monitor = SyncHealthMonitor()
        monitor.record_sync(_make_metrics(seller_id=1))
        alerts = monitor.get_active_alerts(seller_id=1)
        assert alerts == []

    def test_no_alerts_when_unknown(self):
        monitor = SyncHealthMonitor()
        alerts = monitor.get_active_alerts(seller_id=999)
        assert alerts == []

    def test_sync_stale_alert(self):
        monitor = SyncHealthMonitor()
        m = _make_metrics(seller_id=1, channel="review", age_seconds=20 * 60)
        monitor.record_sync(m)
        alerts = monitor.get_active_alerts(seller_id=1)
        codes = {a["code"] for a in alerts}
        assert "sync_stale" in codes
        stale = next(a for a in alerts if a["code"] == "sync_stale")
        assert stale["severity"] == "high"

    def test_sync_errors_alert(self):
        monitor = SyncHealthMonitor()
        for _ in range(5):
            monitor.record_sync(
                _make_metrics(seller_id=2, errors=1, error_detail="timeout")
            )
        alerts = monitor.get_active_alerts(seller_id=2)
        codes = {a["code"] for a in alerts}
        assert "sync_errors" in codes

    def test_sync_rate_limited_alert(self):
        monitor = SyncHealthMonitor()
        monitor.record_sync(_make_metrics(seller_id=3, rate_limited=True))
        alerts = monitor.get_active_alerts(seller_id=3)
        codes = {a["code"] for a in alerts}
        assert "sync_rate_limited" in codes
        rl = next(a for a in alerts if a["code"] == "sync_rate_limited")
        assert rl["severity"] == "medium"

    def test_sync_zero_fetch_alert(self):
        monitor = SyncHealthMonitor()
        for _ in range(4):
            monitor.record_sync(
                _make_metrics(seller_id=4, fetched=0, created=0, updated=0)
            )
        alerts = monitor.get_active_alerts(seller_id=4)
        codes = {a["code"] for a in alerts}
        assert "sync_zero_fetch" in codes

    def test_alert_format_matches_ops_alert_schema(self):
        """Verify alert dict has same keys as InteractionOpsAlert schema."""
        monitor = SyncHealthMonitor()
        monitor.record_sync(
            _make_metrics(seller_id=5, rate_limited=True)
        )
        alerts = monitor.get_active_alerts(seller_id=5)
        assert len(alerts) > 0
        for alert in alerts:
            assert set(alert.keys()) == {"code", "severity", "title", "message"}
            assert isinstance(alert["code"], str)
            assert isinstance(alert["severity"], str)
            assert isinstance(alert["title"], str)
            assert isinstance(alert["message"], str)

    def test_multiple_alerts_at_once(self):
        monitor = SyncHealthMonitor()
        # Stale + errors + rate limited
        m = _make_metrics(
            seller_id=6,
            channel="review",
            age_seconds=20 * 60,
            errors=1,
            error_detail="fail",
            rate_limited=True,
        )
        monitor.record_sync(m)
        alerts = monitor.get_active_alerts(seller_id=6)
        codes = {a["code"] for a in alerts}
        assert "sync_stale" in codes
        assert "sync_errors" in codes
        assert "sync_rate_limited" in codes
