"""
Tests for configurable reply_pending_window_minutes.

Verifies that _reply_pending_override respects the window parameter,
and that the default (180 min) is preserved for backward compatibility.
"""

import os

os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_reply_pending.db")

from datetime import datetime, timezone, timedelta

from app.models.interaction import Interaction
from app.services.interaction_ingest import (
    _DEFAULT_REPLY_PENDING_WINDOW,
    _reply_pending_override,
)


def _make_interaction_with_reply(minutes_ago: int) -> Interaction:
    """Create an Interaction with a local AgentIQ reply sent `minutes_ago` minutes ago."""
    reply_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return Interaction(
        seller_id=1,
        marketplace="wildberries",
        channel="review",
        external_id="r-test",
        text="Test review",
        status="responded",
        priority="low",
        needs_response=False,
        source="wb_api",
        extra_data={
            "last_reply_source": "agentiq",
            "last_reply_at": reply_at.isoformat(),
        },
    )


class TestReplyPendingOverride:
    """Tests for _reply_pending_override with configurable window."""

    def test_default_window_is_180(self):
        """The module-level default should be 180 minutes."""
        assert _DEFAULT_REPLY_PENDING_WINDOW == 180

    def test_within_default_window(self):
        """A reply 60 min ago should be pending under default 180-min window."""
        existing = _make_interaction_with_reply(minutes_ago=60)
        assert _reply_pending_override(existing=existing) is True

    def test_outside_default_window(self):
        """A reply 200 min ago should NOT be pending under default 180-min window."""
        existing = _make_interaction_with_reply(minutes_ago=200)
        assert _reply_pending_override(existing=existing) is False

    def test_custom_window_short(self):
        """With a 30-min window, a reply 60 min ago should NOT be pending."""
        existing = _make_interaction_with_reply(minutes_ago=60)
        assert _reply_pending_override(existing=existing, window_minutes=30) is False

    def test_custom_window_long(self):
        """With a 1440-min (24h) window, a reply 200 min ago should still be pending."""
        existing = _make_interaction_with_reply(minutes_ago=200)
        assert _reply_pending_override(existing=existing, window_minutes=1440) is True

    def test_custom_window_exact_boundary(self):
        """A reply just inside the window boundary should still be pending."""
        # Use window_minutes=61 (1 min of headroom) to avoid flaky sub-second
        # timing drift between _make_interaction_with_reply and the function's
        # own datetime.now() call.
        existing = _make_interaction_with_reply(minutes_ago=60)
        assert _reply_pending_override(existing=existing, window_minutes=61) is True

    def test_no_existing_interaction(self):
        """None existing always returns False."""
        assert _reply_pending_override(existing=None) is False
        assert _reply_pending_override(existing=None, window_minutes=1440) is False

    def test_non_agentiq_source_ignored(self):
        """Replies from non-agentiq sources should not trigger override."""
        reply_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        existing = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="review",
            external_id="r-other",
            text="Test",
            status="responded",
            priority="low",
            needs_response=False,
            source="wb_api",
            extra_data={
                "last_reply_source": "wb_api",
                "last_reply_at": reply_at.isoformat(),
            },
        )
        assert _reply_pending_override(existing=existing, window_minutes=1440) is False

    def test_missing_reply_at(self):
        """If last_reply_at is missing, override should return False."""
        existing = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="review",
            external_id="r-nots",
            text="Test",
            status="responded",
            priority="low",
            needs_response=False,
            source="wb_api",
            extra_data={
                "last_reply_source": "agentiq",
            },
        )
        assert _reply_pending_override(existing=existing, window_minutes=180) is False
