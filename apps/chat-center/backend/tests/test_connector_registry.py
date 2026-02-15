"""Tests for connector registry and factory."""

import pytest

from app.services.connector_registry import (
    get_connector,
    list_registered_connectors,
    register_connector,
)
from app.services.base_connector import BaseChannelConnector
from app.services.wb_connector import WBConnector
from app.services.wb_feedbacks_connector import WBFeedbacksConnector
from app.services.wb_questions_connector import WBQuestionsConnector
from app.services.ozon_connector import OzonConnector


class TestConnectorRegistry:
    """Test connector registry functionality."""

    def test_list_registered_connectors(self):
        """Test that all built-in connectors are auto-registered."""
        connectors = list_registered_connectors()

        # Should have at least 4 connectors (WB chat/review/question, Ozon chat)
        assert len(connectors) >= 4

        # Convert to dict for easier testing
        registry = {(mp, ch): cls for mp, ch, cls in connectors}

        # Check WB connectors
        assert ("wildberries", "chat") in registry
        assert registry[("wildberries", "chat")] == "WBConnector"

        assert ("wildberries", "review") in registry
        assert registry[("wildberries", "review")] == "WBFeedbacksConnector"

        assert ("wildberries", "question") in registry
        assert registry[("wildberries", "question")] == "WBQuestionsConnector"

        # Check Ozon connector
        assert ("ozon", "chat") in registry
        assert registry[("ozon", "chat")] == "OzonConnector"

    def test_get_wb_chat_connector(self):
        """Test factory returns correct WB chat connector."""
        connector = get_connector("wildberries", "chat", api_key="test.token.here")

        assert isinstance(connector, WBConnector)
        assert isinstance(connector, BaseChannelConnector)
        assert connector.marketplace == "wildberries"
        assert connector.channel == "chat"

    def test_get_wb_review_connector(self):
        """Test factory returns correct WB review connector."""
        # WBFeedbacksConnector expects api_token, so pass it via kwargs
        connector = get_connector("wildberries", "review", api_token="test_token")

        assert isinstance(connector, WBFeedbacksConnector)
        assert isinstance(connector, BaseChannelConnector)
        assert connector.marketplace == "wildberries"
        assert connector.channel == "review"

    def test_get_wb_question_connector(self):
        """Test factory returns correct WB question connector."""
        # WBQuestionsConnector expects api_token, so pass it via kwargs
        connector = get_connector("wildberries", "question", api_token="test_token")

        assert isinstance(connector, WBQuestionsConnector)
        assert isinstance(connector, BaseChannelConnector)
        assert connector.marketplace == "wildberries"
        assert connector.channel == "question"

    def test_get_ozon_chat_connector(self):
        """Test factory returns correct Ozon chat connector."""
        connector = get_connector(
            "ozon",
            "chat",
            client_id="123456",
            api_key="test_key",
        )

        assert isinstance(connector, OzonConnector)
        assert isinstance(connector, BaseChannelConnector)
        assert connector.marketplace == "ozon"
        assert connector.channel == "chat"

    def test_get_unknown_marketplace_raises(self):
        """Test that unknown marketplace raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_connector("amazon", "chat", api_key="test")

        assert "Unknown connector" in str(exc_info.value)
        assert "amazon" in str(exc_info.value)

    def test_get_unknown_channel_raises(self):
        """Test that unknown channel raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_connector("wildberries", "email", api_key="test")

        assert "Unknown connector" in str(exc_info.value)
        assert "email" in str(exc_info.value)

    def test_case_insensitive_lookup(self):
        """Test that marketplace/channel lookup is case-insensitive."""
        # WBConnector chat channel has api_key -> api_token mapping
        connector1 = get_connector("Wildberries", "Chat", api_key="test.token.here")
        connector2 = get_connector("WILDBERRIES", "CHAT", api_key="test.token.here")

        assert isinstance(connector1, WBConnector)
        assert isinstance(connector2, WBConnector)

    def test_register_custom_connector(self):
        """Test registering a custom connector."""

        class CustomConnector(BaseChannelConnector):
            marketplace = "custom"
            channel = "test"

            def __init__(self, api_key: str):
                self.api_key = api_key

            async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
                return {"data": []}

        register_connector("custom", "test", CustomConnector)

        connector = get_connector("custom", "test", api_key="test")
        assert isinstance(connector, CustomConnector)

    def test_register_non_base_connector_raises(self):
        """Test that registering non-BaseChannelConnector raises TypeError."""

        class NotAConnector:
            pass

        with pytest.raises(TypeError) as exc_info:
            register_connector("invalid", "chat", NotAConnector)

        assert "must inherit from BaseChannelConnector" in str(exc_info.value)

    def test_missing_credentials_raises(self):
        """Test that missing credentials raises informative error."""
        # WB Chat requires api_token (mapped from api_key)
        # If we don't provide it, __init__ will fail
        with pytest.raises(TypeError) as exc_info:
            get_connector("wildberries", "chat")  # No api_key

        assert "Failed to instantiate" in str(exc_info.value)
