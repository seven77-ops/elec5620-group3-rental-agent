# Agent 4 integration

User-approved scope: merge the teammate's Agent 4 enhancements from `/Users/seven/Downloads/final/代码` into this existing application. Preserve current listing, contract and UI work, including removal of standalone attachments and manual recommendation-report actions. Do not replace runtime databases or configuration.

## Implementation and verification

- [x] Import regression tests for the teammate's core fixes, assistance APIs and presentation helpers; confirm failures against the existing application.
- [x] Merge the five changed Agent 4 core/schema files, assistance and progress APIs, and shared-provider task additions. Retain current provider timeouts and contract prompts.
- [x] Merge aftercare forms, task editing, bond extraction/drafts/reminders, and case progress. Add the operator navigation entry.
- [x] Make submitted reviews and persistent decisions discoverable in an operator inbox, identified by case, address and source. Keep operator-key authorization and version checks. A release permits guidance only; it does not approve a deduction or move funds.
- [x] Verify submission, cross-case inbox visibility, non-release decisions, release, durable history and tenant-visible outcomes with API and isolated browser tests. Verify AI helpers using an explicit test provider; never send real user material in tests.
- [x] Run module/server regression tests, frontend tests and production build; review changes and publish a concise verification record. Reload the existing local API only after verification, preserving the active runtime directory and data. Actual runtime was confirmed as `.runtime` by matching saved cases to the running API; all four database table-content digests were unchanged after reload.

No new authentication system, government integration, payments, external messages or new chat mutation workflow is included.
