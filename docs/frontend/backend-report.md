# Backend implementation report

Date: 2026-10-17. Scope: `server/`, runtime `.gitignore`, this report. Original member modules and the API contract were not modified.

## Delivered

FastAPI `server.app.main:app` and `create_app(runtime_dir=..., operator_key=...)` implement every endpoint in `docs/frontend/api-contract.md`. A single bootstrap adapts imports for the existing original Agent 2/3/4 packages. SQLite preserves rental cases, drafts, immutable confirmed versions, evaluation inputs/datasets/results, selection evidence, independent contract consents/revocations, review histories, generated upload references, M4 mapping and frozen-command receipts. Original intake and M4 databases retain ownership of their own atomic receipts.

Actual original functions called: Agent 2 `validate_profile`, `evaluate`, `compare_reports`, `build_selected_listing_evidence`, `render_markdown`; Agent 3 `load_document`, `receive_review`, `correct_review`, `approve_review`, `generate_questions`, `validate_review`, `question_list`; M4 `AftercareAgent.submit/get` and its original command schema validator. No business scoring/rules are reimplemented. Gate/status details remain the original module outputs.

Uploads authorize consent plus current saved selection before any ASGI receive, including malformed content types. Streaming caps raw bytes at 2,000,000 and revalidates consent before disk write; filenames never choose disk paths. PDF/DOCX/TXT parsing and PDF/OCR constraints remain original. Upload identity freezes content hash, suffix, consent, selected evidence and the Agent 3 rule date. Same request returns the original intake review, not a mutated later review; a changed request conflicts.

M4 accepts only `{case_id,request_id,expected_version,operation,payload}`. The rental case ID is mapped internally. Actor/role, operation clock and generated tenancy IDs are server-bound; schema validation remains original. New commands reserve their generated values durably; retries retain those values after intervening operations or a lost adapter receipt. A pending creation reserves one mapping and blocks simultaneous different creations before either can create an orphan M4 case. Original operator actions require `RENTAL_OPERATOR_KEY` via `X-Operator-Key`; tenant/config routes never disclose it. External model flags are restricted to false.

An additional compatible download route, `GET /api/v1/contract-reviews/{reviewId}/questions/export`, exposes the original ContractQuestionList with `prepared_not_sent` because raw ContractReview's strict schema does not contain that field. No requested route/response shape was changed.

The sample tenancy omits server-owned tenant/tenancy IDs and changes only `confirmed` to false. The actual sample source labels and other tenancy/evidence fields are preserved. Fixture command endpoint returns payloads, not actor/request/version/time command wrappers.

## TDD evidence

Initial test setup first hit missing FastAPI in the shell's default framework Python. Created isolated `.venv`; sandbox DNS restricted initial pip access. Dependency installation then succeeded via approved sandbox escalation. No global Python installation was changed. Stable tested direct dependencies are pinned in `server/requirements.txt`; the environment graph is in `server/requirements-lock.txt`.

RED: the first seven tests failed with the explicit assertion `HTTP adapter has not been implemented` before `main.py` existed. GREEN: those seven passed after the initial implementation using the actual member code.

Further RED/GREEN cycles found and fixed:

- A second request for the same deterministic evaluation run overwrote its saved comparison. Failing equality test now passes; saved run inputs/results remain immutable.
- Boolean `confirmation_version:true` matched version 1 in Python. It now returns 422.
- Default JSON parsing accepted duplicate/nonfinite keys/numbers. Strict route parsing now returns `invalid_json`.
- The M4 full fixture workflow initially could not deliver future reminders under a seconds-only clock. Server clocks now progress to allowlisted original scenario checkpoints for polling and closure.
- Concurrent different M4 creations raced and could create two module cases. The forced-interleaving test failed before pending mapping reservation, and now verifies one durable module case.
- Original question packet export returned 404 before its route existed; now uses original `question_list`, including empty questions and `prepared_not_sent`.
- A JSON content type on an unauthorized raw upload caused generic strict parsing to read its body. A direct-ASGI regression captured the receive call; raw upload routes now exclusively own body processing and reject before receiving.

Final boundary suite: **17 tests passed**. No fake agent result fixtures or mocked business outputs. One concurrency test pauses the real module submit with an event to force the unsafe interleaving; it then invokes the actual submit and inspects SQLite case count.

## Executed verification

All commands executed from the isolated frontend-demo worktree using its `.venv`:

| Command | Actual result |
|---|---|
| `.venv/bin/python -m unittest discover -s server/tests -v` | 17 passed |
| `(cd agent2 && ../.venv/bin/python -m unittest discover -s tests -v)` | 71 passed |
| `(cd agent3 && ../.venv/bin/python -m unittest discover -s tests -v)` | 25 passed |
| `(cd agent4 && ../.venv/bin/python -m unittest discover -s tests -v)` | 57 passed |
| `.venv/bin/python -m unittest discover -s integration/tests -v` | 6 passed |

Normal API workflow asserts 15 eligible candidates from the real synthetic dataset, selects DEMO-006 and obtains Agent 3 `Reviewed`. Rent $650 sample produces `Awaiting Human Review`; tenant approval is 403, question generation is blocked until an operator approval, corrections increment version and invalidate questions. The original M4 18-command workflow keeps the planned edit/date changes, blocks the disputed draft, releases only via original operator conditions, delivers reminders at the declared polling checkpoint and reaches `Resolved` with retained history/export.

Real HTTP smoke check: started uvicorn on loopback port 8011 (sandbox escalation required for binding/connect), received 200 for health, OpenAPI (24 paths), and actual case creation, then shut down the temporary process. `compileall`, `pip check` and `git diff --check` also passed.

Direct ASGI tests show zero receive calls without active consent; streamed upload testing omits content length and crosses the byte limit with two chunks, leaving no upload file. Persistence tests reopen `create_app` on the same runtime; receipt recovery removes only the adapter's result then verifies the real M4 receipt reproduces the exact response.

## Limits and operating notes

Local synthetic demo only. Operator key access control does not implement production user login, multi-user isolation or network deployment. No real Agent 1 conversation/model integration or automatic M3→M4 lease confirmation is claimed. In-app reminders require explicit command polling; there is no background delivery guarantee.

Evaluation, selection and contract reference clocks remain separately disclosed. Each M4 case starts at 2026-10-15 10:00 +11, advances at least a second per new command, and uses original allowlisted 2026-11-03 09:00 polling / 09:01 closure checkpoints. Current clock is visible in the returned case; the browser cannot override it. Old receipts preserve their original timestamps.

Raw uploaded contracts are retained under ignored runtime storage until the user deletes that local runtime; this version does not add a retention/deletion API. Runtime contains synthetic data only. JSON request size has a separate 256,000-byte bound. Browser errors hide application/runtime absolute roots and stack traces.

Original module receipts and adapter coordination use separate databases; they are not one cross-database transaction. Recovery uses the original frozen commands and stable intake IDs. New M4 logical requests with failed business validations may reserve a receipt identity; retrying changed input requires a new request ID, as documented. A crash during create leaves a pending marker recoverable by retrying the original request.

Startup, operator setup and exact request/download examples: `server/README.md`. Browser UI acceptance and performance/user-study claims belong to parent integration verification, not this backend report.
