# AgentIQ — Instructions for Codex

## Cross-model Sync (MANDATORY)
- Before any work, read **`CLAUDE.md`**.
- This file and `CLAUDE.md` must stay aligned on critical rules.
- If you change one file's global instructions, update the other in the same commit.

## Startup Checklist
1. Read `CLAUDE.md`.
2. Read this `CODEX.md`.
3. Read task-specific docs referenced by `CLAUDE.md` (reviews/chat-center/design/research).

## Architecture: 5-Layer Model
Canonical doc: **`docs/architecture/architecture.md`** — validated against codebase 2026-02-14.

Five layers: **Ingestion** (85%) → **Context** (40%) → **Orchestration** (25%) → **Intelligence** (75%) → **Analytics** (70%).

Key gaps tracked as G1-01..G5-05 in architecture.md. Priority: Context (Customer profile, Product cache) and Analytics (Revenue model) are P1. Orchestration (Routing, Assignment) is P2 — needed when sellers grow to teams.

Principle: **new channel = new connector, not a rewrite**. The `Interaction` model is channel-agnostic.

Scaling notes: **`docs/architecture/SCALING_NOTES.md`** — inline AI analysis in sync pipeline, tiered scaling strategy (MVP → enterprise).

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

## Security (MANDATORY)

### Security Documentation
- **`docs/security/SECURITY_AUDIT.md`** — full audit report (36 findings, action plan)
- **`docs/security/SECURITY_REVIEW_PROCESS.md`** — CI checks, pre-deploy checklist, secrets rotation, incident response

### Security Rules for Development
1. **Never commit `.env` files** — secrets only in env vars on production
2. **All new endpoints** must use `Depends(get_current_seller)` (not optional)
3. **All text inputs** must have `max_length` in Pydantic schema
4. **No raw SQL** — only SQLAlchemy ORM with parameterized queries
5. **Before deploy** — run pre-deploy checklist from `SECURITY_REVIEW_PROCESS.md`
6. **Secrets rotation** — follow schedule in SECURITY_REVIEW_PROCESS.md

## Guardrails System (MANDATORY)
Canonical source: **`docs/GUARDRAILS.md`** — the single consolidated document for all guardrails.

### Philosophy
Guardrails are a declarative ethical and operational system, NOT a set of hardcoded if/else branches.
- Rules are described as tables, categories, severity levels, and thresholds.
- Code reads config dicts and applies rules generically — business logic lives in docs, not inline.
- Minimal hardcoding: new rules = add a row to a table or a phrase to a list, not new code paths.
- Four-stage pipeline: **Content** (banned phrases) → **Safety Policies** (A/B/C groups) → **Action Policy** (auto vs assist) → **Audit Trail**.

### Where to look
| What | Where |
|------|-------|
| Full policy docs (single source) | `docs/GUARDRAILS.md` |
| Runtime banned phrases + channel rules | `apps/chat-center/backend/app/services/guardrails.py` |
| Auto-action policy + linking confidence | `apps/chat-center/backend/app/services/interaction_linking.py` |
| LLM analyzer config dict | `scripts/llm_analyzer.py:478-519` |
| Legacy detailed policy (reviews + chat) | `docs/reviews/RESPONSE_GUARDRAILS.md` |

### Key thresholds (from code)
- `MIN_LINK_CONFIDENCE = 0.55` — below this, no link is created
- `AUTO_ACTION_MIN_CONFIDENCE = 0.85` — below this, deterministic links are assist-only
- Probabilistic links are **always** assist-only regardless of confidence
- Reply length: 20-300 chars

## Identity Linking Safety
1. Do not use buyer name/FIO as deterministic identity key.
2. Use `customer_id/order_id` when available.
3. Name/FIO is only a weak probabilistic signal.
4. No auto-actions on low-confidence links (see Guardrails System above).

## Data Source Rules
1. WB API is primary for operational workflows.
2. WBCON is fallback for analytics gaps only.
3. Always label metric source in UI/API (`wb_api` vs `wbcon_fallback`).

## Frontend Design Contract (MANDATORY)
1. For app UI in Chat Center, the single source of truth is `docs/prototypes/app-screens-v3-ru.html`.
2. When implementing backend/service logic, do not redesign layout, hierarchy, or visual patterns.
3. Allowed UI changes are only data wiring and state handling (loading/error/empty) that preserve the approved design.

## Design System (MANDATORY)

**📚 Full documentation:** `docs/design-system/` — Colors, Typography, Components, Panels

**Key files:**
- **`docs/design-system/COLORS.md`** — Color palette (Reviews vs Chat Center themes)
- **`docs/design-system/TYPOGRAPHY.md`** — Fonts, type scale, typography system
- **`docs/design-system/COMPONENTS.md`** — UI components (buttons, inputs, badges, cards, etc.)
- **`docs/design-system/PANELS.md`** — Panel components (Help, Context, Advanced Filters)

**Core principles:**
1. Consistency — unified visual language across all modules
2. Context near action — panel triggers placed at the top of sections
3. Clarity over complexity — plain language, semantic naming
4. Mobile-first — responsive, touch-friendly (44x44px touch targets)
5. Accessibility — WCAG AA compliance, keyboard navigation, ARIA labels

**Quick reference:**
- **Reviews App (dark theme):** `#0a1018` background, `#e8a838` accent (Montserrat font)
- **Chat Center (light theme):** `#ffffff` background, `#1a73e8` accent (Inter font)

## Maintenance Rule
- When you read `CODEX.md`, also re-open `CLAUDE.md` before substantial edits.
