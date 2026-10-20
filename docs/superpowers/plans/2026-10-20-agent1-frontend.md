# Agent1 Frontend Integration Implementation Plan

> Execute inline in the current isolated checkout. The user already approved the integration scope; independent reviewers inspect completed changes before publication.

**Goal:** Replace the frontend's simulated confirmation/search logic with Agent1's actual local services.
**Architecture:** Adapter-scoped Agent1 Store joins SQLite transactions for profile changes; durable task preparation and real receipt reconciliation surround Agent2 execution. Retain the existing frontend API shape except for required review_token and added provenance metadata.
**Tech Stack:** Python 3.13, FastAPI, SQLite, existing Agent1/2/3/4, React/TypeScript/Ant Design, Vite.

## Constraints
- Existing member modules remain unchanged; only adapter, frontend, tests and integration documentation change.
- Synthetic form inputs are explicit; no model call, real tenancy choice or member-attended acceptance is claimed.
- No new automatic selection, contract consent or M3/M4 behavior.
- Store browser and core draft revisions separately; preserve old immutable versions/results.

## Task 1: Core-backed API
Files: `server/app/adapters/agent1.py` (Store join + public service adapter); `profiles.py`, `services.py`, `business.py`, `bootstrap.py`, `main.py`, `system.py`; tests `server/tests/test_agent1_api.py`, existing `test_api.py`.
- [x] Add failing integration tests for real core persistence, stale/missing tokens, new-version confirmation, stable retry, durable response loss, atomic rollback, concurrent confirmation, late-result rejection and legacy read-only behavior.
- [x] Run `.venv/bin/python -m unittest discover -s server/tests -p test_agent1_api.py -v`; expect missing Agent1 provenance/token handling failures.
- [x] Wire PreferenceAgent.startCollection/setFields/reviewDraft/confirmProfile to existing create/draft/confirm routes. Confirmation request becomes `{draft_revision,fingerprint,review_token}`.
- [x] Reserve via HandoverService with a prepare-only receiver inside joined transaction, then execute real HandoverService.reconcileRetry outside it. Persist original report and Agent1 `compare_current(..., optional=True).raw_comparison` only for the current confirmed version.
- [x] Update existing boundary helper for review tokens, run old and new suites and correct regressions.

## Task 2: Browser workflow
Files: `frontend/src/api/types.ts`, `app/context.tsx`, `app/App.tsx`, `features/Preferences.tsx`, `features/Recommendations.tsx`, `frontend/e2e/journey.spec.ts`.
- [x] Send the displayed token with confirmation; derive current confirmation from latest version, draft revision and Agent1 state.
- [x] Show actual Agent1 local-service status, warnings and legacy-case read-only guidance; preserve existing form and immutable comparison UI.
- [x] Add browser regression assertions for actual Agent1 provenance, new confirmed version, exact task replay and same-snapshot comparison. Keep selection/contract flow unchanged.
- [x] Run `npm run build`, then validate actual browser identity/content/error health, create/confirm/evaluate, edit/reconfirm/compare, refresh, and desktop/mobile rendering.

## Task 3: Review and publication
- [x] Independently review diff against the spec and fix important defects; rerun affected checks.
- [ ] Update API/run documentation, commit named paths and push existing PR4 branch; update PR description with actual validation.
- [ ] Record PR6 merge and Agent1 browser integration evidence in SCRUM35/19/34, retaining team/live-LLM acceptance as pending.
