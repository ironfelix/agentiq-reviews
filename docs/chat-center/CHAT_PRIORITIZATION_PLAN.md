# Chat Prioritization Plan

> Date: 2026-02-10
> Status: Implementation Ready

---

## 1. Bug Diagnosis: Why All Chats Show as "Waiting"

### Root Cause

The bug is in `/agentiq/apps/chat-center/backend/app/tasks/sync.py` in function `_upsert_chat_and_messages()`.

**Problem #1: Initial chat status is always "waiting"**
```python
# Line 300 - Both branches are identical!
chat_status="waiting" if chat_data.get("is_new_chat") else "waiting",
```
This sets ALL new chats to "waiting" regardless of who sent the last message.

**Problem #2: Status update logic only triggers on NEW buyer messages**
```python
# Lines 342-345
if msg["author_type"] == "buyer":
    chat.unread_count += 1
    chat.chat_status = "client-replied" if chat.chat_status == "responded" else "waiting"
```
This only updates `chat_status` when a NEW buyer message arrives. But:
- It never sets `chat_status = "responded"` when a seller message arrives
- It doesn't analyze ALL messages in the chat to determine the correct status
- When syncing existing chats, messages are skipped as duplicates, so status is never updated

**Problem #3: No status update for seller messages during sync**
The sync function only handles buyer messages. When we sync seller messages from the marketplace API, we never update `chat_status` to "responded".

### Evidence

1. In `sync.py:300` - new chats always get `chat_status="waiting"`
2. In `sync.py:343-345` - status only changes on buyer message insert
3. When seller sends a message through our API (`messages.py:153`) it correctly sets `chat_status = "responded"`, but...
4. When we **sync** seller messages from the marketplace (messages seller sent via WB interface), we don't update the status

### Impact

All chats appear in "Ожидают ответа" section because:
- New chats always start as "waiting"
- Seller messages don't trigger status change to "responded"
- Status never transitions correctly

---

## 2. Chat Status Lifecycle (Correct Implementation)

### Status Flow Diagram

```
                    +------------------+
                    |                  |
    New chat ------>|     waiting      |<----+
                    |  (needs reply)   |     |
                    +--------+---------+     |
                             |               |
                    Seller responds          |
                             |               |
                             v               |
                    +------------------+     |
                    |                  |     |
                    |    responded     |-----+
                    |  (we replied)    |     |
                    +--------+---------+     |
                             |               |
                    Customer replies         |
                             |               |
                             v               |
                    +------------------+     |
                    |                  |     |
                    |  client-replied  |-----+
                    | (customer spoke) |
                    +------------------+
```

### Status Definitions

| Status | Meaning | Last Message From | UI Section |
|--------|---------|-------------------|------------|
| `waiting` | Needs our response | Customer (buyer) | Ожидают ответа |
| `responded` | We replied, waiting for customer | Seller | Все сообщения |
| `client-replied` | Customer replied to our response | Customer (after we responded) | Ожидают ответа |
| `auto-response` | AI auto-responded | System/AI | Все сообщения |

### Priority Overlay

| Priority | Condition | UI Section |
|----------|-----------|------------|
| `urgent` | SLA deadline < 30 min OR manual escalation | В работе |
| `high` | SLA deadline < 2 hours OR negative review linked | Ожидают ответа |
| `normal` | Default | Ожидают ответа / Все сообщения |
| `low` | Closed/resolved chats | Все сообщения |

---

## 3. Correct Status Determination Logic

### Algorithm

To correctly determine `chat_status`, analyze ALL messages in the chat:

