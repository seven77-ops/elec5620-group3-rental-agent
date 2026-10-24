# Lease draft generation implementation plan

**Goal:** Agent3 becomes a contract assistant with official NSW standard-form draft generation alongside existing document review.

**Approved scope:** NSW ordinary whole-property residential tenancies, confirmed draft inputs, immutable source/version references, explicit AI opt-in for text-to-fields assistance, current official form with draft markings and blank signatures. No automatic agreement, signature, application submission or arbitrary AI-written legal terms.

**Architecture:** Separate adapter-owned lease draft records freeze selected candidate, confirmed search profile and user-recorded follow-up. A pinned official PDF and explicit field map preserve standard terms. Saved versions export interactive PDFs with a draft cover, no sign-ready claim and no automatic legacy review approval. AI returns strictly grounded optional field suggestions and missing-field questions; only user-confirmed saves create draft versions.

## Tasks
- [x] Download and inspect the official 21 September 2026 form; pin URL, SHA256 and field mappings. Add PDF exporter with canonical AcroForm/widget consistency checks, Unicode appearance rendering, draft cover and page marks. Verify logical values and visual render, including Chinese names.
- [x] Write failing integration tests for context prefill (never infer agreed rent, term, landlord or capacity from ad/defaults), save/retry/versioning, current-source checks, per-case ownership, whole-property restriction, missing/invalid fields and historical PDF downloads. Implement strict lease fields, source fingerprint, durable versions and endpoints.
- [x] Write failing AI tests for consent, grounded field extraction, rejected hallucinations, no state mutation before confirmation, duplicate requests and changed source rejection during external calls. Implement separate lease_draft_extract task with sanitized call metadata and server-generated missing-field questions.
- [x] Build ContractAssistant and LeaseDraft React panels with two modes, editable prefill, source labels, missing-field prompts, AI review/apply, confirm-save, history and version-specific PDF download. Rename real-mode navigation to 合同助手 and route chat generation requests to draft mode; retain original contract review and legacy demo behavior.
- [x] Add browser integration tests for manual/AI draft preparation, confirmed save, versioning/reload/PDF download, existing-review handoff, no-selection and mobile layout. Run server tests, frontend build/API tests, scoped browser regression; inspect desktop/mobile and PDF screenshots.
- [x] Review code, repair concrete findings, restart original preview without changing its saved case. Document template/version provenance, scope and validation results. Do not commit or publish.

## Interfaces
- GET `/api/v1/cases/{case_id}/lease-drafts/context`: candidate/profile/followup source token, conservative defaults, required questions, template metadata.
- GET/POST `/api/v1/cases/{case_id}/lease-drafts`: summaries / `{request_id,context_token,draft_id?,expected_version,confirmed:true,applicability_confirmed:true,fields}`; draft-only state.
- GET `/api/v1/cases/{case_id}/lease-drafts/{draft_id}?version=N`: exact saved version, frozen sources and outstanding information.
- GET `.../{draft_id}/pdf?version=N`: interactive PDF for this saved version; historical downloads readable.
- POST `/api/v1/cases/{case_id}/lease-drafts/proposals`: `{request_id,context_token,message,current_fields,allow_external_ai:true}` -> grounded patch, questions, sanitized call; no draft creation.

## Verification commands
- `.venv/bin/python -m unittest server.tests.test_lease_drafts`
- `.venv/bin/python -m unittest discover -s server/tests`
- `npm --prefix frontend run build` and `npm --prefix frontend run test:api`
- isolated preview 5195/8015 with existing assistant test fixture; `candidate-followup`, `lease-draft`, `assistant`, `agent2-real`, `workspace-sync` browser specs
- Poppler render saved export's cover, filled pages and signature page; inspect values in both get_fields and effective widget values/appearances.
