# Feature Spec: Interaction Reply

Last updated: 2026-02-13
Status: draft

Owner:

## 1. Summary
- Title: `POST /api/interactions/{interaction_id}/reply`
- Goal: обеспечить безопасную, детерминированную отсылку ответа на unified `Interaction` независимо от сущности (review/question/chat) и marketplace.
- Non-goals: не описывать UI/experience (они живут в `docs/prototypes`), не изобретать новый канал.

## 2. Context
- Why now: клиенты ожидают unified workflows, guardrails и audit trail в Spec-Driven pipeline.
- Related docs: `docs/specs/CATALOG.md`, `docs/specs/entities/UNIFIED_INTERACTION.md`, `docs/specs/guardrails/AI_DRAFTS.md`, `docs/specs/guardrails/REVIEWS_RESPONSES.md`, `docs/specs/guardrails/CHAT_RESPONSES.md`, `docs/specs/guardrails/QUESTIONS_RESPONSES.md`, `docs/specs/marketplaces/CONTRACT.md`.
- Related code: `apps/chat-center/backend/app/api/interactions.py`, `app/services/interaction_drafts.py`, `app/services/wb_feedbacks_connector.py`, `app/services/wb_questions_connector.py`, `app/tasks/sync.py`.
- Data sources: WB APIs (primary), AgentIQ DB (interactions/chat/message tables).

## 3. User / Business Impact
- Primary user: seller operators and AgentIQ agents who send replies on behalf of sellers.
- Success metric: replies that pass guardrails and produce zero incidents per rollout stage.

## 4. Interfaces
### API
- Endpoint: `POST /api/interactions/{interaction_id}/reply`
- Request: `payload.text` (non-empty string) plus optional metadata (future: template_id, template_data).
- Response: `InteractionReplyResponse` with updated interaction status and result (`sent`/`queued`).
- AuthN/AuthZ: requires authenticated seller owning interaction (`require_seller_ownership`).

### Data model
- Interaction table: `status`, `needs_response`, `priority`, `extra_data` augmented with `last_reply_*`.
- Chat table: `chat_status`, `last_message_at`, `unread_count`.
- Message table: inserted record for chat replies.

## 5. Behavior
- MUST: trim `payload.text`, reject empty strings (400).
- MUST: load `Interaction` and enforce seller ownership (`require_seller_ownership`).
- MUST: branch on `interaction.channel`:
  - `review`: use WB feedback connector (`answer_feedback`); apply `guardrails/REVIEWS_RESPONSES.md`; include concept of pending moderation (`last_reply_source=agentiq` + `wb_sync_state=pending`).
  - `question`: use WB questions connector (`patch_question`) with `state` from interaction (default `wbRu`); apply `guardrails/QUESTIONS_RESPONSES.md`; ensure answer respects marketplace limits from `marketplaces/CONTRACT.md`.
  - `chat`: resolve linked `Chat` via `extra_data.chat_id` or lookup by `marketplace_chat_id`; guard (404 if missing). Insert outgoing `Message`, keep `status=pending` if credentials missing; if API key present, enqueue `send_message_to_marketplace` task and keep `status=pending`. Always apply `guardrails/CHAT_RESPONSES.md`.
- MUST: guard for unsupported channels (400).
- MUST: wrap any connector failure as 502 but keep underlying `detail`.
- MUST: after successful send/update:
  - update `Interaction` status → `responded`, `needs_response=False`, `priority=low`.
  - enrich `extra_data` with `last_reply_text`, `last_reply_outcome`, `last_reply_source`, `last_reply_at`, `wb_sync_state`.
- MUST: call `record_reply_events` to capture audit metadata (source/version) referencing `guardrails/AI_DRAFTS.md`.
- SHOULD: while `current_seller.api_key_encrypted` missing, set chat status and `unread_count` to 0, persist message with `status=sent`.

## 6. Error Model
- 404 if `interaction_id` missing or linked chat missing.
- 400 for empty text or unsupported channel.
- 502 for connector failures or task dispatch errors (wrap underlying exception message).
- All errors must log minimal PII and include `interaction_id`.

## 7. Security & Privacy
- MUST NOT log secrets/credentials.
- Guardrails ensure banned phrases/PII not present (`guardrails/*`).
- Access control: verify seller ownership before any side effect.
- Replies traverse connectors that hide API keys (use stored `api_key_encrypted` and asynchronous workers).

## 8. Performance & Limits
- Timeouts: connectors should respect marketplace rate limits; API returns quickly if connector enqueues work.
- Pagination: not applicable.
- Rate limits: rely on existing rate limiter (if any); spec should note additional throttling if connectors start returning `429`.

## 9. Observability
- Logs should annotate `interaction_id`, `channel`, `marketplace`, trace guardrail version.
- Metrics: count of replies per channel, # rejected guardrail violations, # connector errors.
- `record_reply_events` must persist `reply_text` hash, outcome, policy version.

## 10. Acceptance Criteria
1. Sending reply without text returns 400 before calling connectors.
2. Each channel handles its connector path and updates `extra_data` as described.
3. Guardrails documented in `guardrails/*` are referenced and applied; an automated check fails if reply text contains banned phrases.
4. Audit trail entries exist after every reply (via `record_reply_events`).
5. Interaction status reflects response (status=responded, needs_response=false).

## 11. Tests
- Unit: missing interaction, empty text, unsupported channel, missing chat path, connector failure path, guardrail violation stub.
- Integration: simulate review/question/chat reply flows with mocked connectors to ensure status updates.
- Guardrail regression: run text validation lib (future) to ensure banned phrases cause rejection.

## 12. Rollout / Migration Plan
- Feature flag: not required (already live), but spec ensures future toggles don't bypass guardrails.
- Backward compatibility: existing endpoints not changed; new metadata added to `extra_data`.
- Rollback: revert spec and guardrail updates if connectors misbehave; we can rethrow to 502 and inspect logs.