```python
def determine_chat_status(messages: List[Message]) -> str:
    """
    Determine chat_status based on message history.

    Rules:
    1. Sort messages by sent_at (oldest to newest)
    2. Find the LAST message
    3. If last message from buyer -> "waiting" (or "client-replied" if we responded before)
    4. If last message from seller -> "responded"
    5. If last message from system/AI -> "auto-response"
    """
    if not messages:
        return "waiting"  # No messages = waiting for first contact

    # Sort by timestamp
    sorted_messages = sorted(messages, key=lambda m: m.sent_at)
    last_message = sorted_messages[-1]

    # Determine based on last message author
    if last_message.author_type in ("buyer", "customer"):
        # Check if we ever responded before this message
        seller_messages_before = [
            m for m in sorted_messages[:-1]
            if m.author_type in ("seller", "system")
        ]
        if seller_messages_before:
            return "client-replied"  # Customer replied to our response
        else:
            return "waiting"  # Still waiting for first response

    elif last_message.author_type == "seller":
        return "responded"

    elif last_message.author_type == "system":
        return "auto-response"

    return "waiting"  # Fallback
```

---

## 4. Fix Implementation

### 4.1 Fix in `sync.py` - `_upsert_chat_and_messages()`

**Current broken code (lines 287-345):**
```python
if not chat:
    # Create new chat
    chat = Chat(
        ...
        chat_status="waiting" if chat_data.get("is_new_chat") else "waiting",  # BUG!
        ...
    )
    ...

# Only updates on buyer message
if msg["author_type"] == "buyer":
    chat.unread_count += 1
    chat.chat_status = "client-replied" if chat.chat_status == "responded" else "waiting"
```

**Fixed code:**
```python
async def _upsert_chat_and_messages(db, seller_id: int, marketplace: str, chat_data: dict):
    """
    Upsert chat and its messages to database.

    IMPORTANT: After inserting/updating messages, recalculate chat_status
    based on the last message author.
    """
    external_chat_id = chat_data["external_chat_id"]

    # Find or create chat
    result = await db.execute(
        select(Chat).where(
            and_(
                Chat.seller_id == seller_id,
                Chat.marketplace_chat_id == external_chat_id
            )
        )
    )
    chat = result.scalar_one_or_none()

    if not chat:
        # Create new chat with temporary status
        chat = Chat(
            seller_id=seller_id,
            marketplace=marketplace,
            marketplace_chat_id=external_chat_id,
            customer_name=chat_data.get("client_name", ""),
            customer_id=chat_data.get("client_id", ""),
            status="open",
            unread_count=0,
            last_message_at=chat_data["last_message_at"],
            first_message_at=chat_data["last_message_at"],
            last_message_preview=chat_data.get("last_message_text", ""),
            chat_status="waiting",  # Will be recalculated below
            sla_priority="normal",
        )
        db.add(chat)
        await db.flush()
        logger.debug(f"Created new chat {chat.id} for {external_chat_id}")
    else:
        # Update existing chat metadata
        chat.last_message_at = chat_data["last_message_at"]
        chat.last_message_preview = chat_data.get("last_message_text", "")
        chat.customer_name = chat_data.get("client_name") or chat.customer_name

    # Insert messages (skip duplicates)
    new_buyer_messages = 0
    for msg in chat_data["messages"]:
        # Check if message exists
        existing = await db.execute(
            select(Message.id).where(
                and_(
                    Message.chat_id == chat.id,
                    Message.external_message_id == msg["external_message_id"]
                )
            )
        )
        if existing.scalar_one_or_none():
            continue  # Skip duplicate

        message = Message(
            chat_id=chat.id,
            external_message_id=msg["external_message_id"],
            direction="incoming" if msg["author_type"] == "buyer" else "outgoing",
            text=msg.get("text", ""),
            attachments=msg.get("attachments"),
            author_type=msg["author_type"],
            status="sent",
            is_read=msg["author_type"] == "seller",
            sent_at=msg["created_at"],
        )
        db.add(message)

        # Count new buyer messages for unread
        if msg["author_type"] == "buyer":
            new_buyer_messages += 1

    # Update unread count
    chat.unread_count += new_buyer_messages

    # CRITICAL: Recalculate chat_status based on ALL messages
    await _recalculate_chat_status(db, chat)

    logger.debug(f"Upserted {len(chat_data['messages'])} messages for chat {chat.id}")


async def _recalculate_chat_status(db, chat: Chat):
    """
    Recalculate chat_status based on message history.

    Logic:
    - If last message from buyer: "waiting" or "client-replied"
    - If last message from seller: "responded"
    - If last message from system: "auto-response"
    """
    # Get all messages for this chat, ordered by time
    result = await db.execute(
        select(Message)
        .where(Message.chat_id == chat.id)
        .order_by(Message.sent_at.asc())
    )
    messages = result.scalars().all()

    if not messages:
        chat.chat_status = "waiting"
        return

    last_message = messages[-1]

    if last_message.author_type in ("buyer", "customer"):
        # Check if we ever responded
        seller_messages = [m for m in messages[:-1] if m.author_type in ("seller", "system")]
        if seller_messages:
            chat.chat_status = "client-replied"
        else:
            chat.chat_status = "waiting"

    elif last_message.author_type == "seller":
        chat.chat_status = "responded"
        chat.unread_count = 0  # Clear unread when we respond

    elif last_message.author_type == "system":
        chat.chat_status = "auto-response"

    else:
        chat.chat_status = "waiting"  # Fallback

    logger.debug(f"Chat {chat.id} status recalculated: {chat.chat_status}")
```

