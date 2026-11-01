# Candidate follow-up implementation plan

> Execute inline in the existing `codex/local-ai-integration` workspace. User approved the candidate → enquiries → real contract design. Preserve all existing changes; do not commit unrelated work.

**Goal:** A saved real candidate has useful next actions in recommendations and chat, durable user-recorded facts, and independent real contract intake with factual comparison.

**Architecture:** A case/selection-bound follow-up object stores versioned user statements separately from immutable public ads. Contract consent binds the exact current candidate; real contracts use Agent3's existing optional-selection review entry point with `selection=None`. A separately frozen real context supports comparisons without manufacturing legacy verified evidence.

**Tech stack:** FastAPI, existing SQLite object repository, Agent3 Python functions, React/AntD, Playwright.

## Constraints
- Public advertisements remain unverified; no synthetic replacement, automatic verification, messages sent to agents, or claims of application submission/signing.
- User must explicitly save follow-up facts and independently consent to contract processing. External AI retains its existing separate per-action consent.
- Current profile and exact candidate checks, optimistic follow-up revisions, immutable history and durable request receipts protect stale tabs/retries.
- Real contracts use the current Sydney date; stale rule packs remain degraded. Legacy demo clocks and contract behavior stay compatible.
- Existing reviews remain readable after candidate/profile changes. Their original consent cannot authorize further writes against a new candidate.

## Task 1 — Durable candidate follow-up
- [x] Add `server/tests/test_candidate_followup.py`: select a real ad; GET `/candidate-followup`; POST a confirmed record with selection signature/version; restart and assert facts persist while the original ad/selection remains unchanged. Assert stale version, candidate switch, cross-case reference, invalid dates/numbers and duplicate request conflicts fail.
- [x] Run `.venv/bin/python -m unittest server.tests.test_candidate_followup` and observe missing-route failures.
- [x] Implement `server/app/adapters/candidate_followup.py`: read/save/export, per-selection digest identity, strict nullable fact fields and user-recorded provenance. Register routes in `server/app/routes.py`.
- [x] Rerun the test module.

## Task 2 — Real candidate contract intake
- [x] Add tests for consent before upload, real review with `selection_evidence=None`, frozen ad/profile/follow-up context, comparable user-recorded rent differences, unknown ad rent scope, corrections updating comparisons, retries/revocation and stale selection.
- [x] Add `Services.contract_selection` for current real candidate authorization while retaining the legacy `selected` guard. Modify only contract consent/upload authorization to use it.
- [x] Real uploads call `review_agreement` using Sydney's current date; save `real_context` beside the original Agent3 review. Add `server/app/adapters/real_contract.py` to calculate documentary comparisons; expose them through existing context and export routes. Never append invented verified evidence.
- [x] Run new tests plus legacy contract and AI tests. Update old real-data tests to assert consent alone does not verify candidates.

## Task 3 — Connected UI and chat intent
- [x] Add typed follow-up API and shared `CandidateFollowup.tsx`: compact candidate card, enquiry checklist, editable user-recorded facts, explicit save, download questions, and an existing-contract action. Embed in recommendations and assistant; handle stale selection, load failures and 360px layout.
- [x] Add `followup` to strict AI intent schema/prompt; server answers from saved candidate and routes to the shared follow-up drawer. No model-written facts saved automatically.
- [x] Remove the real-candidate dead end in Contract, adapt upload copy/controls for real documents, show frozen baseline comparisons and source notes; retain legacy demo behavior.
- [x] Add Playwright integration coverage: save facts → reload/open chat → existing contract → independent consent → upload → rent comparison; mobile drawer; no-candidate and historical selection guards.

## Task 4 — Verification and documentation
- [x] Run server unit suite, frontend build and scoped browser suites on an isolated runtime. Visually inspect desktop/mobile screenshots.
- [x] Restart only the original preview API if needed, preserving user data. Read-only verify the user's current case UI.
- [x] Document capabilities, limits and verification in `docs/frontend/2026-10-22-candidate-followup.md`. Run `git diff --check` and summarize usable next steps.
