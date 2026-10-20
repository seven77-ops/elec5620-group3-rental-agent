# Local AI Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development for scoped module implementation and reviews; execute the tightly coupled server/frontend integration in the parent session. User explicitly authorized implementation after the Markdown plan, with no further design approval pause.

**Goal:** Deliver locally reviewable Agent 3 cited extraction and risk explanation, Agent 2 grounded recommendation explanation, and matching frontend controls.

**Architecture:** Original business rules remain authoritative. New pure Agent modules accept injected JSON gateways; a shared server-only provider and durable sidecar adapter coordinate explicit consent, calls and receipts outside SQLite write locks. Users explicitly apply validated contract candidates through original correction/versioning.

**Tech Stack:** Python stdlib HTTP, FastAPI/SQLite, React/TypeScript/Ant Design, unittest, Playwright. No new provider SDK.

## Global Constraints

- Local only: no push, PR/Jira updates or other external publication.
- Baseline 2e375bb; Agent 3 GitHub tree 60d469b2ab24986124d4f4d5fc275a3ff09b944f.
- Preserve original ContractReview Schema/CLI behavior, Agent 1/4, scoring and human/consent/version gates.
- Candidate fields: address/rent_amount/start_date/end_date/rent_period/rent_scope/currency, exact original line quote required for non-null values.
- No automatic application: explicitly selected candidate fields + confirmed true, original full review digest and consent/selection checked.
- Models explain only existing findings/recommendations, cannot change status, rank, score or permissions.
- Endpoint HTTPS only, no redirects; request timeout default12 max15 seconds; browser AI budget45 seconds.
- No real-provider success claim without actual configured call. Test provider named test_stub.
- Persist AI sidecars outside original report schema; network outside SQLite transaction; original request replay and context rechecks.

### Task 1: Agent 3 cited extraction + preview explanations

Files: create agent3/contract_agent/ai_analysis.py and agent3/tests/test_ai_analysis.py. Original modules remain source of extraction/rules/correction.
Interfaces: `analyze_contract(document:dict, review:dict, gateway:Callable[[dict],dict])->dict`. Gateway input has task=contract_extract or contract_explain. Extraction response `{fields:[{field,value,line,quote}]}`. Explanation response `{explanations:[{finding_id,text}]}`. Return `{candidates:[{field,value,evidence,valid,reason}],preview_findings,explanations,explanation_status}`. Every requested field represented (unknown null if missing); invalid candidate never included in preview corrections. Evidence derives source_name/page/line from original document. Explanation errors leave candidates and deterministic preview usable.

- [ ] Add meaningful tests before code: free-text core fields with exact quoted lines accepted, invented line/quote/value refused, booleans/nonfinite/invalid ISO/duplicate/unknown fields refused; preview retains high-risk status, source review immutable, explanation IDs checked; no findings skips second call.
- [ ] Run `(cd agent3 && ../.venv/bin/python -m unittest discover -s tests -p test_ai_analysis.py -v)` and record RED.
- [ ] Implement isolated module using original `correct_review` for preview, never save or auto-approve.
- [ ] Run new tests and existing Agent 3 suite, record GREEN; scoped local commit and report.
- [ ] Independent task review with spec/quality verdicts; resolve important findings.

### Task 2: Agent 2 grounded recommendation explanation

Files: create agent2/rental_agent/ai_explanation.py and agent2/tests/test_ai_explanation.py.
Interface: `explain_recommendations(report:dict,gateway:Callable[[dict],dict])->dict`. Gateway task=recommendation_explain. Response `{items:[{listing_id,text,evidence_refs:[source_ref]}]}` with exactly the saved Top5 IDs, unique and only provided evidence refs. Return `{items}`; empty report returns empty without calling. Build compact context from saved scores, breakdowns, reasons/tradeoffs and actual evidence refs, not arbitrary browser values.

- [ ] Add RED tests for saved eligible Top5, forged/pending/duplicate IDs, unknown refs, empty report no call and immutable report.
- [ ] Implement context and strict response validator, keep engine/report schemas unchanged.
- [ ] Run new and existing Agent 2 tests, local scoped commit/report; independent review.

### Task 3: Server gateway + sidecar HTTP integration

Files: new server/app/ai/{provider,service}.py (split further by contract/recommendation responsibility if needed); modify main.py/routes.py/settings.py/adapters/services.py; minimal reusable review persistence helper in adapters/contracts.py; tests server/tests/test_ai_api.py/test_ai_provider.py; root .env.example; scripts/dev.py env loader.
Interfaces: exact six routes and envelope from docs/frontend/2026-10-20-ai-integration-plan.md. `create_app(...,ai_provider=None)` injection for transport tests only; provider exposes public_config(), `__call__(context)` and truthful per-call metadata via a recorder wrapper. API body accepts no raw prompt, paths, model overrides or key. Original agreement loaded only after saved origin consent checked.

- [ ] Provider RED tests: off/missing config, HTTPS/no redirects, strict JSON, timeout/oversize/secret-free errors, actual response request ID and usage.
- [ ] API RED tests: consent gate zero calls, current evaluation/review binding, immutable sidecar, stale snapshot rejects, explicit candidate apply creates new version once, original request conflict/replay, network can run while consent revoked (no SQLite lock held).
- [ ] Implement configured provider, pending reservation + immutable receipts + gate recheck, no external call for disabled/zero findings/zero results as applicable. Apply uses a shared original save-review helper inside one transaction.
- [ ] Run provider/API tests and complete server regression; local scoped commit. Review integration diff.

### Task 4: Frontend controls + recovery

Files: create frontend/src/features/ai/{AiCallDetails,RecommendationAi,ContractAi}.tsx, frontend/src/api/ai.ts; wire Recommendations.tsx/Contract.tsx; update factual AI copy in shell/upload; additive styles. Avoid moving unrelated workflows.

- [ ] Write browser tests for explicit unchecked consent, no-key failure preserving rules, structured test_stub results/citations, user confirmation applying candidates, stale analysis disabled and refresh recovery.
- [ ] Add typed endpoints/envelopes and 45-second AI fetch budget; disable duplicate submissions and scope state to run/review, reset consent on context change. Retry captures original request, new generation gets new ID.
- [ ] Show model source, calls, actual duration/status and optional usage; invalid candidates marked pending, apply only selected valid fields. Original report remains visible after AI failure.
- [ ] Run build, existing browser journeys, new AI journeys and production preview. Inspect desktop/mobile screenshots.

### Task 5: Final verification + teammate handoff

Files: docs/frontend/2026-10-20-ai-verification.md, docs/frontend/agent3-ai-handoff.md; root docs/frontend pointer to local plan/run guide. `.runtime/ai-qa/` ignored for test artifacts.

- [ ] Run current Agent 1/2/3/4, integration and server suites; build and browser tests. Save actual counts and logs.
- [ ] Review complete local diff and fix important issues with covering tests; no duplicate full-suite rerun without changes.
- [ ] Document backend .env sample, enable/restart steps, no-config behavior, real-provider test pending if key absent, and Agent 3 source/modified files/compatibility checklist.
- [ ] Keep local commits on codex/local-ai-integration, verify no new remote branch/push/Jira mutation, leave local app running, open Markdown guide and report final results to user.
