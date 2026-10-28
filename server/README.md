# Local rental journey API

Run commands from the repository root. Python 3.11+ is required; verified with Python 3.13.2. This server calls the existing `agent1`, `agent2`, `agent3`, and `agent4` modules directly. The editable preference form now uses Agent1 validation, revision-bound review tokens, immutable confirmed versions, HandoverService and verified version comparison. Form/example data is synthetic; live LLM extraction remains disabled. All examples are synthetic. No external AI or messaging is enabled.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r server/requirements-lock.txt
.venv/bin/python -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

API: `http://127.0.0.1:8000/api/v1`; OpenAPI and interactive documentation: `http://127.0.0.1:8000/docs`. The frontend uses its Vite `/api` proxy. Keep this local demo bound to loopback. Runtime databases and uploaded files are under ignored `.runtime/`; set `RENTAL_RUNTIME_DIR` on the server to choose another directory. No HTTP parameter accepts a server filesystem path. To test isolated state, import `create_app(runtime_dir=temporary_directory)`.

## Local operator key

Operator actions are disabled until the human sets a server environment variable before startup:

```sh
export RENTAL_OPERATOR_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$RENTAL_OPERATOR_KEY"
.venv/bin/python -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000
```

Use that value in the frontend's local operator key field, or send `X-Operator-Key` on an operator request. The key is never returned by `/demo-config`, case reads, errors, or any tenant endpoint. It must never be a Vite environment variable or checked-in source value. The server supplies the fixed local tenant/operator IDs. This is local demonstration access control, with no production account/session isolation claim. Operator approval is authorized only by this key, never by a browser role field.

## API flow

