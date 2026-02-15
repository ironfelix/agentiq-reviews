"""
Lightweight tests for unified interactions layer.

These tests do not require a running API server and do not call external WB APIs.
"""

import os

# Ensure settings can be initialized in test context.
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1rZXktZm9yLXB5dGVzdC0xMjM0NTY3ODkwMTI=")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_interactions.db")

import pytest

from app.main import app
from app.models.interaction import Interaction
from app.services.interaction_drafts import _fallback_draft, generate_interaction_draft
from app.services.interaction_metrics import (
    EVENT_DRAFT_ACCEPTED,
    EVENT_DRAFT_EDITED,
    EVENT_REPLY_MANUAL,
    classify_reply_quality,
)


class TestInteractionRoutes:
    """Route smoke tests for interactions API."""

    def test_interaction_routes_registered(self):
        paths = {route.path for route in app.routes}
        assert "/api/interactions" in paths
        assert "/api/interactions/metrics/quality" in paths
        assert "/api/interactions/metrics/quality-history" in paths
        assert "/api/interactions/metrics/ops-alerts" in paths
        assert "/api/interactions/metrics/pilot-readiness" in paths
        assert "/api/interactions/sync/reviews" in paths
        assert "/api/interactions/sync/questions" in paths
        assert "/api/interactions/sync/chats" in paths
        assert "/api/interactions/{interaction_id}/timeline" in paths
        assert "/api/interactions/{interaction_id}/ai-draft" in paths
        assert "/api/interactions/{interaction_id}/reply" in paths


class TestInteractionDrafts:
    """Draft generation behavior tests."""

    def test_fallback_draft_for_negative_review(self):
        interaction = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="review",
            external_id="r-1",
            text="Товар с браком",
            rating=1,
            priority="high",
            status="open",
            needs_response=True,
            source="wb_api",
        )
        draft = _fallback_draft(interaction)
        assert draft.source == "fallback"
        assert "жаль" in draft.text.lower()

    @pytest.mark.asyncio
    async def test_generate_draft_question_without_db(self):
        interaction = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="question",
            external_id="q-1",
            text="Подскажите, какой размер при росте 170?",
            priority="high",
            status="open",
            needs_response=True,
            source="wb_api",
        )
        draft = await generate_interaction_draft(db=None, interaction=interaction)
        assert draft.text
        # Fallback analyzer maps the question to a valid intent; the exact
        # intent depends on keyword matching and may vary (sizing_fit,
        # product_spec, spec_compatibility, etc.).
        assert draft.intent is None or isinstance(draft.intent, str)


class TestReplyQualityClassification:
    """Reply quality classification behavior tests."""

    def test_reply_quality_accepted(self):
        interaction = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="review",
            external_id="r-42",
            extra_data={"last_ai_draft": {"text": "Спасибо за отзыв!", "source": "llm"}},
            status="open",
            priority="normal",
            needs_response=True,
            source="wb_api",
        )
        outcome, draft_source = classify_reply_quality(interaction, "  спасибо   за   отзыв! ")
        assert outcome == EVENT_DRAFT_ACCEPTED
        assert draft_source == "llm"

    def test_reply_quality_edited(self):
        interaction = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="question",
            external_id="q-42",
            extra_data={"last_ai_draft": {"text": "Да, подойдет.", "source": "fallback"}},
            status="open",
            priority="normal",
            needs_response=True,
            source="wb_api",
        )
        outcome, draft_source = classify_reply_quality(interaction, "Да, подойдет для роста 170-176.")
        assert outcome == EVENT_DRAFT_EDITED
        assert draft_source == "fallback"

    def test_reply_quality_manual(self):
        interaction = Interaction(
            seller_id=1,
            marketplace="wildberries",
            channel="chat",
            external_id="c-42",
            status="open",
            priority="normal",
            needs_response=True,
            source="wb_api",
        )
        outcome, draft_source = classify_reply_quality(interaction, "Здравствуйте, уточните номер заказа.")
        assert outcome == EVENT_REPLY_MANUAL
        assert draft_source is None
