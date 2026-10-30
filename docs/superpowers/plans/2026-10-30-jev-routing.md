# Jev routing integration

User-approved scope: add an independent OpenRouter Jev client, leave its key empty, and connect classification, existing business execution and RAG answering. Keep Alibaba generation/retrieval configuration and all existing confirmation/version/operator boundaries.

- [x] Add failure-first tests for the Decisions protocol, secret handling, deadlines, configuration, routing policy, shadow behavior and assistant/RAG integration.
- [x] Implement `JevProvider` with the fixed HTTPS Decisions endpoint, pinned model default, separate key and strict typed-response validation. Add empty placeholders to backend configuration only. Default mode is `off`; `shadow` and `active` need explicit configuration.
- [x] Add a state-aware router: exact explicit continuations first; bounded nonblocking shadow classification; provisional configurable thresholds for active acceptance; uncertain/error fallbacks. Accepted business domains narrow the existing extraction schema; knowledge goes to the existing public RAG; mixed-domain requests ask what to handle first.
- [x] Preserve validated intents, known-listing references, source/citation checks, current snapshot binding, retry receipts and explicit write/AI consent. Record metadata-only routing diagnostics without copying transcript or credentials.
- [x] Add labelled bilingual evaluation fixtures and an offline policy evaluation CLI; labels are proposed baseline fixtures, not evidence of measured Jev accuracy. Actual Jev API testing remains unavailable until a key is provided.
- [x] Run targeted and broader assistant/RAG/provider tests, browser regression, build and independent code review. Update the architecture/runbook, reload the existing website using its actual runtime, and verify user data remains unchanged.
