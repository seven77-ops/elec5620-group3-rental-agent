# Agent1 - Tenant Advice and Preferences

Yirui Chen | ELEC5620 Group 3 | UC01 / UC02 | Version 1.1.0

Agent1 collects rental preferences, asks for clarification, obtains explicit confirmation, stores immutable profile versions and hands confirmed profiles to the existing local Agent2 evaluator. This release uses English interface text, documentation, examples and presentation reports.

## Quick start

Keep `agent1/` beside the existing `agent2/`, `agent3/`, `agent4/` and `integration/` directories. From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe -m pip install -r agent1/requirements.txt
.\.venv\Scripts\python.exe agent1/main.py --demo
```

Use your actual Python interpreter if the virtual environment is elsewhere. Agent1 needs Python 3.10+; the team's Agent2/Agent3 integration recommends 3.11+. No interpreter downgrade is required solely because an older release omitted a file encoding. All Agent1 text-file reads now specify UTF-8 explicitly.

`--demo` is a scripted demonstration: extraction and tenant approval are simulated; the actual Agent2 evaluator is called with synthetic listings. It does not test live LLM quality. Expected counts are 15 eligible candidates in the first run and zero in the second run after a deliberately restrictive budget change.

## Manual review and confirmation

```powershell
.\.venv\Scripts\python.exe agent1/main.py --manual --tenant Yirui
```

At the `You >` prompt:

```text
/load examples/demo-draft.json
/review
```

Review the values, warnings and normalised profile. Enter `/confirm TOKEN`, replacing TOKEN with the displayed confirmation token. Then run `/search` and `/export`. Confirmation saves a version; search is a separate action. `/set budget.maximum 600` creates an unconfirmed revision and requires a new review and confirmation.

`--manual` does not interpret natural language. Use `/help` to see all commands, `/fields` for supported types and `/show` for the current draft. A case ID is printed at startup; resume with `--case CASE_ID`. `/cancel` retains history but blocks further collection and searches for that case.

## Live LLM configuration

Copy `.env.example` to `.env` inside `agent1/` and set:

```dotenv
LLM_BASE_URL=https://your-provider.example/v1
LLM_MODEL=your-provider-model-name
LLM_API_KEY=your-secret-key
```

Run `main.py` without `--manual` or `--demo`. Environment variables take precedence over `.env`. The provider must support `POST /chat/completions` and JSON-object output. See the [Chat API reference](https://developers.openai.com/api/reference/resources/chat) for the request format; compatibility must be checked with the selected provider. No real API request or paid model call has been executed during this release validation.

The service receives the current message, draft and up to 12 recent conversation messages. Credentials are sent only in the request header. Remote endpoints require HTTPS; local endpoints may use HTTP. Redirects are not followed.

Generated clarification messages are requested in English. User-provided text and quoted evidence retain their original language. Model proposals are validated against allowed fields and types; evidence must quote the latest input. This does not prove semantic accuracy: the tenant must still review the extracted values. The model cannot confirm preferences, change system IDs or initiate a search.

Timeouts, truncated or invalid JSON, unsupported fields and invalid evidence preserve the existing draft. Manual `/set` corrections remain available.

## Example conversation

Use these fictional requirements to exercise live extraction after configuring your provider:

1. I need a private room for one person. My preferred budget is AUD450 per person per week, with a hard maximum of AUD550 including bills.
2. This is a synthetic demonstration. Use demo-usyd as the destination, Australia/Sydney as the timezone and 09:00 as my arrival time. I accept public transport and walking. I prefer a 25-minute commute, with a hard maximum of 40 minutes.
3. My move-in window is 2027-02-01 to 2027-02-07. I want a 12-month lease. A private bedroom is mandatory.
4. Furnishing and a private bathroom are soft preferences, with weights of 0.6 and 0.4. My overall weights are commute 0.35, cost 0.30, housing 0.20 and amenities 0.15. My preferred area is undecided and I have no additional requirements.
5. Please change my maximum budget to AUD600. Keep everything else unchanged.

Review the resulting fields before confirming. An apparently successful model response may still contain an incorrect interpretation. The dates and routes above are for the fixed synthetic Agent2 dataset, not current property availability.

## Requirements and implementation

| Requirement | Implementation | Verification boundary |
|---|---|---|
| AR-M1-01 / UC01: conversation and clarification | LLMService proposes edits; PreferenceAgent validates and applies them atomically | Mock responses and failures tested; live extraction remains unverified |
| Missing, undecided and conflicting values | Typed draft fields, null values, targeted questions and cross-field checks | Local behavioral tests |
| Mandatory versus negotiable preferences | Budget/commute hard limits, hard facilities, weighted soft facilities and explicit priorities | Unsupported hard conditions block confirmation |
| AR-M1-02 / UC02: review and confirmation | Review token binds the draft revision and preview content | Stale and duplicate confirmations rejected |
| Confirmed version storage | SQLite transaction, version increments and immutable profile rows | Rollback, reopening and version-preservation tests |
| Agent1 to Agent2 | Local Python adapter using the unchanged RentalProfile 1.0 contract | Actual evaluator called in tests and demo |
| Acceptance and retry | Persisted task ID, receipt time, fixed dataset and cached result | Failure and lost-response tests |
| AR-M1-03: no-match revision | Verify current completed result, offer revision and preserve prior version | Failed and stale feedback rejected |

`DraftReady` is not confirmation. `/review` also displays incomplete drafts and their outstanding issues. In-flight LLM processing is not stored as a persistent ProcessingInput state. Each case currently has one active session and multiple saved profile versions. Domain objects are represented by JSON records and SQLite tables rather than empty classes added only to mirror a diagram.

## Modules

| File | Responsibility |
|---|---|
| main.py | PyCharm and command-line entry point |
| preference_agent/cli.py | ConversationUI, commands and export |
| preference_agent/service.py | Collection, review, confirmation and revision |
| preference_agent/fields.py | Draft fields, questions and validation |
| preference_agent/llm.py | Configurable model transport and extraction prompt |
| preference_agent/store.py | Transactions, optimistic updates and immutable versions |
| preference_agent/handover.py | Local receiver, task reconciliation and feedback binding |
| preference_agent/comparison.py | Verified report comparison, English explanations and history labels |
| preference_agent/acceptance_demo.py | Reproducible offline version-comparison scenario |
| preference_agent/bridge.py | Existing Agent2 calls and English validation messages |
| preference_agent/report.py | English summary of structured evaluation results |
| preference_agent/demo.py | Scripted synthetic demonstration |
| tests/ | Behavioral, integration-boundary and English/encoding regression tests |

Dependencies: Python standard library, SQLite and jsonschema 4.25.1, matching Agent2. LangChain is not used in this implementation.

## Data contract and exports

| Agent1 record | Agent2 contract or exported representation |
|---|---|
| caseId | Retained in the coordination envelope, separate from searchId |
| searchId | profile.search_id; stable across revisions within a case |
| profileVersion | profile.profile_version; increments on new confirmation |
| confirmedBy / confirmedAt | Confirmation metadata outside the strict profile body |
| sourceDraftId / reviewedDraftRevision | The draft and revision approved by the local user action |
| Original budget period | Normalised to week in the review preview; original values retained |
| Areas and additional conditions | Retained in draftSnapshot; unsupported hard conditions block handover |
| profile and dataset fingerprints | Used to bind returned results to the saved version and snapshot |

After a search, `/export` creates `rental-profile.json`, `confirmation.json`, `handoff.json`, `handover.json`, `recommendations.json` and `recommendations.md`. It also writes `export-context.json` with task history and current/historical binding labels. Before a search it exports the confirmed profile, confirmation record and context only. It does not invent a task or acceptance receipt.

`handoff.json` follows the team's proposed envelope fields. Its profileFile points to the accompanying rental-profile.json. It is a local prototype envelope, not a deployed network API. `handover.json` contains the internal execution status.

`recommendations.md` is Agent1's English presentation of structured fields. `recommendations.json` is the unchanged Agent2 response and may contain source-language explanations, including Chinese. It is deliberately preserved for traceability and exact comparison. Scores, evidence, hashes and upstream results are not translated or recomputed for presentation. User-provided text and pre-existing database history are also preserved, not silently translated.

## Limits and persistence

### Version comparison and input recovery (1.2.0)

`/history` labels results as current, historical or outdated for the current unconfirmed draft. Historical reports and immutable confirmed profiles remain saved. A late old response may complete its own stored task but cannot replace the latest task pointer.

After confirming and searching a revised profile, run `/compare` to compare with the most recent completed earlier version on the same data snapshot, or `/compare 1` to choose an earlier version. The current version must have a completed report. Cross-search, cross-snapshot, different assessment-time and mismatched report/run references are rejected. Comparison calls Agent2's existing `compare_reports(before, after)` and covers every candidate, including pending, excluded and duplicate records. Only eligible records have formal scores and ranks.

The terminal comparison is English and shows eligibility, scores, ranks, input changes, change reasons and all four dimension contributions. These English reasons are derived from structured fields, not a translation of upstream prose. `/export` adds `comparison.json` (unchanged upstream comparison), `comparison.en.json` and `comparison.md` when a comparable earlier result exists. Raw upstream reasons may contain Chinese. Comparison failures are displayed and recorded in `export-context.json`; they are never silently treated as successful comparisons. Comparison files are derived exports, not replacements for either stored recommendation report.

In manual mode, ordinary text and pasted output do not change session state or invalidate confirmation. Pasted `You >` or `Agent1 >` prefixes are rejected with guidance. If a session from an older release is stuck in ProcessingError after confirmation, `/recover-confirmed` explicitly dismisses the failed input only if the draft exactly matches the last confirmed snapshot. It does not create a version, change preferences or trigger evaluation. A revised draft cannot use this recovery command to bypass confirmation. Genuine model failures still invalidate an unconfirmed review.

Run the new offline acceptance scenario from the repository root:

```powershell
.\.venv\Scripts\python.exe agent1/main.py --acceptance-demo
```

It creates a separate synthetic case and checks confirmation gating, pasted input, repeated requests, commute priority, budget priority (DEMO-012 first; DEMO-002 from rank 9 to 3), budget tightening, and a new campus without route evidence. Results and comparisons are exported under `agent1/reports/acceptance-CASE_ID/`. This is not a live LLM session, joint test or Sprint Review.

The default database is `agent1/state/agent1.sqlite3`. confirmedBy is a local label, not authenticated identity or a signature. SQLite protections guard normal application writes, not an administrator with direct database access.

The same case, profile version and dataset reuse a task ID. Acceptance and completion are separate states. A partial Agent2 report can still be a completed evaluation. Concurrent retries may repeat pure computation, but use one logical task; this is not distributed exactly-once delivery. A revised draft must be confirmed before another search. An active synchronous evaluation cannot be interrupted by a second command in the same CLI thread.

Agent2 currently does not filter preferred areas, assess unsupported soft requirements or check property capacity. Such limitations appear during review. Unsupported hard requirements are not silently removed. There is no general mapping from real campus names to destination IDs.

No real listings, map services, network agent API, login system or complete human-review console is provided. Agent1 does not automatically select a property, process a contract or start Agent3/Agent4. Those actions require their own inputs and consent.

## Tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s agent1/tests -v
```

See VALIDATION.md for results and unverified areas. Local tests and a scripted demo do not establish live LLM accuracy or compliance with every course marking criterion.
