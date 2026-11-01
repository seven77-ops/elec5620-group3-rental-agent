# Living Continuity Implementation Plan

**Goal:** Deliver the approved lease-to-living handoff, contextual repair conversation, and actionable living-page todos.
**Architecture:** Preserve case-owned living records and explicit versioned confirmation. Lease source previews are read-only, token-bound and independently confirmed as actual occupancy before importing selected nonempty fields. Repair followups reference saved records or pending proposals and never create duplicate repairs merely to rewrite an email. Todos derive from records and navigate to existing actions.
**Tech Stack:** FastAPI/Python, existing SQLite repository, React/TypeScript/Ant Design, unittest and Playwright.

## Global constraints

Preserve all existing dirty changes; no Git commit, push or deployment. Do not alter original user-case data during testing. No email delivery or booking submission. Never infer an actual tenancy from an advertisement, review or unsigned draft. Require user confirmation, source and record version checks before import/update. Missing source values do not erase saved values. Existing utilities, repairs, bookings and evidence remain preserved. Exact address/contact details remain outside model context unless typed by the user. White/blue UI and 360px layout. No new independent progress page.

## Task 1: Lease source preview/import backend

Files: new `server/app/living/tenancy.py`, `server/tests/test_living_tenancy.py`. Root wires routes and adds date fields.

Contract: `LivingTenancy(ctx).preview(case_id)` -> `{expected_version,source:null|{kind,id,version,label,token,current,warning},values:Partial<LivingProfile>,previous:Partial<LivingProfile>,linked_source:null|object,changed:bool}`. Source kind `lease_draft` or `aftercare`. Use newest saved draft only when its candidate context is current; stale draft visible with `current:false` but cannot import. Prefer an existing confirmed aftercare tenancy if latest current draft has no changed address; if a current draft has a different address, show draft with explicit changed-home warning. Source token hashes source identity/version/fields and selection identity; do not include unrelated aftercare task state. `preview` performs no writes.

`LivingTenancy(ctx).apply(case_id,body)` accepts `{request_id,expected_version,confirmed:true,actual_tenancy_confirmed:true,source_token,fields:[...]}`; fields must be a nonempty subset of preview values. Server rereads source under transaction, requires same token/current source, checks exact record version, validates merged profile, stores `tenancy_source` metadata and receipt. Repeated identical request replays; different payload same request conflicts. Reject stale/foreign source. No empty/null fields offered or imported. Values mapping: address; agent_name (or landlord_name when agent absent); exact valid email/phone parsed from agent_contact/landlord_contact only; lease_start_date/start_date and lease_end_date/end_date. If confirmed aftercare source has only address, only import address and known carpeted boolean. No AI or network calls.

- [x] Write failing tests for no-write preview, draft import confirmation, chosen fields/non-overwrite, stale/changed candidate, idempotency and no duplicate record changes; run red.
- [x] Implement bounded source reader/token-bound import and run green. Report exact tests and scope.

## Task 2: Contextual repair followups backend (root)

Files: `living/fields.py`, `living/service.py`, new `living/repairs.py`, new `assistant/repair_dialogue.py`, `assistant/living.py`, `assistant/service.py`, `ai/provider.py`, tests `test_living_continuity.py`, demo intent fixture.

Extend living profile with nullable `lease_start_date`,`lease_end_date` (normalize old records on read; older full-profile payloads remain valid). New repair update proposal kind `repair_update`, values `{repair_id,status?,note?,email_tone?}`; `email_tone` standard/polite/concise. All updates require confirmation and exact record version. Notes are verbatim user messages; no inferred appointments. Existing repair status endpoint accepts optional note and email_tone and uses same validator. Update entry records `updates:[{at,note,status}]` and optional `email_tone`, preserving old repair facts/recipient/address. Rewriting uses deterministic tone templates over saved factual lines, not model-generated facts. A created repair proposal records resulting repair ID after apply.