The canonical browser interface is `docs/frontend/api-contract.md`. Requests use bounded strict JSON, including application/json, application/*+json, and absent content type; other media types are rejected. Parsing caps streamed bytes at 256,000 and rejects unknown outer fields, duplicate JSON keys, and non-finite numbers (including numeric overflow). Errors have `{error:{code,message,request_id,fields?}}`. Saved results remain available after a failed operation.

1. `POST /api/v1/cases` with `{}`. Keep the returned `case_id` as the only persisted browser case reference.
2. `POST /cases/{id}/profile-drafts` with `{expected_revision,profile}`; the server binds `search_id` and allocates confirmation versions. `POST /cases/{id}/profile-confirmations` with the exact `{draft_revision,fingerprint,review_token}` returned in the saved case. Editing invalidates confirmation for subsequent mutations; historical versions remain immutable.
3. `POST /cases/{id}/evaluations` with `{request_id,confirmation_version}`. The original report is returned as `{run_id,report,comparison,agent1_task_id,comparison_source}`. Task execution and comparison are delegated to Agent1, whose local receiver calls the existing Agent2 evaluator. Same deterministic run never overwrites an earlier saved comparison. `POST /cases/{id}/selections` with `{request_id,run_id,listing_id,confirmed:true}` explicitly selects an eligible current-version listing.
4. `POST /cases/{id}/contract-consents` with `{confirmed:true}`. Revoke using `{confirmed:false,consent_id}`. After refresh, `GET /cases/{id}/contract-consents` restores `{consents:[{consent_id,active,recorded_at,revoked_at?,selection_current}]}`; only matching current confirmed selection yields `selection_current:true`. `GET /contract-reviews/{id}/context` restores `{case_id,consent_id,consent_active}` using the saved originating consent. That active context flag also requires the exact current confirmed selection; an unbound legacy review returns null/false. Both reads remain available for historical or revoked records and expose no upload filenames or keys. Then send raw file bytes to `POST /cases/{id}/contract-reviews` with `Content-Type: application/octet-stream`, `X-Consent-Id`, `X-Request-Id`, and URL-encoded `X-Filename` headers. This is not multipart. TXT/DOCX/PDF only, 2,000,000 bytes maximum, PDF maximum 10 pages. Consent and selection are checked before any ASGI body receive even for a wrong content type, and again before disk writes. Oversized streams leave no partial file. Use synthetic contracts only.
5. Corrections use `{expected_version,corrections}`; decisions use `{expected_version,decision:"approve"|"return",note}` and the operator header; questions use `{expected_version}`. The responses are unmodified original ContractReview objects. Each mutation requires the originating contract consent to remain active and exactly bound to the current confirmed selection, including operator decisions. The case, consent and selection gate are read inside the same serialized write transaction. Revocation preserves historical reads/downloads while blocking further analysis or writes. `GET /contract-reviews/{id}/history` returns `{history:[{snapshot_id,review}]}` in insertion order, including immutable snapshots of same-version question/operator changes. `GET /contract-reviews/{id}/questions/export` additionally exports the original ContractQuestionList with `handoff_status:prepared_not_sent`; no findings produces an empty question array.
6. Obtain actual editable M4 sample payloads from `GET /aftercare/template-commands`. `GET /demo-config` contains the sample tenancy with `confirmed:false`. Create after explicit confirmation using `POST /aftercare/commands` with `{case_id,request_id,expected_version:0,operation:"create",payload:{tenancy,evidence}}`. Here `case_id` is the **outer rental case**, while the returned case ID is the mapped M4 ID. The server replaces tenancy/tenant IDs with generated/server values. Later operations use the same outer rental case ID and current M4 version. `operator_decision` requires the operator key. For `request_draft`, both `use_model` and `allow_external_ai` must be false.

All paths above after step 1 use the `/api/v1` prefix. Downloads bind saved references: `/cases/{id}/exports/selection`, `/evaluations/{run}/export?format=json|markdown`, `/contract-reviews/{id}/export`, `/contract-reviews/{id}/questions/export`, `/aftercare/cases/{m4id}/export`.

## Clocks and retry identity

- Agent 2 evaluation snapshot: `2026-09-17T09:00:00+10:00`.
- Agent 2 explicit selection replay: `2026-09-17T10:00:00+10:00`.
- Agent 3 rule reference date: `2026-10-15`. Actual confirmation/review timestamps remain actual module/server timestamps.
- M4 starts each case at `2026-10-15T10:00:00+11:00` and advances at least one second per new reserved command. `poll_reminders` advances to the allowlisted scenario checkpoint `2026-11-03T09:00:00+11:00`, and `confirm_outcome` to `09:01`, when later than the current clock. These are disclosed synthetic scenario checkpoints, not wall-clock background delivery. Each original request retains its initial generated time even after other commands.

Retries preserve the entire submitted logical request. Reusing an ID with changed content/consent/selection/version yields a conflict. Adapter receipts and M4 frozen commands are durable before module submission; M4's own atomic receipts recover a lost adapter response. Concurrent tenancy creation reserves its mapping before module submission to prevent duplicate/orphan cases. Original module databases remain separate from the adapter's `web.sqlite3` and are not patched internally. Reviews and each subsequent saved review mutation are retained as separate immutable version snapshots, including operator/questions operations for which Agent 3 retains the same numeric field version.

Synthetic agreement downloads are allowlisted IDs `normal` and `rent_conflict`; the latter changes the sample weekly rent from $500 to $650. User filenames are presentation data only; disk names are generated opaque references under runtime storage. Missing OCR tools or unreadable text return the original resubmission error; no parsing success is fabricated.

## Verification

```sh
.venv/bin/python -m unittest discover -s server/tests -v
(cd agent2 && ../.venv/bin/python -m unittest discover -s tests -v)
(cd agent3 && ../.venv/bin/python -m unittest discover -s tests -v)
(cd agent4 && ../.venv/bin/python -m unittest discover -s tests -v)
.venv/bin/python -m unittest discover -s integration/tests -v
```

The boundary suite covers actual module results, exact confirmation and version gates, durable persistence, stale selection, immutable comparisons, before-read upload authorization, streamed size enforcement, revocation, changed-input retries, operator decisions, original question packets, mapped M4 identity, monotonic/replayed clocks, lost adapter receipts, concurrent create, and the full original M4 scenario through reminder delivery and closure. It does not substitute fake reports for member code. Detailed evidence is in `docs/frontend/backend-report.md`.

## Server organization

`app/main.py` wires the application. `settings.py` owns fixtures/server configuration, `http.py` owns strict parsing/error conversion, `routes.py` registers HTTP endpoints, and `adapters/` separates profile/evaluation/selection, contract intake/reviews, M4 coordination and shared saved-object/authorization services. `adapters/business.py` imports the original member entry points; `repository.py` owns adapter storage. Old runtime reviews created before consent binding was added remain readable; their future mutations require a new explicitly consented intake because an unbound legacy review cannot prove active originating consent.

## Agent1 integration (2026-10-20)

PR #6 is merged into main. New cases persist real Agent1 sessions/profiles/tasks in the adapter SQLite file (`.runtime/web.sqlite3`), alongside its separate adapter objects table; original member source files are unchanged. CaseState.agent1 exposes core provenance. Browser case ID and monotonic browser draft revision remain distinct from Agent1 case ID and per-draft revision. Confirmation source is `agent1`.

The Store adapter joins the existing serialized SQLite transaction for case creation, draft edits and confirmation. Failed adapter writes roll back core changes too. Confirmation requires the current review token and exact browser revision/fingerprint; exact retries reuse the immutable record. Capability warnings are shown beside the saved review and inside its confirmation dialog.

Evaluation is two-phase: atomically reserve the HTTP request and member task through the public handover API with a prepare-only receiver, commit, then call the actual local receiver through reconcileRetry. Agent1 independently commits acceptance/completion. Changed-input retries fail; lost replies reconcile one task. The current version is checked before publishing; a late response cannot replace a newer result. Comparisons use Agent1's verified stored versions and the original Agent2 comparison structures.

Legacy form-only cases retain read-only history/exports. New preference confirmations, searches and selection mutations require a new Agent1 case; historical confirmations are never invented or rewritten. Separately confirmed existing aftercare cases remain available. Old HTTP clients must read the case and include its review_token when confirming new cases.

The editable form is a supported local entry mode. LLM extraction is not enabled; the browser accepts no model credentials. Synthetic fixtures and clocks remain unchanged. After changing preferences, previous selections are explicitly historical and cannot continue contract intake until reselected.

## Optional local AI sidecars

The new `/api/v1/ai/config`, saved-evaluation `/ai-explanations`, saved-review `/ai-analyses` and explicit `/apply` endpoints are opt-in. Original rule-only endpoints stay unchanged. Configure backend-only settings using root `.env.example` and `scripts/dev.py`; see [local AI guide](../docs/frontend/2026-10-20-ai-local-run.md). No provider is enabled by default and test_stub is injected only by the isolated test app. AI candidates do not alter ContractReview until the user explicitly applies selected, cited values.
