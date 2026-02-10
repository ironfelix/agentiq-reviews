# LLM Processing Plan for Chat Center

**Created:** 2026-02-10
**Status:** Research & Planning
**Author:** Claude Code Analysis

---

## Executive Summary

This document analyzes the current state of LLM processing in Chat Center and proposes improvements for handling empty messages, timing of AI analysis, and AI suggestion display.

---

## 1. Current State Analysis

### 1.1 Message Processing Flow

```
WB API Events → WBConnector.fetch_messages() → sync.py → Database
                                                   ↓
                                           analyze_pending_chats (Celery Beat, every 2 min)
                                                   ↓
                                           AIAnalyzer.analyze_chat()
                                                   ↓
                                           Chat.ai_suggestion_text, Chat.ai_analysis_json
```

**Key Files:**
- `/backend/app/services/wb_connector.py` - WB API integration
- `/backend/app/tasks/sync.py` - Sync tasks and AI analysis triggers
- `/backend/app/services/ai_analyzer.py` - LLM integration (DeepSeek)
- `/backend/app/api/chats.py` - REST API with manual analyze endpoint

### 1.2 What Works

| Feature | Status | Location |
|---------|--------|----------|
| Message sync from WB | Working | `sync.py:_sync_wb()` |
| AI analysis task | Working | `sync.py:analyze_chat_with_ai()` |
| Periodic analysis | Working | Celery Beat every 2 min |
| Manual analyze button | Working | `POST /api/chats/{id}/analyze` |
| AI suggestion in right panel | Working | `App.tsx` context panel |
| AI suggestion in ChatWindow | Working | `ChatWindow.tsx:224-244` |
| Guardrails application | Working | `ai_analyzer.py:_apply_guardrails()` |

### 1.3 What Does NOT Work / Needs Improvement

| Issue | Impact | Priority |
|-------|--------|----------|
| Empty messages not handled | Users see blank messages | High |
| No "Analyzing..." indicator | Users don't know analysis is running | Medium |
| AI suggestions appear after 2+ minutes | Poor real-time UX | High |
| No image placeholders | Confusing for image-only messages | Medium |
| Attachments not displayed | Missed context from images | Medium |

---

## 2. Issue Analysis & Solutions

### 2.1 Empty Messages and Images

#### Current Behavior

**WB API returns:**
```json
{
  "message": {
    "text": "",
    "files": [{"fileName": "image.jpg", "downloadID": "abc123"}]
  }
}
```

**Current code in `wb_connector.py:205-224`:**
```python
messages.append({
    "text": event.get("message", {}).get("text", ""),
    "attachments": [
        {
            "type": "file",
            "file_name": f.get("fileName", ""),
            "download_id": f.get("downloadID", "")
        }
        for f in event.get("message", {}).get("files", [])
    ],
    ...
})
```

**Problem:** Text is empty string, attachments are saved but never displayed in frontend.

#### Proposed Solution

**Backend changes (`wb_connector.py`):**

```python
# Add after line 224
def _normalize_message_text(text: str, attachments: list) -> str:
    """Generate display text for messages with images/files."""
    if text and text.strip():
        return text.strip()

    if attachments:
        file_count = len(attachments)
        if file_count == 1:
            return "[Изображение]"
        return f"[{file_count} изображений]"

    return ""  # Truly empty message - will be filtered out
```

**Frontend changes (`ChatWindow.tsx`):**

```tsx
// Add to renderMessages()
const getMessageContent = (message: Message) => {
  if (message.text && message.text.trim()) {
    return message.text;
  }

  if (message.attachments && message.attachments.length > 0) {
    const count = message.attachments.length;
    return (
      <div className="message-attachment-placeholder">
        <svg>...</svg>
        {count === 1 ? "Изображение" : `${count} изображений`}
        <span className="attachment-note">Изображения недоступны в API</span>
      </div>
    );
  }

  return <span className="empty-message">Пустое сообщение</span>;
};
```

#### MVP Rules for Empty Messages

1. **If `text` is empty but `attachments` exist** - Show "[Изображение]" placeholder
2. **If `text` is empty AND no attachments** - Filter out, don't show in UI
3. **For AI analysis** - Skip empty messages, note in context: "Клиент отправил изображение (недоступно)"
4. **Unread count** - Don't increment for truly empty messages
5. **Last message preview** - Show "[Изображение]" if text empty but has attachments

---

### 2.2 Timing of Intent Detection & AI Analysis

#### Current Implementation

```
sync_all_sellers (every 30s)
    → sync_seller_chats()
        → _upsert_chat_and_messages()

analyze_pending_chats (every 2 min)
    → find chats where:
        - unread_count > 0
        - ai_suggestion_text IS NULL
        - chat_status IN ('waiting', 'client-replied')
    → analyze_chat_with_ai() for each (max 10)
```

**Problem:** 2-minute delay is too long for real-time customer support.

#### Analysis of Options

| Option | Pros | Cons | Latency |
|--------|------|------|---------|
| **A: Sync-time analysis** | Immediate | Blocks sync, timeout risk | ~5s |
| **B: On-open analysis** | Only for viewed chats | Delay on first open | ~3s |
| **C: Background after sync (current)** | Non-blocking | 2+ min delay | ~120s |
| **D: Event-driven immediate** | Near real-time | Complex, needs WebSocket | ~5s |