---

## 5. Chat Closure Recommendations

### 5.1 Industry Best Practices (Zendesk, Intercom, Freshdesk)

Based on customer support industry standards:

| Platform | Auto-close Trigger | Timer | Status Flow |
|----------|-------------------|-------|-------------|
| **Zendesk** | No customer reply after resolution | 4 days default (configurable) | Open -> Pending -> Solved -> Closed |
| **Intercom** | No activity after snooze/resolution | 7 days | Open -> Closed |
| **Freshdesk** | No response to "resolved" status | 48 hours | Open -> Pending -> Resolved -> Closed |
| **AgentIQ (proposed)** | See below | 10 days | Open -> Responded -> Closed |

### 5.2 Proposed Closure Strategy for AgentIQ

**Automatic Closure Rules:**

1. **After 10 days of inactivity** (no new messages from either side)
   - Status: `responded` or `auto-response` -> `closed`
   - Trigger: Celery scheduled task

2. **After seller marks as resolved**
   - Add new status: `resolved` (pending auto-close)
   - After 24 hours with no customer reply -> `closed`

3. **After customer confirms resolution**
   - Immediate: `closed`
   - Optional: Ask for rating

**Manual Closure:**

4. **"Close Chat" button**
   - Available for seller in UI
   - Sets status: `closed`
   - Can be reopened if customer writes again

### 5.3 Status Extension for Closure

```python
# Add to Chat model
CHAT_STATUS_CHOICES = [
    "waiting",       # Needs seller response
    "responded",     # Seller replied
    "client-replied", # Customer replied back
    "auto-response", # AI auto-responded
    "resolved",      # Seller marked as resolved, pending close
    "closed",        # Archived, no action needed
]
```

### 5.4 UI Changes Needed

1. Add "Close Chat" button in chat window
2. Add "Closed" filter in sidebar
3. Show "Reopen" button for closed chats
4. Add closure timestamp display

---

## 6. SLA Priority Logic

### Current SLA Rules

| Priority | Trigger | Deadline |
|----------|---------|----------|
| `urgent` | SLA deadline < 30 min | Immediate attention |
| `urgent` | Linked to negative review | Immediate attention |
| `high` | SLA deadline < 2 hours | Within 2 hours |
| `high` | First message in chat | Within 1 hour |
| `normal` | Default | Within 24 hours |
| `low` | Follow-up question | Best effort |

### SLA Deadline Calculation

