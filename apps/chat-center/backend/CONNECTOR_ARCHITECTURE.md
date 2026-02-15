# Connector Architecture Diagram

## Overview

This document visualizes the BaseConnector architecture implemented in MVP-012.

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                        Application Layer                        │
│  (interaction_ingest.py, sync.py, API endpoints)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ Uses factory to get connectors
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Connector Registry                           │
│  (connector_registry.py)                                        │
│                                                                 │
│  • Factory: get_connector(marketplace, channel, credentials)   │
│  • Registry: {(marketplace, channel) -> ConnectorClass}        │
│  • Auto-registration on import                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │ Returns instance of
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BaseChannelConnector                           │
│  (base_connector.py)                                            │
│                                                                 │
│  Abstract Interface:                                            │
│  • marketplace: str                                             │
│  • channel: str                                                 │
│  • list_items() → Dict[str, Any]  [REQUIRED]                   │
│  • send_reply() → Dict[str, Any]  [optional]                   │
│  • mark_read() → bool             [optional]                   │
│  • get_updates() → Dict[str, Any] [optional]                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Inherited by
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Concrete Connectors                            │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │  WBConnector     │  │ OzonConnector    │                    │
│  │  (chat)          │  │ (chat)           │                    │
│  ├──────────────────┤  ├──────────────────┤                    │
│  │ marketplace="wb" │  │ marketplace="oz" │                    │
│  │ channel="chat"   │  │ channel="chat"   │                    │
│  └──────────────────┘  └──────────────────┘                    │
│                                                                 │
│  ┌────────────────────┐  ┌────────────────────┐                │
│  │ WBFeedbacksConn.   │  │ WBQuestionsConn.   │                │
│  │ (review)           │  │ (question)         │                │
│  ├────────────────────┤  ├────────────────────┤                │
│  │ marketplace="wb"   │  │ marketplace="wb"   │                │
│  │ channel="review"   │  │ channel="question" │                │
│  └────────────────────┘  └────────────────────┘                │
└────────────────────────┬────────────────────────────────────────┘
                         │ Calls marketplace APIs
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    External APIs                                │
│                                                                 │
│  • WB Chat API:      /api/v1/seller/events                     │
│  • WB Feedbacks API: /api/v1/feedbacks                         │
│  • WB Questions API: /api/v1/questions                         │
│  • Ozon Chat API:    /v1/chat/updates                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Factory Pattern Flow

```
┌──────────────────────────────────────────────────────────────┐
│ Application code needs a connector                           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────────────────────┐
  │ get_connector("wildberries", "review", api_key="...")    │
  └────────────────────┬─────────────────────────────────────┘
                       │
                       ▼
       ┌───────────────────────────────────────┐
       │ Look up in registry:                  │
       │ ("wildberries", "review")             │
       │   ↓                                    │
       │ WBFeedbacksConnector                  │
       └────────────────┬──────────────────────┘
                        │
                        ▼
         ┌──────────────────────────────────────┐
         │ Instantiate with credentials:        │
         │ WBFeedbacksConnector(api_token="...") │
         └────────────────┬─────────────────────┘
                          │
                          ▼
           ┌──────────────────────────────────┐
           │ Return connector instance        │
           │ (type: BaseChannelConnector)     │
           └────────────────┬─────────────────┘
                            │
                            ▼
              ┌─────────────────────────────────┐
              │ Application uses unified API:   │
              │ await connector.list_items()    │
              │ await connector.send_reply()    │
              └─────────────────────────────────┘
```

---

## Connector Registry Internals

```python
_CONNECTOR_REGISTRY = {
    ("wildberries", "chat"):     WBConnector,
    ("wildberries", "review"):   WBFeedbacksConnector,
    ("wildberries", "question"): WBQuestionsConnector,
    ("ozon", "chat"):            OzonConnector,
}

def get_connector(marketplace, channel, **credentials):
    key = (marketplace.lower(), channel.lower())
    connector_class = _CONNECTOR_REGISTRY[key]
    return connector_class(**credentials)
```

---

## Inheritance Hierarchy

```
ABC (Python built-in)
 │
 ├── BaseChannelConnector (abstract)
 │    │
 │    ├── WBConnector
 │    │    └── marketplace = "wildberries"
 │    │    └── channel = "chat"
 │    │
 │    ├── WBFeedbacksConnector
 │    │    └── marketplace = "wildberries"
 │    │    └── channel = "review"
 │    │
 │    ├── WBQuestionsConnector
 │    │    └── marketplace = "wildberries"
 │    │    └── channel = "question"
 │    │
 │    └── OzonConnector
 │         └── marketplace = "ozon"
 │         └── channel = "chat"
```

---

## Method Dispatch Pattern

```
Application calls:
  connector.list_items(skip=0, take=100)

  ▼ Dispatch based on connector type

WBFeedbacksConnector:
  list_items() → list_feedbacks()
    ↓
  /api/v1/feedbacks?skip=0&take=100

WBQuestionsConnector:
  list_items() → list_questions()
    ↓
  /api/v1/questions?skip=0&take=100

WBConnector:
  list_items() → fetch_messages_as_chats()
    ↓
  /api/v1/seller/events

OzonConnector:
  list_items() → list_chats()
    ↓
  /v1/chat/list
```

---

## Backwards Compatibility Layer

