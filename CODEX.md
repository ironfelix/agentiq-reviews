# AgentIQ — Instructions for Codex

## Cross-model Sync (MANDATORY)
- Before any work, read **`CLAUDE.md`**.
- This file and `CLAUDE.md` must stay aligned on critical rules.
- If you change one file's global instructions, update the other in the same commit.

## Startup Checklist
1. Read `CLAUDE.md`.
2. Read this `CODEX.md`.
3. Read task-specific docs referenced by `CLAUDE.md` (reviews/chat-center/design/research).

## Source of Truth Policy
1. Product and operational rules are shared between models.
2. No model-specific contradictions are allowed.
3. In case of mismatch:
- Treat `CLAUDE.md` + `CODEX.md` as highest local project policy.
- Fix the mismatch immediately.

## Handoff Protocol (between providers/models)
1. Document major decisions in project docs (`docs/...`) with date.
2. Keep plans executable: backlog, owners, acceptance criteria.
3. Mark data-source decisions explicitly (`WB API first`, fallback rules, confidence thresholds).

## Documentation Policy (MANDATORY)
Path note: in this repo the canonical docs live under `docs/` at the repository root.

1. Project documentation lives in `docs/` and is consolidated via:
- `docs/docs-home.html` (human portal, statuses, module map)
- `docs/INDEX.md` (Markdown index)
2. Keep docs fresh (avoid stale docs):
- Every major document must start with `Last updated:` and `Status:`.
- If it's a hypothesis/idea: explicitly state "plan / not implemented".
- If it's implemented: include pointers to the source of truth (files/endpoints/tables) and current constraints.
3. Execution log for Unified Communications must be maintained in:
- `docs/product/UNIFIED_COMM_PLAN_V3_WB_FIRST.md`

## Identity Linking Safety
1. Do not use buyer name/FIO as deterministic identity key.
2. Use `customer_id/order_id` when available.
3. Name/FIO is only a weak probabilistic signal.
4. No auto-actions on low-confidence links.

## Data Source Rules
1. WB API is primary for operational workflows.
2. WBCON is fallback for analytics gaps only.
3. Always label metric source in UI/API (`wb_api` vs `wbcon_fallback`).

## Frontend Design Contract (MANDATORY)
1. For app UI in Chat Center, the single source of truth is `docs/prototypes/app-screens-v3-ru.html`.
2. When implementing backend/service logic, do not redesign layout, hierarchy, or visual patterns.
3. Allowed UI changes are only data wiring and state handling (loading/error/empty) that preserve the approved design.

## Maintenance Rule
- When you read `CODEX.md`, also re-open `CLAUDE.md` before substantial edits.