```python
def calculate_sla_deadline(chat: Chat, messages: List[Message]) -> datetime:
    """
    Calculate SLA deadline based on message context.

    Rules:
    1. Negative review linked -> 1 hour from first customer message
    2. New chat (first message) -> 1 hour (WB: +20% conversion)
    3. Normal follow-up -> 24 hours
    """
    if not messages:
        return datetime.utcnow() + timedelta(hours=24)

    first_customer_msg = next(
        (m for m in messages if m.author_type == "buyer"),
        None
    )

    if not first_customer_msg:
        return datetime.utcnow() + timedelta(hours=24)

    # Check for negative review linkage (from Feedbacks API)
    if chat.has_linked_negative_review:
        return first_customer_msg.sent_at + timedelta(hours=1)

    # New chat - 1 hour SLA for conversion
    if len(messages) <= 1:
        return first_customer_msg.sent_at + timedelta(hours=1)

    # Regular follow-up - 24 hours
    return first_customer_msg.sent_at + timedelta(hours=24)
```

### SLA Escalation Task (Already Exists)

The `check_sla_escalation` task in `sync.py` already handles escalation to `urgent` when deadline is within 30 minutes. This is correct and should continue working.

---

## 7. Complete Status Flow Examples

### Example 1: New Customer Chat

```
1. Customer writes: "Hi, when will you ship?"
   -> chat_status = "waiting"
   -> sla_priority = "normal" (or "high" if new chat)
   -> UI: "Ожидают ответа" section

2. Seller responds: "Hi! We'll ship today."
   -> chat_status = "responded"
   -> unread_count = 0
   -> UI: "Все сообщения" section

3. Customer writes: "Thanks! Can you send tracking?"
   -> chat_status = "client-replied"
   -> unread_count = 1
   -> UI: "Ожидают ответа" section

4. Seller responds: "Here's your tracking: XYZ123"
   -> chat_status = "responded"
   -> unread_count = 0
   -> UI: "Все сообщения" section

5. 10 days pass with no activity
   -> chat_status = "closed" (auto)
   -> UI: Hidden or in "Closed" filter
```

### Example 2: Negative Review Chat

```
1. WB opens chat for 2-star review
   -> chat_status = "waiting"
   -> sla_priority = "urgent" (linked to negative)
   -> sla_deadline = +1 hour
   -> UI: "В работе" section (red dot)

2. Seller responds within 30 min: "We're sorry! Let us help..."
   -> chat_status = "responded"
   -> sla_priority = "high" (still important)
   -> UI: "Все сообщения" section

3. Customer replies: "OK, I'll try the return"
   -> chat_status = "client-replied"
   -> sla_priority = "high"
   -> UI: "Ожидают ответа" section

4. Resolution + customer updates review to 5 stars
   -> chat_status = "resolved"
   -> sla_priority = "normal"
   -> UI: "Все сообщения" section
```

---

## 8. Implementation Checklist

### Backend Changes

- [ ] Fix `_upsert_chat_and_messages()` in `sync.py`
- [ ] Add `_recalculate_chat_status()` helper function
- [ ] Add new status values: `resolved`, `closed`
- [ ] Add Celery task for auto-closing inactive chats
- [ ] Update API endpoint to support manual close/reopen

### Frontend Changes

- [ ] Verify `ChatList.tsx` grouping logic works with fixed statuses
- [ ] Add "Close Chat" button
- [ ] Add "Closed" filter option
- [ ] Show closure information in chat details

### Testing

- [ ] Test new chat creates with correct status
- [ ] Test seller message sets status to "responded"
- [ ] Test customer reply sets status to "client-replied"
- [ ] Test SLA escalation continues to work
- [ ] Test auto-close after 10 days

---

## 9. Summary

### Bug Root Cause
The sync function always set `chat_status = "waiting"` and only updated it on NEW buyer messages. Seller messages from marketplace sync never triggered status updates.

### Fix
Recalculate `chat_status` after every message sync by analyzing the last message author in the conversation.

### Key Insight
The frontend (`ChatList.tsx`) grouping logic is correct. The bug is entirely in the backend sync logic that fails to properly calculate `chat_status`.

---

**Document Version:** 1.0
**Last Updated:** 2026-02-10