```
┌────────────────────────────────────────────────────────┐
│ OLD CODE (still works)                                 │
├────────────────────────────────────────────────────────┤
│ connector = await get_wb_feedbacks_connector_for_...  │
│ items = await connector.list_feedbacks()              │
└──────────────────────┬─────────────────────────────────┘
                       │ Both methods exist
                       ▼
        ┌──────────────────────────────────┐
        │  WBFeedbacksConnector            │
        ├──────────────────────────────────┤
        │  list_items()  ←─ NEW            │
        │      ↓ delegates to              │
        │  list_feedbacks() ←─ OLD         │
        │      ↓ calls API                 │
        │  _request(GET, /feedbacks)       │
        └──────────────────────────────────┘
                       │ Returns same data
                       ▼
┌────────────────────────────────────────────────────────┐
│ NEW CODE (recommended)                                 │
├────────────────────────────────────────────────────────┤
│ connector = get_connector("wildberries", "review", ...) │
│ items = await connector.list_items()                   │
└────────────────────────────────────────────────────────┘
```

---

## Extensibility: Adding a New Marketplace

### Step 1: Implement Connector

```python
from app.services.base_connector import BaseChannelConnector

class AliExpressReviewsConnector(BaseChannelConnector):
    marketplace = "aliexpress"
    channel = "review"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
        # Call AliExpress API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.aliexpress.com/reviews",
                params={"offset": skip, "limit": take},
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            return response.json()

    async def send_reply(self, *, item_id: str, text: str, **kwargs):
        # Post reply to AliExpress
        pass
```

### Step 2: Register

```python
from app.services.connector_registry import register_connector

register_connector("aliexpress", "review", AliExpressReviewsConnector)
```

### Step 3: Use

```python
connector = get_connector("aliexpress", "review", api_key="...")
reviews = await connector.list_items(skip=0, take=100)
```

**That's it!** No changes to application code needed.

---

## Registry Auto-Registration

When `connector_registry.py` is imported, it automatically runs:

```python
def _auto_register_connectors():
    try:
        from app.services.wb_connector import WBConnector
        register_connector("wildberries", "chat", WBConnector)
    except ImportError:
        logger.warning("WBConnector not available")

    try:
        from app.services.wb_feedbacks_connector import WBFeedbacksConnector
        register_connector("wildberries", "review", WBFeedbacksConnector)
    except ImportError:
        logger.warning("WBFeedbacksConnector not available")

    # ... similar for other connectors

_auto_register_connectors()  # Runs on import
```

This ensures connectors are available as soon as the module is imported,
without requiring manual registration in application code.

---

## Type Safety

```python
# Type hints ensure IDE auto-completion and type checking

from app.services.connector_registry import get_connector
from app.services.base_connector import BaseChannelConnector

# Returns BaseChannelConnector (base type)
connector: BaseChannelConnector = get_connector(
    "wildberries",
    "review",
    api_key="..."
)

# IDE knows connector has these methods:
await connector.list_items()   # ✓ Auto-complete works
await connector.send_reply()   # ✓ Auto-complete works

# But also allows calling concrete methods:
if hasattr(connector, "list_feedbacks"):
    await connector.list_feedbacks()  # ✓ Backwards compat
```

---

## Error Handling

```python
# Unknown marketplace
try:
    connector = get_connector("amazon", "chat", api_key="...")
except ValueError as e:
    print(e)  # "Unknown connector: marketplace=amazon, channel=chat"

# Unknown channel
try:
    connector = get_connector("wildberries", "email", api_key="...")
except ValueError as e:
    print(e)  # "Unknown connector: marketplace=wildberries, channel=email"

# Missing credentials
try:
    connector = get_connector("wildberries", "chat")  # No api_key
except TypeError as e:
    print(e)  # "Failed to instantiate WBConnector: missing required..."

# Optional method not implemented
connector = get_connector("wildberries", "review", api_key="...")
try:
    await connector.mark_read(item_id="123")
except NotImplementedError as e:
    print(e)  # "WBFeedbacksConnector does not implement mark_read"
```

---

## Comparison: Before vs After

### Before (Multiple Factory Functions)

```python
# Different import for each marketplace/channel
from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller
from app.services.wb_questions_connector import get_wb_questions_connector_for_seller
from app.services.ozon_connector import get_connector_for_seller

# Different method names for same operation
wb_fb = await get_wb_feedbacks_connector_for_seller(seller_id, db)
items1 = await wb_fb.list_feedbacks()  # Feedbacks

wb_q = await get_wb_questions_connector_for_seller(seller_id, db)
items2 = await wb_q.list_questions()  # Questions

ozon = await get_connector_for_seller(seller_id, db)
items3 = await ozon.list_chats()  # Chats

# Hard to write marketplace-agnostic code
```

### After (Unified Interface)

```python
# Single import, single pattern
from app.services.connector_registry import get_connector

# Same method name for all channels
connector1 = get_connector("wildberries", "review", api_key=token)
items1 = await connector1.list_items()

connector2 = get_connector("wildberries", "question", api_key=token)
items2 = await connector2.list_items()

connector3 = get_connector("ozon", "chat", client_id=cid, api_key=token)
items3 = await connector3.list_items()

# Easy to write marketplace-agnostic code
def ingest_channel(marketplace: str, channel: str, credentials):
    connector = get_connector(marketplace, channel, **credentials)
    return await connector.list_items()
```

---

## Summary

The BaseConnector architecture provides:

1. **Unified Interface** - Same methods across all marketplaces
2. **Factory Pattern** - Single entry point for all connectors
3. **Type Safety** - IDE auto-completion + type checking
4. **Extensibility** - Easy to add new marketplaces/channels
5. **Backwards Compatibility** - All existing code continues to work
6. **Auto-Registration** - No manual setup required
7. **Error Handling** - Clear error messages for common issues

This architecture scales from 2 marketplaces to 20+ without code changes.