#### Recommended Approach: Hybrid (B + C)

**Phase 1 (MVP):** Keep background analysis, add on-demand when opening chat

```python
# In chats.py get_chat() or new endpoint
@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(chat_id: int, ...):
    chat = await get_chat_by_id(chat_id, db)

    # Trigger analysis if needed (non-blocking)
    if chat.ai_suggestion_text is None and chat.unread_count > 0:
        analyze_chat_with_ai.delay(chat_id)
        chat.analysis_status = "pending"  # New field

    return chat
```

**Phase 2:** Reduce Celery Beat interval to 30 seconds for faster background updates

```python
# In tasks/__init__.py
"analyze-pending-chats-every-30s": {
    "task": "app.tasks.sync.analyze_pending_chats",
    "schedule": 30.0,  # Was 120s
},
```

**Phase 3:** WebSocket for real-time updates (future)

#### "Analyzing..." Indicator

**Backend:** Add `analysis_status` field to Chat model

```python
# In models/chat.py
analysis_status = Column(String(20), default=None, nullable=True)
# Values: null, "pending", "analyzing", "complete", "error"
```

**Frontend:** Show indicator in context panel

```tsx
// In App.tsx context panel
{selectedChat?.analysis_status === 'pending' && (
  <div className="analysis-status">
    <div className="spinner" />
    Анализируется...
  </div>
)}
```

**Update flow:**
1. Chat opened with `ai_suggestion_text = null` → set `analysis_status = "pending"`
2. Celery task starts → set `analysis_status = "analyzing"`
3. Task completes → set `analysis_status = "complete"`, populate `ai_suggestion_text`
4. Frontend polls or WebSocket updates

---

### 2.3 AI Suggestions in ChatWindow

#### Current State

**AI suggestion IS displayed** in `ChatWindow.tsx:224-244`:

```tsx
{chat.ai_suggestion_text && (
  <div className="ai-suggestion" onClick={handleUseAISuggestion}>
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
  </div>
)}
```

**Why it might not appear:**

1. **`ai_suggestion_text` is null** - Analysis hasn't run yet
2. **Analysis failed** - DeepSeek API error, no fallback stored
3. **Chat doesn't meet criteria** - `unread_count = 0` or `chat_status` not waiting
4. **Last message is from seller** - Analysis returns `recommendation: null` by design

#### Diagnostic Checklist

| Check | Expected | Actual |
|-------|----------|--------|
| `chat.ai_suggestion_text` in API response | String or null | ? |
| `ai_analysis_json` populated | JSON string | ? |
| DeepSeek API key configured | `DEEPSEEK_API_KEY` in .env | ? |
| Celery worker running | `celery -A app.tasks worker` | ? |
| Celery beat running | `celery -A app.tasks beat` | ? |

#### Fixes

**1. Always show AI panel, indicate status:**

```tsx
// In ChatWindow.tsx
{chat.ai_suggestion_text ? (
  <div className="ai-suggestion" onClick={handleUseAISuggestion}>
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">{chat.ai_suggestion_text}</div>
  </div>
) : chat.unread_count > 0 ? (
  <div className="ai-suggestion ai-suggestion--pending">
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text">
      <span className="spinner" /> Генерируется...
    </div>
  </div>
) : (
  <div className="ai-suggestion ai-suggestion--empty">
    <div className="ai-suggestion-label">AI Рекомендация</div>
    <div className="ai-suggestion-text text-muted">
      Нет ожидающих сообщений
    </div>
  </div>
)}
```

**2. Trigger analysis on chat open if missing:**

```tsx
// In App.tsx handleSelectChat()
const handleSelectChat = useCallback(async (chat: Chat) => {
  setSelectedChat(chat);
  fetchMessages(chat.id);

  // Trigger AI analysis if missing and has unread
  if (!chat.ai_suggestion_text && chat.unread_count > 0) {
    try {
      await chatApi.analyzeChat(chat.id, { async_mode: true });
    } catch (e) {
      console.warn('Failed to trigger analysis:', e);
    }
  }
  ...
}, []);
```

**3. Ensure fallback analysis stores result:**

```python
# In ai_analyzer.py analyze_chat_for_db()
if analysis:
    chat.ai_analysis_json = json.dumps(analysis, ensure_ascii=False, default=str)
    chat.ai_suggestion_text = analysis.get("recommendation")
    # ^ This line already exists, but check if recommendation is null
    if not chat.ai_suggestion_text and analysis.get("intent"):
        # Generate fallback if LLM returned no recommendation
        chat.ai_suggestion_text = analyzer._fallback_analysis(
            messages_data, chat.customer_name
        ).get("recommendation")
```

---

## 3. Industry Best Practices

### 3.1 Intent Detection Timing

**Zendesk Answer Bot / Intercom Fin / Freshdesk Freddy:**

