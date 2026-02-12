# Unified Inbox Bugfix Report (Reviews + Questions + Chats)

Last updated: 2026-02-12  
Status: Implemented (local + deployed to staging)

## Symptoms Reported (operator UX)

- Channel tabs/counts showed `50` while реально было ~`500` (page-size vs total mismatch).
- Questions showed “current date” (ingestion-time) instead of real buyer timestamp.
- Items marked “Отвечено”, but seller reply text was missing in UI.
- Reviews with only rating (5★) looked like “empty” because text was absent.
- Chat interactions did not show full history (only synthetic 1-2 messages).

## Root Causes

1. Backend ingestion: `_parse_iso_dt()` was broken, so `occurred_at` for review/question stayed `NULL`.
2. Ingestion didn’t map WB seller answers into a UI-consumable field (`extra_data.last_reply_text`).
3. Frontend treated every interaction as a synthetic “chat thread”, ignoring real chat `messages` table for `channel=chat`.
4. Frontend counters were computed from the currently loaded page (`len(chats)`), not from storage totals.

## Fixes Implemented

### Backend (data correctness)

- Fixed ISO datetime parsing + UTC normalization in ingestion:
  - `apps/chat-center/backend/app/services/interaction_ingest.py`
- Persisted WB seller answers into:
  - `extra_data.wb_answer_text` (raw)
  - `extra_data.last_reply_text` (UI draft/outgoing message source)
- Made ingestion extra-data merge safe (new ingestion does not wipe drafts/linking metadata).

### Frontend (operator correctness)

- For `channel=chat` interactions: load real history via `chat_id` from `interaction.extra_data`:
  - `apps/chat-center/frontend/src/App.tsx`
- For review without text: show explicit placeholder (“только оценка: N★”) in list preview and message body:
  - `apps/chat-center/frontend/src/App.tsx`
- Counter correctness: show totals from backend pipeline metrics (not page-size):
  - `apps/chat-center/frontend/src/components/ChatList.tsx`
  - uses `qualityMetrics.pipeline` from `GET /api/interactions/metrics/quality`

### Staging (demo reliability)

- Fixed static assets layout so `/app/` can load JS/CSS:
  - `/app/` serves SPA entry: `/var/www/agentiq/app/index.html`
  - assets served from root: `/var/www/agentiq/assets/*` (requested as `/assets/*`)
  - See: `docs/product/STAGING_DEMO_STATUS.md`

## Verification

- Backend regression: `apps/chat-center/backend` pytest suite green (hermetic).
- Frontend regression: `apps/chat-center/frontend` `npm run build` green.
- Staging: `http://79.137.175.164/app/` loads, `http://79.137.175.164/api/health` OK.

