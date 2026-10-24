# Unified frontend implementation plan

> For agentic workers: apply subagent-driven-development for the backend implementation and independent review; execute tightly coupled frontend integration in this session. User approved the frontend design and requested implementation.

**Goal:** deliver the approved rental workflow with real Python module calls and durable local demo state.
**Architecture:** React/TypeScript/Vite/Ant Design communicates with a FastAPI coordination layer and SQLite; original agent directories are preserved.
**Tech Stack:** React, TypeScript, Vite, Ant Design, FastAPI, SQLite, unittest, Playwright.

## Global constraints

- Agent1 is explicitly simulated; Agent2/3/4 call original Python entry points.
- No external model, real listing, payment or message sending.
- Immutable confirmed profile versions; exact draft confirmation; stale reports cannot overwrite latest results.
- Synthetic replay clocks are separate; never refresh original observations.
- Consent precedes contract body parsing/reading; raw upload avoids multipart pre-parsing.
- Idempotent retry preserves original input and server clock; versions checked at every write.
- Tenant has no operator powers; operator authorization is configured on the server.
- Runtime uploads, DBs, generated reports and credentials remain ignored.
- API shapes are defined in api-contract.md.

## Task 1: Python HTTP adapter and durable state

Files: server/app/{main,settings,repository,profiles,contracts,aftercare}.py, server/requirements.txt, server/tests/test_api.py, server/README.md.
Interfaces: api-contract.md. Use repository transactions for immutable refs and receipts; mount all routes in create_app(runtime_dir=...) to isolate tests.

- [x] Add meaningful failing API tests: unconfirmed evaluation refuses; draft edit/confirmation binding; actual 30-row recommendation and selection; no-consent upload body not consumed/no file; receive retry/conflict; correction/version and operator gate; aftercare needs explicit confirmation and commands preserve version/idempotency.
- [x] Run `python -m unittest discover -s server/tests -v` and record missing-feature failures.
- [x] Implement API contract with actual module calls, strict server-owned references, error semantics, runtime-only files and deployment instructions.
- [x] Run new API tests and original agent/integration suites. Commit scoped server changes.

## Task 2: React app and workflow

Files: frontend/package.json, vite.config.ts, src/app, src/api, src/features, src/components, src/styles; package lock.
Consumes: all Task 1 APIs. Produces: six routed responsive views and downloadable real artifacts.

- [x] Create design tokens and concept inventory from approved Markdown scheme and generated recommendation concept.
- [x] Build shell, progress view and accessible preference form with exact summary/confirmation, input validation and stable request retry.
- [x] Implement recommendation tabs, original score/evidence presentation, version comparison and explicit selection confirmation.
- [x] Implement server consent before enabling file selection, raw upload retry, review sources/correction/questions and separate operator panel.
- [x] Implement confirmed tenancy form, M4 plans/tasks/date proposals, bond history/drafts, opt-in reminders and explicit closure.
- [x] Run TypeScript/build and browser checks against real API; fix any state/overflow/console issues.

## Task 3: End-to-end verification and handoff

Files: docs/frontend/{implementation,verification}.md, frontend/e2e or scripts, root run scripts.

- [x] Exercise core path and failure gates in browser; verify refresh and saved exports.
- [x] Inspect desktop and 360/768/1440 widths, keyboard/focus and long content. Compare screenshot against concept and note intentional data-driven deviations.
- [x] Run full regression suites, frontend build and API boundary tests. Record actual outputs and limitations.
- [x] Review whole diff, fix important findings, commit only related source/docs/lockfile; create and attach draft PR if publishing authorization is established, otherwise provide concrete reviewable local branch.

## Progress

- Repository baseline: b06614de1c7825d7fbc4bcc773a75efa4eb1da97; latest remote main fetched 2026-10-17.
- Isolated clean checkout: .workspaces/frontend-demo, branch codex/frontend-demo.
