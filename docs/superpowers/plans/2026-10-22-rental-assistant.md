# Unified Rental Assistant Implementation Plan

> For agentic workers: use subagent-driven-development for bounded tasks and review integration in the parent.

**Goal:** Deliver persistent conversation-driven rental assistance and a concise white/blue UI across the existing workflow.
**Architecture:** Shared page and typed backend assistant; Agent1 adapters own confirmed preference edits, Agent2 catalog owns facts and reports, Agent3/4 remain explicit handoffs. Reuse current model transport with dedicated structured tasks.
**Tech Stack:** Existing Python/FastAPI/SQLite, React/Ant Design/Vite; no new dependencies.

## Global Constraints
- Work only in .workspaces/frontend-demo; preserve existing uncommitted changes. Do not commit.
- Follow docs/superpowers/specs/2026-10-22-rental-assistant-design.md API contract exactly.
- Preserve #174EA6 and white surfaces. No invented data, photographs or provider success.
- Backend external calls outside transactions; strict case ownership, revision and request identity; proposal application requires explicit confirmation.
- Preference edits flow through Agent1 and real evaluations; no bypass to legacy synthetic data or contract handoff.

## Task 1 — Backend assistant
Files: new server/app/assistant/{service,intents,tools,routes}.py as needed, server/app/ai/provider.py, server/app/routes.py, server/tests/test_assistant_api.py.
- [x] Add tests first: endpoint initially 404, then real responses through an injected model fake (transport boundary only).
- [x] Implement API contract, model intent task/schema validation, real catalogue tools, proposal lifecycle and Agent3/4 handoffs.
- [x] Verify: .venv/bin/python -m unittest server.tests.test_assistant_api and relevant existing tests.

## Task 2 — Frontend assistant and visual refinement
Files: frontend/src/api/assistant.ts, frontend/src/features/assistant/*, frontend/src/app/App.tsx, frontend/src/features/RealRecommendations.tsx, frontend/src/styles/* and frontend/e2e/assistant.spec.ts.
- [x] Add browser regression for shared navigation, welcome, message sending and history restoration.
- [x] Implement shared chat, history, actionable proposal confirmation, real fact cards, loading/retry/consent and accessible composer. Keyboard submit must respect IME composition.
- [x] Condense redundant recommendation banners/filter descriptions into compact state and optional details while keeping source/unknowns available.
- [x] Verify TypeScript/Vite build; browser flow in isolated server, desktop and 360px mobile, no errors or horizontal overflow.

## Task 3 — Integration, reference comparison and review
- [x] Inspect reference chat screenshot and current site; record only useful design observations in implementation notes.
- [x] Verify live model on isolated case, user-visible generated data and proposal/report/card identity.
- [x] Run backend regression, Agent1 regression, API tests and changed browser tests.
- [x] Review backend/frontend for spec compliance and critical concurrency/confirmation errors; repair findings.
- [x] Restart user preview with original runtime and read-only verify original case survives. Stop isolated test servers.
