# Area Evidence Implementation Plan

> **For agentic workers:** Execute this plan inline, task by task, with verification before completion.

**Goal:** Add source-bound area advice and lifestyle context to the existing rental conversation and commute recommendations.

**Architecture:** Curated JSON evidence is loaded by a small Python retrieval service. The model emits only structured area names and lifestyle topics; server code joins evidence and real inventory. React renders the same evidence cards in chat and shared commute results.

**Tech Stack:** Python, FastAPI, jsonschema, unittest, React, TypeScript, Ant Design, Playwright.

## Global Constraints

- Preserve existing user cases and uncommitted changes.
- No AUO extraction or bulk address export; no paid API or new dependency.
- Unknown quietness, safety, exact distance and commute remain unknown.
- Never turn an LGA observation or resident opinion into a property fact.
- Lifestyle inputs remain conversation-only and do not silently write the confirmed profile.

### Task 1: Source-bound retrieval

- [x] Add `server/tests/test_area_evidence.py` covering source dates, unknown areas, stale evidence, geographic scope, no quiet/safety guarantees, explicit topic matching and inventory constraints; run it and confirm missing implementation failure.
- [x] Add `agent2/data/areas/sydney-evidence.json` with verified short summaries for 12 existing suburbs and `server/app/areas/evidence.py` exposing `AreaKnowledge`, `advice(catalog, brief, areas=None)` and `fingerprint`.
- [x] Run `.venv/bin/python -m unittest server.tests.test_area_evidence -v` and resolve failures.

### Task 2: Chat and commute integration

- [x] Add integration tests in `server/tests/test_assistant_areas.py`: multi-turn retention/clearing, supported and uncovered areas, strict model schema, safe no-profile-write behavior, inventory constraints, commute enrichment without changing eligibility.
- [x] Extend brief schema with `lifestyle_priorities`; add `area_advice` intent with `areas` and `brief_patch`; expose supported topics to the model and define exact routing examples in `server/app/ai/provider.py`.
- [x] Connect the advice service in `server/app/assistant/service.py` and attach matching evidence to commute reports in `server/app/commute/planner.py`. Store evidence fingerprint and reject stale shared previews after dataset changes.
- [x] Run new integration tests and existing assistant/commute tests.

### Task 3: Shared UI and user verification

- [x] Add `AreaAdvice.tsx` and `areaAdvice.css`, typed API fields, and render in chat and inside shared commute cards. Show topic labels, evidence type, geography, dates, missing topics and inventory facts.
- [x] Add Playwright coverage for area comparison, source expansion, dataset gaps, chat-to-recommendation reuse and 360px layout.
- [x] Run backend suite, TypeScript/build and relevant browser tests; review changes and record coverage and limitations in `docs/frontend/2026-10-24-area-evidence.md`.
