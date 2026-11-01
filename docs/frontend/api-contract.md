# Web integration contract

The implementation follows `2026-10-17-frontend-handoff.md` and `2026-10-17-frontend-plan.md`. This is the agreed browser/server boundary for implementation.

Base URL `/api/v1`. Responses are JSON except uploads/downloads. Errors: `{error:{code,message,request_id,fields?}}`. Tenant is a server-configured local demo identity. Human review opens directly without an operator key. The server assigns the fixed local reviewer identity; request bodies still cannot override actor_role. No production auth claim.

## Data

CaseState: `{case_id,search_id,draft:{draft_id,revision,profile,fingerprint},confirmations:[{version,fingerprint,profile,confirmed_at}],evaluations:[{run_id,profile_version,created_at}],selection:SelectedListingEvidence|null,reviews:[{review_id,version,status}],aftercare_case_id:string|null}`. Optional additional metadata can be added without changing existing fields. New case has a saved unconfirmed profile template with unique search_id. Profile versions are allocated by server confirmation; client cannot silently rewrite immutable versions.

`GET /health` gives health.
`GET /demo-config` gives `{mode:'synthetic_demo',clocks:{evaluation,selection,contract,aftercare},profile_template,tenancy_template,agreement_examples:[{id,name}],capabilities}`. Tenancy template is the actual M4 sample tenancy with confirmed false and source labels; do not create automatically. `GET /demo-agreements/{id}` downloads allowlisted synthetic examples normal and rent_conflict.
`POST /cases {}` and `GET /cases/{caseId}` return CaseState.
`POST /cases/{caseId}/profile-drafts {expected_revision,profile}` returns CaseState. Validate saved drafts conservatively; field validation errors may be returned without mutating old state. Server sets search and confirmation version, does not trust client changes to them.
`POST /cases/{caseId}/profile-confirmations {draft_revision,fingerprint,review_token}` returns CaseState. Only exact saved draft can be confirmed. Editing invalidates current-draft confirmation.
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
`POST /contract-reviews/{reviewId}/decisions {expected_version,decision,note}` returns raw ContractReview. Module's allowed decisions only.
`POST /contract-reviews/{reviewId}/questions {expected_version}` returns raw ContractReview. Keep prepared_not_sent.

## Aftercare

`GET /aftercare/cases/{aftercareCaseId}` returns raw M4 case. Only mapped cases allowed.
`POST /aftercare/commands {case_id,request_id,expected_version,operation,payload}` uses OUTER rental case_id. Server binds actor_id, actor_role, mapped M4 IDs and server monotonic demo as_of; ignore/reject browser identity/time overrides. Create requires `payload.tenancy.confirmed===true`, nonempty required fields, uses server tenant and generated tenancy_id/case_id, validates original schema, stores mapping. Body is not a raw unchecked M4 command. operator_decision does not require an operator header. Responses are original `{case,result,version,...}` receipts.
`GET /aftercare/template-commands` gives allowlisted `{operation:payload}` from original synthetic fixtures without identity/request/version/time. UI can use these payloads as explicitly labeled examples and expose editing. Server still validates.

## Downloads

`GET /cases/{caseId}/exports/selection` returns actual saved selection JSON.
`GET /evaluations/{runId}/export?format=json|markdown` returns saved report/original render_markdown.
`GET /contract-reviews/{reviewId}/export` returns saved review JSON.
`GET /aftercare/cases/{aftercareCaseId}/export` returns saved M4 case JSON.
All paths bind server-saved refs, no arbitrary paths. Browser mutations refresh CaseState, review or M4 current state as appropriate. localStorage stores case reference only.

## Agent1-backed cases (2026-10-20)

New CaseState adds `agent1:{case_id,session_id,state,latest_version,review_token,draft_revision,warnings,input_mode,live_llm}` and server-owned agent1_case_id. Agent1's per-draft revision is separate from monotonic draft.revision. Form edits/confirmation call the actual member services. Confirmation must include the currently displayed review token; exact retries reuse the original confirmation. Returned warnings must be visible before approval.

Evaluation adds `agent1_task_id` and `comparison_source:"agent1_verified_versions"` to the unchanged report/comparison response. Agent1 tasks are durably reserved before actual receiver execution; retry/restart/lost-response reconciliation and current-version checks apply. Historical completed HTTP retries return their original result; an unfinished old task cannot publish over a new version.

Legacy cases without Agent1 provenance remain readable and exportable; preference/search/selection writes require a new case (`409 agent1_upgrade_required`, or the existing unconfirmed gate). Existing separately confirmed aftercare records remain available. Do not fabricate historical confirmations during upgrade. Input remains a form; live LLM extraction is disabled.

## Basic home information

`GET /cases/{case_id}/living-services/home` returns `{values,sources,profile,bookings,expected_version}` for six basic home fields: address, suburb, postcode, agent_name, agent_email and agent_phone. This endpoint is read-only. Saved location/contact groups take priority; otherwise selected listing facts, then confirmed lease/current draft facts supply reference values. Draft contacts require the same displayed address. Sources label the origin; missing data stays blank. Saved providers come from profile.utilities and all bookings (including completed services) come from the same record/version. The drawer saves through the existing versioned `/living-services/profile` endpoint with explicit confirmation, merging basic edits into the full retained profile. Conflict reload rebases untouched fields and retains only local edits. Quick service choices use the existing confirmed `/living-services/bookings` write with status considering and null date/quote; no extra selection store or external booking is created.

## Review evidence files

Upload JPEG, PNG or PDF bytes to the existing case living-services attachments endpoint (10 MiB per file). `report_issue` and `reply_review` accept optional unique `attachment_ids` (at most 10), which must belong to the outer rental case. Read responses add linked saved metadata as `attachments` on reviews. Human review uses only these server-resolved links; original report data remains unchanged.

## Flat issue reports

`POST /cases/{case_id}/issue-reports {request_id,category,description,attachment_ids}` creates a report without tenancy setup. Allowed types are rent/furniture/repairs/tenancy/moveout/post_tenancy/other. Description is original text up to 5000 characters; attachments are up to ten same-case saved IDs. Date, report ID and version are server assigned. Exact request retries are idempotent. `GET /issue-reports` lists new and historical reports in date order. `POST /issue-reports/{report_id}/advice {request_id,expected_version,note}` saves local human advice without changing the original report; note is 1–2000 characters. Receipt, version and closed-status checks prevent duplicate or stale decisions.
