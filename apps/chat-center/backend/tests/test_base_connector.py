"""Tests for BaseChannelConnector abstract interface."""

import pytest

from app.services.base_connector import BaseChannelConnector


class TestBaseConnector:
    """Test BaseChannelConnector abstract methods."""

    def test_cannot_instantiate_base_connector(self):
        """Test that BaseChannelConnector cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseChannelConnector()

    def test_concrete_connector_must_implement_list_items(self):
        """Test that concrete connector must implement list_items."""

        class IncompleteConnector(BaseChannelConnector):
            marketplace = "test"
            channel = "test"

        # Since list_items is @abstractmethod, instantiation should fail
        with pytest.raises(TypeError) as exc_info:
            connector = IncompleteConnector()

        assert "abstract" in str(exc_info.value).lower()

    def test_send_reply_raises_by_default(self):
        """Test that send_reply raises NotImplementedError if not overridden."""

        class MinimalConnector(BaseChannelConnector):
            marketplace = "test"
            channel = "test"

            async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
                return {"data": []}

        connector = MinimalConnector()

        with pytest.raises(NotImplementedError) as exc_info:
            import asyncio

            asyncio.run(connector.send_reply(item_id="123", text="test"))

        assert "does not implement send_reply" in str(exc_info.value)

    def test_mark_read_raises_by_default(self):
        """Test that mark_read raises NotImplementedError if not overridden."""

        class MinimalConnector(BaseChannelConnector):
            marketplace = "test"
            channel = "test"

            async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
                return {"data": []}

        connector = MinimalConnector()

        with pytest.raises(NotImplementedError) as exc_info:
            import asyncio

            asyncio.run(connector.mark_read(item_id="123"))

        assert "does not implement mark_read" in str(exc_info.value)

    def test_get_updates_raises_by_default(self):
        """Test that get_updates raises NotImplementedError if not overridden."""

        class MinimalConnector(BaseChannelConnector):
            marketplace = "test"
            channel = "test"

            async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
                return {"data": []}

        connector = MinimalConnector()

        with pytest.raises(NotImplementedError) as exc_info:
            import asyncio

            asyncio.run(connector.get_updates(since_cursor=None, limit=50))

        assert "does not implement get_updates" in str(exc_info.value)


class TestConcreteConnectors:
    """Test that all existing connectors implement required methods."""

    @pytest.mark.asyncio
    async def test_wb_chat_implements_interface(self):
        """Test that WBConnector implements all required methods."""
        from app.services.wb_connector import WBConnector

        connector = WBConnector(api_token="test.token.here")

        # Check attributes
        assert connector.marketplace == "wildberries"
        assert connector.channel == "chat"

        # Check that methods are implemented (not testing actual API calls)
        assert hasattr(connector, "list_items")
        assert hasattr(connector, "send_reply")
        assert hasattr(connector, "get_updates")

        # mark_read is not implemented for WB Chat (not in API)
        with pytest.raises(NotImplementedError):
            await connector.mark_read(item_id="test")

    @pytest.mark.asyncio
    async def test_wb_feedbacks_implements_interface(self):
        """Test that WBFeedbacksConnector implements required methods."""
        from app.services.wb_feedbacks_connector import WBFeedbacksConnector

        connector = WBFeedbacksConnector(api_token="test_token")

        # Check attributes
        assert connector.marketplace == "wildberries"
        assert connector.channel == "review"

        # Check that methods are implemented
        assert hasattr(connector, "list_items")
        assert hasattr(connector, "send_reply")

        # mark_read is not implemented for WB Feedbacks (not in API)
        with pytest.raises(NotImplementedError):
            await connector.mark_read(item_id="test")

        # get_updates is not implemented (feedbacks use skip/take pagination)
        with pytest.raises(NotImplementedError):
            await connector.get_updates(since_cursor=None)

    @pytest.mark.asyncio
    async def test_wb_questions_implements_interface(self):
        """Test that WBQuestionsConnector implements required methods."""
        from app.services.wb_questions_connector import WBQuestionsConnector

        connector = WBQuestionsConnector(api_token="test_token")

        # Check attributes
        assert connector.marketplace == "wildberries"
        assert connector.channel == "question"

        # Check that methods are implemented
        assert hasattr(connector, "list_items")
        assert hasattr(connector, "send_reply")
        assert hasattr(connector, "mark_read")

        # get_updates is not implemented (questions use skip/take pagination)
        with pytest.raises(NotImplementedError):
            await connector.get_updates(since_cursor=None)

    @pytest.mark.asyncio
    async def test_ozon_implements_interface(self):
        """Test that OzonConnector implements required methods."""
        from app.services.ozon_connector import OzonConnector

        connector = OzonConnector(client_id="123", api_key="test")

        # Check attributes
        assert connector.marketplace == "ozon"
        assert connector.channel == "chat"

        # Check that methods are implemented
        assert hasattr(connector, "list_items")
        assert hasattr(connector, "send_reply")
        assert hasattr(connector, "get_updates")

        # mark_read is not implemented for Ozon Chat (not in API)
        with pytest.raises(NotImplementedError):
            await connector.mark_read(item_id="test")


class TestBackwardsCompatibility:
    """Test that old method names still work (backwards compatibility)."""

    @pytest.mark.asyncio
    async def test_wb_feedbacks_old_methods_work(self):
        """Test that old list_feedbacks/answer_feedback still work."""
        from app.services.wb_feedbacks_connector import WBFeedbacksConnector

        connector = WBFeedbacksConnector(api_token="test_token")

        # Old methods should still exist
        assert hasattr(connector, "list_feedbacks")
        assert hasattr(connector, "answer_feedback")

    @pytest.mark.asyncio
    async def test_wb_questions_old_methods_work(self):
        """Test that old list_questions/patch_question still work."""
        from app.services.wb_questions_connector import WBQuestionsConnector

        connector = WBQuestionsConnector(api_token="test_token")

        # Old methods should still exist
        assert hasattr(connector, "list_questions")
        assert hasattr(connector, "patch_question")

    @pytest.mark.asyncio
    async def test_wb_chat_old_methods_work(self):
        """Test that old fetch_messages/send_message still work."""
        from app.services.wb_connector import WBConnector

        connector = WBConnector(api_token="test.token.here")

        # Old methods should still exist
        assert hasattr(connector, "fetch_messages")
        assert hasattr(connector, "send_message")
        assert hasattr(connector, "fetch_chats")
        assert hasattr(connector, "fetch_messages_as_chats")

    @pytest.mark.asyncio
    async def test_ozon_old_methods_work(self):
        """Test that old list_chats/send_message still work."""
        from app.services.ozon_connector import OzonConnector

        connector = OzonConnector(client_id="123", api_key="test")

        # Old methods should still exist
        assert hasattr(connector, "list_chats")
        assert hasattr(connector, "send_message")
        assert hasattr(connector, "_get_updates_internal")
