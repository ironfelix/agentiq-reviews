# MVP-012: BaseConnector Interface + Factory Dispatch

## Implementation Summary

This document describes the implementation of MVP-012, which introduces a unified BaseConnector architecture for all marketplace channel connectors in AgentIQ.

### Objective

Refactor existing connectors (WB, Ozon) into a unified interface with factory dispatch pattern, enabling:
- Consistent API across all marketplace integrations
- Easy addition of new marketplaces/channels
- Type-safe connector instantiation
- Backwards compatibility with existing code

---

## Architecture Overview

### Components Created

1. **`app/services/base_connector.py`** - Abstract base class
2. **`app/services/connector_registry.py`** - Registry + factory pattern
3. **`tests/test_connector_registry.py`** - Registry/factory tests
4. **`tests/test_base_connector.py`** - Interface compliance tests

### Connectors Adapted

All existing connectors now inherit from `BaseChannelConnector`:

1. **`WBConnector`** (chat) - `app/services/wb_connector.py`
2. **`WBFeedbacksConnector`** (review) - `app/services/wb_feedbacks_connector.py`
3. **`WBQuestionsConnector`** (question) - `app/services/wb_questions_connector.py`
4. **`OzonConnector`** (chat) - `app/services/ozon_connector.py`

---

## BaseChannelConnector Interface

```python
class BaseChannelConnector(ABC):
    marketplace: str  # "wildberries", "ozon"
    channel: str      # "chat", "review", "question"

    @abstractmethod
    async def list_items(
        self, *, skip: int = 0, take: int = 100, **kwargs
    ) -> Dict[str, Any]:
        """List items (chats/reviews/questions)."""

    async def send_reply(
        self, *, item_id: str, text: str, **kwargs
    ) -> Dict[str, Any]:
        """Send reply (optional, raises NotImplementedError if N/A)."""

    async def mark_read(
        self, *, item_id: str, **kwargs
    ) -> bool:
        """Mark as read/viewed (optional)."""

    async def get_updates(
        self, *, since_cursor: Optional[str] = None, limit: int = 50, **kwargs
    ) -> Dict[str, Any]:
        """Incremental sync via cursor (optional)."""
```

### Design Principles

1. **Not all methods are required** - Only `list_items` is abstract. Other methods raise `NotImplementedError` by default.
2. **Channel-specific parameters** - Use `**kwargs` to pass channel-specific filters (e.g., `is_answered`, `nm_id`).
3. **Consistent return structure** - All methods return `Dict[str, Any]` with predictable keys.

---

## Connector Registry

### Auto-Registration

Built-in connectors are auto-registered on module import:

```python
from app.services.connector_registry import get_connector

# Auto-registered:
# - ("wildberries", "chat") -> WBConnector
# - ("wildberries", "review") -> WBFeedbacksConnector
# - ("wildberries", "question") -> WBQuestionsConnector
# - ("ozon", "chat") -> OzonConnector
```

### Factory Usage

```python
# Get a connector instance
connector = get_connector(
    "wildberries",
    "review",
    api_key="your_token"
)

# Use unified interface
items = await connector.list_items(skip=0, take=100)
await connector.send_reply(item_id="123", text="Thanks!")
```

### Manual Registration

```python
from app.services.connector_registry import register_connector

class YandexChatConnector(BaseChannelConnector):
    marketplace = "yandex"
    channel = "chat"
    # ... implementation

register_connector("yandex", "chat", YandexChatConnector)
```

---

## Backwards Compatibility

### All existing methods preserved

Each connector retains its original methods:

| Connector | Old Methods | New Methods (BaseConnector) |
|-----------|-------------|----------------------------|
| `WBFeedbacksConnector` | `list_feedbacks()`, `answer_feedback()` | `list_items()`, `send_reply()` |
| `WBQuestionsConnector` | `list_questions()`, `patch_question()` | `list_items()`, `send_reply()`, `mark_read()` |
| `WBConnector` | `fetch_messages()`, `send_message()` | `list_items()`, `send_reply()`, `get_updates()` |
| `OzonConnector` | `list_chats()`, `send_message()` | `list_items()`, `send_reply()`, `get_updates()` |

### Migration Strategy

**Existing code continues to work without changes:**

```python
# OLD (still works)
from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller
connector = await get_wb_feedbacks_connector_for_seller(seller_id, db)
items = await connector.list_feedbacks(skip=0, take=100)

# NEW (recommended)
from app.services.connector_registry import get_connector
from app.services.encryption import decrypt_credentials

api_token = decrypt_credentials(seller.api_key_encrypted)
connector = get_connector("wildberries", "review", api_key=api_token)
items = await connector.list_items(skip=0, take=100)
```

---

## Implementation Details

