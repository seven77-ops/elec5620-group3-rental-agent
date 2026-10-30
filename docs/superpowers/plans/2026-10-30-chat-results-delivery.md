# Chat results delivery implementation plan

> **For agentic workers:** Use TDD and focused parallel implementation of independent contract and repair domains; review together before release.

**Goal:** Deliver natural repair email drafts and independently uploaded contract review results inside chat.

**Architecture:** Repair generation reuses the existing bounded email AI adapter; the exact preview becomes a version-bound saving proposal. Contract upload gains explicitly scoped document consent, with all existing selected-listing consent gates preserved. Reusable React cards render results in the assistant; pages remain available for history and detailed follow-up.

**Tech Stack:** Python/FastAPI/SQLite, React/TypeScript/Ant Design, unittest and Playwright.

## Global constraints

- Existing user data, active Jev configuration and unrelated workspace edits remain intact.
- Email drafting never sends mail; recipient absence does not block generating body text.
- Save only after explicit proposal confirmation; replay is idempotent, stale versions conflict.
- No private contacts or addresses are added to external extraction prompts; retain local recipient snapshots.
- Contract processing, private indexing and external AI each retain their existing consent boundaries; source citations and version invalidation remain enforced.

## Repair delivery

Files: `server/app/assistant/living.py`, `repair_dialogue.py`, new `repair_drafts.py`, `server/app/living/fields.py`, `repairs.py`, `service.py`, `server/app/assistant/service.py`, `server/app/ai/provider.py`; frontend `RepairDraftCard.tsx`, `Assistant.tsx`, `api/assistant.ts`.

- [x] Add `server/tests/test_chat_repair_drafts.py`: assert English polite body before any save, exact preview/save identity, repeat receipt does not regenerate, pending and saved rewrite keep one issue, unavailable generation leaves business records unchanged, missing recipient supported.
- [x] Run the new module red, then add optional language/tone schema fields and generate `repair_email_polish` from grounded issue text outside SQLite writers. Put `repair_email` preview metadata on the saved assistant message; save its exact subject/body through the proposal.
- [x] Rewrite focused pending/saved drafts through the same generator. Supersede pending proposals; preserve repair IDs, recipient snapshots and optimistic version checks. Keep existing historical template records readable.
- [x] Render preview + copy + suggested tone/language edits in a small card. Existing explicit save action remains; hide the redundant field checklist when an email preview exists.
- [x] Run new and existing living/repair/provider tests, then browser drafting/copy/rewrite/save/reload flow.

## Standalone contract review

Files: `server/app/adapters/contracts.py`, `server/app/rag/contracts.py`, `frontend/src/features/Contract.tsx`, `ContractUpload.tsx`, `knowledge/ContractKnowledgePanel.tsx`, new `contracts/ChatContractReview.tsx` and focused tests.

- [x] Write failing standalone consent/upload/review/private-Q&A/revocation tests. Existing selection-bound consents must still become invalid after selection/profile changes.
- [x] Add explicit `scope=document` consent bound to the case and originating review; maintain legacy selection scope as default. Document-only review has no fabricated listing comparison.
- [x] Allow upload with no selection in the contract page and reusable chat widget. Display grounded review fields/findings and offer source-backed follow-up; localize fallback guidance.
- [x] Embed the widget only in the active contract turn, avoiding duplicate upload forms across history. Contract details remain available through the existing page.
- [x] Run contract AI/RAG/security/intake tests and browser standalone upload/review/Q&A flow.

## Integrated verification and release

- [x] Independent code review of consent, snapshot, retry and preview/save behavior; fix material findings.
- [x] Run appropriate broader server tests, browser regressions, build and diff checks.
- [x] Record actual limitations and commands in `docs/frontend/2026-10-30-chat-results-delivery.md`.
- [x] Back up all live SQLite databases; reload only verified local 5191/8011 services and compare original table contents. Keep Jev active and preserve user cases.