| Tool | Approach | Latency |
|------|----------|---------|
| Zendesk | Real-time during typing | <1s |
| Intercom | On message send (webhook) | 2-3s |
| Freshdesk | Background + on-demand | 5-10s |
| Gorgias | Real-time streaming | <2s |

**Best practice:** Analyze on message arrival (webhook/event), not periodic polling.

### 3.2 AI Suggestion Display Patterns

**Common patterns:**

1. **Inline below messages** (Intercom) - AI suggestion appears as a "draft" bubble
2. **Side panel** (Zendesk) - Context panel with suggestion + edit
3. **Quick actions** (Freshdesk) - Buttons for common responses
4. **Streaming response** (Gorgias) - Token-by-token display

**Recommended for AgentIQ:**
- Primary: Inline in ChatWindow (current implementation)
- Secondary: Context panel for editing
- Add: Quick action buttons for template responses

### 3.3 Handling Attachments/Media

**Industry approaches:**

1. **Thumbnail display** - Show small preview, click to expand
2. **OCR/Vision analysis** - Extract text from images with GPT-4V
3. **Placeholder with download** - "[Image] Click to download"
4. **File type icons** - Different icons for images, PDFs, etc.

**MVP recommendation:** Placeholder with note, future: GPT-4V integration

### 3.4 Confidence & Editing

**Best practices:**
- Show confidence score (high/medium/low)
- Allow one-click edit before send
- Track edited suggestions for model improvement
- Provide multiple suggestion options

---

## 4. Implementation Plan

### Phase 1: MVP Fixes (1-2 days)

| Task | File | Priority |
|------|------|----------|
| Handle empty messages with attachments | `wb_connector.py`, `ChatWindow.tsx` | High |
| Add "Analyzing..." indicator | `ChatWindow.tsx`, `App.tsx` | High |
| Trigger analysis on chat open | `App.tsx` | High |
| Ensure fallback suggestion always saved | `ai_analyzer.py` | High |

### Phase 2: UX Improvements (3-5 days)

| Task | File | Priority |
|------|------|----------|
| Reduce analysis interval to 30s | `tasks/__init__.py` | Medium |
| Add `analysis_status` field to Chat | `models/chat.py`, `schemas/chat.py` | Medium |
| Show analysis status in UI | `App.tsx`, `ChatWindow.tsx` | Medium |
| Attachment placeholders with icons | `ChatWindow.tsx`, `index.css` | Medium |

### Phase 3: Real-time (Future)

| Task | Complexity | Impact |
|------|------------|--------|
| WebSocket for live updates | High | High |
| GPT-4V for image analysis | Medium | Medium |
| Streaming AI responses | Medium | High |
| Multiple suggestion variants | Medium | Medium |

---

## 5. MVP Rules Summary

### Empty Messages

```
IF text.trim() == "" AND attachments.length > 0:
    display_text = "[Изображение]" or "[{n} изображений]"
    for_ai_context = "Клиент отправил изображение (содержимое недоступно)"
    increment_unread = true

IF text.trim() == "" AND attachments.length == 0:
    display_text = null (filter out)
    increment_unread = false
```

### AI Analysis Timing

```
ON sync_complete:
    trigger analyze_pending_chats async (every 30s)

ON chat_open:
    IF ai_suggestion_text == null AND unread_count > 0:
        trigger analyze_chat_with_ai async
        show "Анализируется..."

ON analysis_complete:
    update chat.ai_suggestion_text
    update chat.analysis_status = "complete"
    refresh UI (polling or WebSocket)
```

### AI Suggestion Display

```
IF ai_suggestion_text != null:
    show suggestion in ChatWindow (clickable to use)
    show details in context panel

IF ai_suggestion_text == null AND unread_count > 0:
    show "Генерируется..." placeholder

IF ai_suggestion_text == null AND unread_count == 0:
    show "Нет ожидающих сообщений"
```

---

## 6. Technical Debt & Notes

1. **Sync cursor not persisted** - Each sync starts from beginning (see `sync.py:117-121`)
2. **DeepSeek timeout** - 30s may be too short for complex chats
3. **No retry on analysis failure** - Failed analyses don't retry automatically
4. **Polling vs WebSocket** - Current polling (10s) is inefficient

---

## 7. Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time to first AI suggestion | ~2 min | <10s |
| Suggestion display rate | Unknown | >90% of waiting chats |
| Empty message confusion | High | Zero |
| User-reported missing suggestions | Unknown | <5% |

---

## Appendix: Code References

### Key Files

| File | Purpose |
|------|---------|
| `backend/app/tasks/sync.py` | Celery tasks for sync and analysis |
| `backend/app/services/wb_connector.py` | WB API client |
| `backend/app/services/ai_analyzer.py` | DeepSeek LLM integration |
| `backend/app/api/chats.py` | REST API endpoints |
| `frontend/src/components/ChatWindow.tsx` | Chat message display |
| `frontend/src/App.tsx` | Main app with context panel |

### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/chats` | GET | List chats with filters |
| `/api/chats/{id}` | GET | Get single chat |
| `/api/chats/{id}/analyze` | POST | Trigger AI analysis |
| `/api/chats/{id}/messages` | GET | Get chat messages |
| `/api/messages` | POST | Send message |