### 1. BaseConnector (`base_connector.py`)

**Abstract Methods:**
- `list_items()` - REQUIRED for all connectors

**Optional Methods (raise NotImplementedError by default):**
- `send_reply()` - Not all channels support replies
- `mark_read()` - Not all APIs provide mark-as-read
- `get_updates()` - Only for cursor-based incremental sync

**Attributes:**
- `marketplace: str` - Marketplace identifier
- `channel: str` - Communication channel

### 2. Connector Registry (`connector_registry.py`)

**Global Registry:**
```python
_CONNECTOR_REGISTRY: Dict[tuple[str, str], Type[BaseChannelConnector]]
```

**Public API:**
- `register_connector(marketplace, channel, connector_class)` - Manual registration
- `get_connector(marketplace, channel, *, api_key, client_id, **kwargs)` - Factory
- `list_registered_connectors()` - List all available connectors

**Auto-Registration:**
- Runs on module import via `_auto_register_connectors()`
- Safe import handling (logs warnings if connectors unavailable)
- Case-insensitive lookup (`"Wildberries"` == `"wildberries"`)

### 3. Connector Adaptations

Each connector adds:

1. **Class attributes:**
   ```python
   marketplace = "wildberries"
   channel = "review"
   ```

2. **BaseConnector interface methods:**
   ```python
   async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
       # Delegates to existing list_feedbacks/list_questions/etc.
       return await self.list_feedbacks(skip=skip, take=take, **kwargs)
   ```

3. **Backwards compatibility:**
   - All original methods remain unchanged
   - New methods delegate to old methods

---

## Test Coverage

### `test_connector_registry.py`

1. **Registry Tests:**
   - All 4 built-in connectors auto-registered
   - Correct connector class for each (marketplace, channel)

2. **Factory Tests:**
   - `get_connector()` returns correct instance
   - Instances inherit from `BaseChannelConnector`
   - Marketplace/channel attributes set correctly

3. **Error Handling:**
   - Unknown marketplace raises `ValueError`
   - Unknown channel raises `ValueError`
   - Missing credentials raises `TypeError`

4. **Edge Cases:**
   - Case-insensitive lookup
   - Custom connector registration
   - Non-BaseConnector registration fails

### `test_base_connector.py`

1. **Abstract Interface:**
   - Cannot instantiate `BaseChannelConnector` directly
   - Concrete connectors must implement `list_items()`
   - Optional methods raise `NotImplementedError` by default

2. **Concrete Connector Compliance:**
   - All 4 connectors implement required methods
   - `marketplace` and `channel` attributes set
   - Optional methods either implemented or raise correctly

3. **Backwards Compatibility:**
   - Old method names still exist
   - Old methods callable without errors

---

## Usage Examples

### Example 1: Fetch Reviews

```python
from app.services.connector_registry import get_connector

# Get connector
connector = get_connector("wildberries", "review", api_key=api_token)

# Fetch reviews
result = await connector.list_items(
    skip=0,
    take=100,
    is_answered=False,
    order="dateDesc",
)

reviews = result.get("data", {}).get("feedbacks", [])
```

### Example 2: Answer Question

```python
# Get connector
connector = get_connector("wildberries", "question", api_key=api_token)

# Send reply
result = await connector.send_reply(
    item_id="question_123",
    text="Размерная сетка в описании товара",
    state="wbRu",
)

assert result["success"] is True
```

### Example 3: Incremental Chat Sync

```python
# Get connector
connector = get_connector("wildberries", "chat", api_key=api_token)

# Get updates since last cursor
result = await connector.get_updates(
    since_cursor="12345",
    limit=50,
)

new_messages = result["items"]
next_cursor = result["next_cursor"]
has_more = result["has_more"]
```

### Example 4: Multi-Marketplace Support

```python
def get_seller_connector(seller):
    """Factory for seller-specific connector."""
    marketplace = seller.marketplace.lower()
    channel = "review"

    if marketplace == "wildberries":
        api_key = decrypt_credentials(seller.api_key_encrypted)
        return get_connector(marketplace, channel, api_key=api_key)
    elif marketplace == "ozon":
        api_key = decrypt_credentials(seller.api_key_encrypted)
        return get_connector(
            marketplace,
            channel,
            client_id=seller.client_id,
            api_key=api_key,
        )
    else:
        raise ValueError(f"Unsupported marketplace: {marketplace}")
```

---

## Migration Guide

### For New Code

**Use the registry pattern:**

```python
from app.services.connector_registry import get_connector

connector = get_connector("wildberries", "review", api_key=token)
items = await connector.list_items(skip=0, take=100)
```

**Benefits:**
- Type-safe (returns `BaseChannelConnector`)
- Marketplace-agnostic (easy to switch)
- Auto-completion in IDE

