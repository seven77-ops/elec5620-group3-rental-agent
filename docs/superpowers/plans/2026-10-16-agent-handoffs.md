# Agent 1 input examples and Agent 3 packaging implementation plan

> **For agentic workers:** Execute inline with the executing-plans workflow; the user has authorised these two selected tasks. No delegated agents are needed.

**Goal:** Supply the agreed Agent 1 → Agent 2 synthetic input examples and make the existing Agent 3 README commands work from `agent3/`.

**Architecture:** Keep the strict RentalProfile body separate from case, task and confirmation metadata. Examples describe a proposed coordination envelope, not an implemented Agent 1 service or authenticated approval. Move tracked Agent 3 files into its existing README directory without changing their bytes. A repository integration test runs the existing Agent 2 and Agent 3 CLIs with synthetic data only.

**Tech Stack:** Python 3.11+, unittest, jsonschema==4.25.1, pypdf>=6.0,<7.0, existing JSON Schemas and CLIs.

## Global constraints

- No real tenant data, contracts, external models or live listing requests.
- `caseId` and `searchId` are distinct; only searchId maps to search_id.
- RentalProfile schema 1.0 and scoring rules-1.0 remain unchanged.
- Agent 1 implementation and human/team integration approval remain unverified.
- Never send messages to teammates; the user will speak to Chenyang.

## Tasks

- [x] Create `integration/agent1-to-agent2/confirmed-profile.json` and `handoff.json`, plus their field mapping and confirmation/version/retry instructions in `integration/README.md`.
- [x] Add `integration/tests/test_handoffs.py`: verify the documented Agent 3 working directory, fixture references, a fresh selected packet, request replay, and conflict escalation. Run the directory test before moving files and confirm `No module named contract_agent`.
- [x] Move each tracked file below `agent3 /` to the matching path below `agent3/` with git mv; refuse any destination collision. Update root navigation and Agent 3 documentation.
- [x] Run Agent 2's 71 tests, Agent 3's 25 tests, repository integration tests, compile checks and diff checks. Record actual results and logs in `integration/reports/2026-10-16/` and confirm original moved file bytes are unchanged.
- [x] Review changes, commit and publish PR #1. Independent read-only review approved the change and independently confirmed 71 + 25 + 6 passing checks. Integrate via the PR and verify remote main before reporting completion.
