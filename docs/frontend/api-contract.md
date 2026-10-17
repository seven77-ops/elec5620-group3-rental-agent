# Web integration contract

The implementation follows `2026-10-17-frontend-handoff.md` and `2026-10-17-frontend-plan.md`. This is the agreed browser/server boundary for implementation.

Base URL `/api/v1`. Responses are JSON except uploads/downloads. Errors: `{error:{code,message,request_id,fields?}}`. Tenant is a server-configured local demo identity. Operator routes require `X-Operator-Key` matching a server-only configured value, obtained by the human from local startup instructions; browsing a route or passing actor_role grants no permissions. No production auth claim.

## Data

CaseState: `{case_id,search_id,draft:{draft_id,revision,profile,fingerprint},confirmations:[{version,fingerprint,profile,confirmed_at}],evaluations:[{run_id,profile_version,created_at}],selection:SelectedListingEvidence|null,reviews:[{review_id,version,status}],aftercare_case_id:string|null}`. Optional additional metadata can be added without changing existing fields. New case has a saved unconfirmed profile template with unique search_id. Profile versions are allocated by server confirmation; client cannot silently rewrite immutable versions.

`GET /health` gives health.
`GET /demo-config` gives `{mode:'synthetic_demo',clocks:{evaluation,selection,contract,aftercare},profile_template,tenancy_template,agreement_examples:[{id,name}],capabilities}`. Tenancy template is the actual M4 sample tenancy with confirmed false and source labels; do not create automatically. `GET /demo-agreements/{id}` downloads allowlisted synthetic examples normal and rent_conflict.
`POST /cases {}` and `GET /cases/{caseId}` return CaseState.
`POST /cases/{caseId}/profile-drafts {expected_revision,profile}` returns CaseState. Validate saved drafts conservatively; field validation errors may be returned without mutating old state. Server sets search and confirmation version, does not trust client changes to them.
`POST /cases/{caseId}/profile-confirmations {draft_revision,fingerprint}` returns CaseState. Only exact saved draft can be confirmed. Editing invalidates current-draft confirmation.
`POST /cases/{caseId}/evaluations {request_id,confirmation_version}` returns `{run_id,report,comparison}`. Refuse if current draft is unconfirmed. comparison null if incompatible or no prior run; optional comparison_error describes why. Store immutable inputs and results.
`GET /evaluations/{runId}` returns `{run_id,report,comparison}` with optional comparison_error. Bind to saved case/input.
`POST /cases/{caseId}/selections {request_id,run_id,listing_id,confirmed:true}` returns SelectedListingEvidence. Reject stale/current-version mismatches, rebuild evidence using original snapshot and fixed disclosed selection clock.

## Contract

`POST /cases/{caseId}/contract-consents {confirmed:true}` returns `{consent_id,active:true}`. Revocation: same route `{confirmed:false,consent_id}`. Review requires current saved selection.
`GET /cases/{caseId}/contract-consents` returns `{consents:[{consent_id,active,recorded_at,revoked_at?,selection_current}]}` for refresh/revocation recovery. `selection_current` requires exact saved evidence equality and a current confirmed profile. No filenames or keys are exposed.
`POST /cases/{caseId}/contract-reviews` is a RAW BYTES upload, not multipart. Headers `X-Consent-Id`, `X-Request-Id`, `X-Filename` (URL-encoded filename), `Content-Type:application/octet-stream`. Before any request body reading or disk write, verify consent and saved case/selection, then enforce max 2,000,000 bytes while streaming. File suffix allowlist TXT/DOCX/PDF. Only synthetic-contract demo is supported and clearly labeled. Freeze request identity including consent reference; retry same content/selection/date/consent returns original review. Return `{review,newly_created}`. Store generated opaque file reference in ignored runtime directory, never client path.
`GET /contract-reviews/{reviewId}` returns raw ContractReview.
`GET /contract-reviews/{reviewId}/context` returns `{case_id,consent_id,consent_active}` from the saved association. `consent_active` additionally requires current selection equality; historical reads remain allowed after revocation. Legacy unbound reviews return `consent_id:null,consent_active:false`.
`GET /contract-reviews/{reviewId}/history` returns `{history:[{snapshot_id,review:ContractReview}]}` in insertion order, retaining snapshots of same-version question/operator changes.
`POST /contract-reviews/{reviewId}/corrections {expected_version,corrections}` returns raw ContractReview.
`POST /contract-reviews/{reviewId}/decisions {expected_version,decision,note}` requires operator header and returns raw ContractReview. Module's allowed decisions only.
`POST /contract-reviews/{reviewId}/questions {expected_version}` returns raw ContractReview. Keep prepared_not_sent.

## Aftercare

`GET /aftercare/cases/{aftercareCaseId}` returns raw M4 case. Only mapped cases allowed.
`POST /aftercare/commands {case_id,request_id,expected_version,operation,payload}` uses OUTER rental case_id. Server binds actor_id, actor_role, mapped M4 IDs and server monotonic demo as_of; ignore/reject browser identity/time overrides. Create requires `payload.tenancy.confirmed===true`, nonempty required fields, uses server tenant and generated tenancy_id/case_id, validates original schema, stores mapping. Body is not a raw unchecked M4 command. operator_decision requires operator header. Responses are original `{case,result,version,...}` receipts.
`GET /aftercare/template-commands` gives allowlisted `{operation:payload}` from original synthetic fixtures without identity/request/version/time. UI can use these payloads as explicitly labeled examples and expose editing. Server still validates.

## Downloads

`GET /cases/{caseId}/exports/selection` returns actual saved selection JSON.
`GET /evaluations/{runId}/export?format=json|markdown` returns saved report/original render_markdown.
`GET /contract-reviews/{reviewId}/export` returns saved review JSON.
`GET /aftercare/cases/{aftercareCaseId}/export` returns saved M4 case JSON.
All paths bind server-saved refs, no arbitrary paths. Browser mutations refresh CaseState, review or M4 current state as appropriate. localStorage stores case reference only.