### For Existing Code

**No migration required!** All existing factory functions still work:

```python
# These still work
connector = await get_wb_feedbacks_connector_for_seller(seller_id, db)
connector = await get_wb_questions_connector_for_seller(seller_id, db)
connector = await get_wb_connector_for_seller(seller_id, db)
```

**Optional refactor (recommended for new features):**

```python
# OLD
from app.services.wb_feedbacks_connector import get_wb_feedbacks_connector_for_seller
connector = await get_wb_feedbacks_connector_for_seller(seller_id, db)

# NEW
from app.services.connector_registry import get_connector
from app.services.encryption import decrypt_credentials

result = await db.execute(select(Seller).where(Seller.id == seller_id))
seller = result.scalar_one()
api_token = decrypt_credentials(seller.api_key_encrypted)

connector = get_connector(seller.marketplace, "review", api_key=api_token)
```

---

## Future Enhancements

### 1. Add New Marketplace

```python
# 1. Implement connector
class AliExpressChatConnector(BaseChannelConnector):
    marketplace = "aliexpress"
    channel = "chat"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def list_items(self, *, skip: int = 0, take: int = 100, **kwargs):
        # Implementation
        pass

# 2. Register
from app.services.connector_registry import register_connector
register_connector("aliexpress", "chat", AliExpressChatConnector)

# 3. Use
connector = get_connector("aliexpress", "chat", api_key=token)
```

### 2. Add New Channel to Existing Marketplace

```python
# Add Ozon Reviews support
class OzonReviewsConnector(BaseChannelConnector):
    marketplace = "ozon"
    channel = "review"
    # ... implementation

register_connector("ozon", "review", OzonReviewsConnector)
```

### 3. Unified Ingestion Pipeline

```python
async def ingest_items_unified(
    db,
    seller_id: int,
    marketplace: str,
    channel: str,
) -> IngestStats:
    """Unified ingestion using connector registry."""
    # Get seller
    seller = await get_seller(db, seller_id)

    # Get connector
    api_token = decrypt_credentials(seller.api_key_encrypted)
    connector = get_connector(
        marketplace,
        channel,
        api_key=api_token,
        client_id=seller.client_id if marketplace == "ozon" else None,
    )

    # Fetch items
    result = await connector.list_items(skip=0, take=500)

    # Ingest to interactions table
    # ... (channel-agnostic processing)
```

---

## Verification Checklist

- [x] `base_connector.py` created with abstract interface
- [x] `connector_registry.py` created with factory + auto-registration
- [x] `WBConnector` adapted (chat)
- [x] `WBFeedbacksConnector` adapted (review)
- [x] `WBQuestionsConnector` adapted (question)
- [x] `OzonConnector` adapted (chat)
- [x] `test_connector_registry.py` created (12 test cases)
- [x] `test_base_connector.py` created (10 test cases)
- [x] All connectors have `marketplace` and `channel` attributes
- [x] All connectors implement `list_items()`
- [x] Backwards compatibility preserved (old methods still work)
- [x] Auto-registration works on module import
- [x] Factory handles credentials correctly (api_key, client_id)
- [x] Type hints everywhere

---

## Running Tests

```bash
cd apps/chat-center/backend
source venv/bin/activate

# Run registry tests
pytest tests/test_connector_registry.py -v

# Run base connector tests
pytest tests/test_base_connector.py -v

# Run all tests
pytest tests/ -v
```

Expected output:
- `test_connector_registry.py`: 12 passed
- `test_base_connector.py`: 10 passed

---

## Documentation

### Code Documentation

- All modules have comprehensive docstrings
- All methods have type hints
- All classes have usage examples in docstrings

### Architecture Docs

Update the following docs:
- `docs/architecture/architecture.md` - Add connector registry pattern
- `docs/architecture/DATA_LAYER.md` - Update connector section
- `mvp/PROJECT_SUMMARY.md` - Add connector architecture

---

## Summary

This implementation introduces a **unified BaseConnector architecture** that:

1. ✅ Provides consistent interface across all marketplace integrations
2. ✅ Enables easy addition of new marketplaces/channels
3. ✅ Maintains 100% backwards compatibility with existing code
4. ✅ Uses factory pattern for type-safe instantiation
5. ✅ Auto-registers all built-in connectors
6. ✅ Has comprehensive test coverage (22 test cases)
7. ✅ Follows single responsibility principle (each connector = one channel)
8. ✅ Scales to future marketplaces (AliExpress, Yandex, etc.)

**No breaking changes.** All existing code continues to work without modification.

**Recommended next step:** Gradually migrate existing code to use `get_connector()` instead of individual factory functions (e.g., `get_wb_feedbacks_connector_for_seller()`).