Conversation resolves focus from the last repair action/proposal (including across reload); context includes safe record IDs/titles/descriptions/status/latest user update and a pending repair summary, never contact/address. New intent fields `repair_id`, `repair_update:{status?,email_tone?}` with service_action `update_repair`. If pending focus exists, tone rewrite produces a replacement proposal; final successful turn supersedes prior pending proposal. If saved focus exists, propose update, not new repair. Ambiguous references ask the user to identify issue. Explicit page chat prompts can include the saved repair ID. User can switch to a named saved issue. All derived actions remain case owned and model references validated.

- [x] Add red tests for polite rewrite before/after save, same-record reply and resolution, ambiguous/cross-case/stale references, unchanged contacts and duplicate protection.
- [x] Implement focus/schema/tools, confirmation summaries and status decoration; run focused suites.

## Task 3: Living UI continuity and todos

Files owned by frontend worker: `frontend/src/api/living.ts`, `features/living/*`, optional small `TenancyForm.tsx` link, new `frontend/e2e/living-continuity.spec.ts`. Root owns assistant UI/API if needed.

Use Task 1 endpoints: GET `/cases/{id}/living-services/tenancy-source`, POST `/cases/{id}/living-services/tenancy-import` with flat body above. `LivingProfile` adds nullable optional-compatible lease_start/end dates; record adds optional `tenancy_source`. Display source/version and previous/new field values; field checkboxes default only differing nonempty fields. Explicit actual-tenancy checkbox and confirmation modal; no import on preview/cancel. Changed-home warning explains existing utility/repair/service records stay unchanged. After successful import refresh record/source. Preserve input on failures and reject stale versions.

Top of hub: compact `待办事项` derived locally (max five, count plus view more if needed), e.g. prepared repair -> contact, contacted -> record reply, considering/contacted service -> quote/date confirmation, upcoming booked service -> view; move_out_date -> open existing moveout tab. No fake deadlines, no periodic automation. Action opens correct tab and specific repair/service record with scroll/focus and a useful button. Empty state is short. Optional missing-contact task only when a meaningful address/repair exists. Do not reintroduce independent progress page.

Repair cards show user-recorded updates, allow manual note/status and polite/concise rewrite using existing confirmed write envelope, plus chat followup button (prefill, never autosend) referencing issue ID and title. Use new update shape `{status?,note?,email_tone?}` and same `/repairs/{id}` endpoint. Existing email draft remains unsent; do not modify factual content when rewriting. Profile editor includes lease dates and labels them as lease dates, distinct from planned move-out date.

- [x] Add browser failing tests for source preview/cancel/import/reload, todo deep link and contextual/manual repair updates, mobile fit.
- [x] Build components using existing white/blue Ant Design; run browser tests in isolated runtime and build/API checks. Do not edit root-owned assistant files.

## Task 4: Integration, review and actual model verification

- [x] Root registers source/import endpoints, completes assistant wiring and fixtures. Run server full suite, Agent4 regressions and frontend build/API tests.
- [x] Run Playwright continuity and existing living/chat/assistant/contract suites on isolated runtime. Test actual configured model on a new temp case for create -> polite -> confirm -> agent reply -> resolution. Verify unconfirmed messages do not mutate living records.
- [x] Read-only review of changed files and fix actionable findings; inspect desktop/mobile screenshots.
- [x] Update feature docs with exact results; restart original preview using same runtime only after checks. Verify original case/chat unaffected, stop test services, leave original preview running.

## Completion ledger

Tasks 1–4 complete. New APIs and UI, contextual repair proposals, source synchronization and inline todos implemented. Review P2 findings (old-payload date preservation and composite source version labeling) fixed with failing reproductions and passing covering tests; re-review clean. Final verification:199 server,57 Agent4,9 frontendAPI,build,28 aggregate browser plus6 final continuity (29 unique browser cases),actualqwen6turns,desktop/mobile console clean,original13record hash preserved. No commit/publish. Full record:docs/frontend/2026-10-22-living-continuity.md.
