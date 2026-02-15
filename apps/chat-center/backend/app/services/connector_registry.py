"""Connector registry for marketplace channel connectors.

This module provides:
- Registry pattern for connector classes
- Factory function to instantiate connectors
- Auto-registration of built-in connectors (WB, Ozon)

Usage:
    # Get a connector instance
    connector = get_connector("wildberries", "review", api_key="...")

    # Register a custom connector
    register_connector("yandex", "chat", YandexChatConnector)
"""

import logging
from typing import Any, Dict, Optional, Type

from app.services.base_connector import BaseChannelConnector

logger = logging.getLogger(__name__)

# Global registry: (marketplace, channel) -> Connector class
_CONNECTOR_REGISTRY: Dict[tuple[str, str], Type[BaseChannelConnector]] = {}


def register_connector(
    marketplace: str,
    channel: str,
    connector_class: Type[BaseChannelConnector],
) -> None:
    """Register a connector class for a specific marketplace and channel.

    Args:
        marketplace: Marketplace identifier (e.g., "wildberries", "ozon")
        channel: Communication channel (e.g., "chat", "review", "question")
        connector_class: Connector class (must inherit from BaseChannelConnector)

    Raises:
        TypeError: If connector_class doesn't inherit from BaseChannelConnector
    """
    if not issubclass(connector_class, BaseChannelConnector):
        raise TypeError(
            f"{connector_class.__name__} must inherit from BaseChannelConnector"
        )

    key = (marketplace.lower(), channel.lower())
    _CONNECTOR_REGISTRY[key] = connector_class
    logger.debug(
        "Registered connector: %s -> %s",
        key,
        connector_class.__name__,
    )


def get_connector(
    marketplace: str,
    channel: str,
    *,
    api_key: Optional[str] = None,
    client_id: Optional[str] = None,
    **kwargs: Any,
) -> BaseChannelConnector:
    """Factory function to instantiate a connector.

    Args:
        marketplace: Marketplace identifier (e.g., "wildberries", "ozon")
        channel: Communication channel (e.g., "chat", "review", "question")
        api_key: API key/token for authentication (required for most connectors)
        client_id: Client ID (required for Ozon)
        **kwargs: Additional connector-specific parameters

    Returns:
        Instantiated connector instance

    Raises:
        ValueError: If marketplace or channel is unknown
        TypeError: If required credentials are missing

    Examples:
        >>> connector = get_connector("wildberries", "review", api_key="...")
        >>> items = await connector.list_items(skip=0, take=100)
    """
    key = (marketplace.lower(), channel.lower())

    if key not in _CONNECTOR_REGISTRY:
        raise ValueError(
            f"Unknown connector: marketplace={marketplace}, channel={channel}. "
            f"Available: {list(_CONNECTOR_REGISTRY.keys())}"
        )

    connector_class = _CONNECTOR_REGISTRY[key]

    # Instantiate connector with appropriate credentials
    # Each connector has its own __init__ signature, so we pass all params
    init_params: Dict[str, Any] = {}
    if api_key:
        # All WB connectors use "api_token" parameter
        if marketplace.lower() == "wildberries":
            init_params["api_token"] = api_key
        else:
            init_params["api_key"] = api_key
    if client_id:
        init_params["client_id"] = client_id

    init_params.update(kwargs)

    try:
        return connector_class(**init_params)
    except TypeError as e:
        raise TypeError(
            f"Failed to instantiate {connector_class.__name__}: {e}. "
            f"Check that required credentials are provided."
        ) from e


def list_registered_connectors() -> list[tuple[str, str, str]]:
    """List all registered connectors.

    Returns:
        List of tuples: (marketplace, channel, connector_class_name)
    """
    return [
        (marketplace, channel, cls.__name__)
        for (marketplace, channel), cls in _CONNECTOR_REGISTRY.items()
    ]


# Auto-register built-in connectors on module import
def _auto_register_connectors() -> None:
    """Auto-register all built-in connectors.

    This function is called automatically when the module is imported.
    It registers WB and Ozon connectors for all supported channels.
    """
    try:
        from app.services.wb_connector import WBConnector
        register_connector("wildberries", "chat", WBConnector)
    except ImportError:
        logger.warning("WBConnector not available for auto-registration")

    try:
        from app.services.wb_feedbacks_connector import WBFeedbacksConnector
        register_connector("wildberries", "review", WBFeedbacksConnector)
    except ImportError:
        logger.warning("WBFeedbacksConnector not available for auto-registration")

    try:
        from app.services.wb_questions_connector import WBQuestionsConnector
        register_connector("wildberries", "question", WBQuestionsConnector)
    except ImportError:
        logger.warning("WBQuestionsConnector not available for auto-registration")

    try:
        from app.services.ozon_connector import OzonConnector
        register_connector("ozon", "chat", OzonConnector)
    except ImportError:
        logger.warning("OzonConnector not available for auto-registration")


# Run auto-registration when module is imported
_auto_register_connectors()
