# Product guide integration review — 2026-10-30 Sydney

## Two conclusions

**Scope compliance: passes the reviewed requirements and regression probes.** The authored English guide covers the approved implemented workflows and correctly separates optional favorites/comparison from direct selection, inspection preparation from booking, unsigned drafts from signatures, repair drafting from sending, provider records from external bookings, and product help from tenancy rules. It accurately describes the separate contract-processing/local-search/cloud/per-question consent controls. Public and private evidence stores remain separate. All original and expanded failing probes now pass, including the polite comparison action, the seven lifecycle-help topics and Chinese local-only HTTP search. All three findings are closed after the final read-only recheck below.

**Code quality: passes this integration review; no outstanding material finding.** The fixed authored-file path, strict complete-record equality, SHA-256 body version, escaped-only renderer, restrictive CSP and versioned citation endpoint are clear and tested. Keyword/vector scope filters operate before result limits. No private-data publication, executable HTML, arbitrary file path or fake-host product source issue was found in this read-only review. Scope/query regression coverage now includes the reported action and multilingual retrieval failures. This conclusion is bounded by the offline/source review and tests described below; it is not a guarantee about every natural-language phrasing or live external-provider behavior.

## Initial material findings (historical; see current follow-up below)

### P1 — An incidental explanatory word overrides an explicit action

Locations: `server/app/rag/scope.py:6` and `:17–18`; `server/app/assistant/service.py:149–181`.

`is_product_question()` requires only an explanatory token anywhere and a product token anywhere. It does not require the message to be a read-only explanation or exclude imperative clauses. Reproduction:

```text
is_product_question('I know how favorites work. Select the first house.') == True
```

This is an explicit selection request with background context, but `AssistantService.send()` replaces its normal transition with `{'intent': 'knowledge'}`. `DecisionRouter.prepare()` accepts that as `direct_intent`, and the subsequent repair route is also skipped for product questions. The selection request therefore becomes product help instead of reaching the normal selection/confirmation behavior. This directly conflicts with the requested action-versus-help boundary.

Recommendation: recognize a clearly explanatory product request, and let explicit action clauses retain normal routing or use the existing mixed-task clarification path. Cover an incidental “how” sentence followed by selection, a polite action request, mixed help-plus-action requests, and an active/pending action context. Do not fix this by weakening confirmation gates.

### P2 — Several guide topics are routed out of the product evidence scope

Locations: `server/app/rag/scope.py:7–22`; `server/app/rag/service.py:66–69`.

The guide documents cases, requirements, upload, consent, utilities, moving, cleaning and aftercare, but `_PRODUCT` only enumerates a small subset of those controls. The following direct product-help questions all return `False`:

```text
How do I start a new case?
How do I upload a contract?
How do I revoke cloud consent?
How do I edit my rental requirements?
```

`retrieval_source_types()` consequently selects only official/student reference types. In the public RAG API, the relevant authored guide is excluded even though it contains the answer; the user receives unrelated tenancy material or no evidence. Native chat also loses the deterministic help route and may reach a contract/action branch instead. This is not a missing documentation issue: the necessary text already exists.

Recommendation: expand explanatory recognition to implemented guide controls in both UI languages, with precise product-operation phrases and legal/private-contract counterexamples. Keep clause/legal interpretation questions on their established reference/private route. Integration tests should cover representative questions from every guide section rather than only favorites and lease generation.

### P2 — Recognized Chinese product questions have no local retrieval tokens

Locations: `server/app/rag/index.py:14,20–22`; `server/app/rag/scope.py:14–18`; `server/app/rag/service.py:66–83`.

The recognizer explicitly accepts Chinese product-help questions, but `terms()` extracts only `[a-z0-9]+`, while its existing Chinese-to-English bridge covers tenancy terms and has no product-control mappings. Reproduction in an isolated index containing only `product_document()`:

```text
question: 怎么使用我的租房需求？
product scope: True
local keyword hits: 0

question: 收藏和选定并跟进有什么区别？
product scope: True
local keyword hits: 0
```

Without optional cloud embeddings, or when semantic retrieval is unavailable, these supported questions cannot retrieve the English-first guide even though it contains the exact Chinese control labels. The existing scope unit test only asserts the boolean classification and misses this failure.

Recommendation: add a deterministic product query bridge/normalization tied to the guide's public controls, or another local multilingual retrieval path. Verify complete local `rag/search` results and source classification with `allow_external_ai=False`; retain the independent cloud consent boundary.

## Capability and boundary checks

The brief/report and complete `product-guide.md` were read. Public source code was checked for case/conversation navigation and guide labels, real-listing filtering, the inspection checklist and contract navigation, commute reference/direction links, lease AI/confirmation controls, upload limits/consent, private contract search, repair composer and provider/aftercare controls. No unsupported automatic booking, automatic email sending, automatic signature, agent-reply form or legal-validity guarantee is claimed by the guide.

`product_document()` reads only the fixed repository Markdown file and returns explicit reviewed-release metadata. `validate_product_document()` compares the complete record with that local canonical record, so changing the body and recomputing its hash, adding a case ID/private text/path, or supplying another host cannot impersonate the guide. `KnowledgeIndex.prepare()` calls that validation before deriving chunk metadata. The renderer validates again and escapes heading/list/paragraph content; Markdown links and raw tags remain text and cannot request external resources.

`KnowledgeService.user_guide()` is deliberately public and accepts only an optional version string. Wrong versions return 409. Product chunk citations derive `/api/v1/rag/product-guide?version=<document hash>`, avoiding silent substitution of a newer guide for a cited version. Response headers set no-cache, nosniff and a CSP that excludes scripts/external assets, frames and base URLs.

Public retrieval passes a fixed reference/product type filter to both keyword and vector search before limits. Private contract answering explicitly requests reference types, keeping product instructions out of clause/law evidence. Private contract `_owned`, binding/version/grant checks and separate storage remain in `contracts.py`; product help does not call private clause retrieval. No real cases, uploads, private runtime files, credentials or external AI/network endpoints were read during this review.

## Verification performed

```text
.venv/bin/python -m unittest server.tests.test_product_guide server.tests.test_rag_expansion -v
Ran 14 tests — OK
```

Additional offline reproduction used `TemporaryDirectory`, a fresh `KnowledgeIndex`, `product_document()`, `is_product_question()` and `retrieval_source_types()`. It confirmed all three findings above. It also confirmed the positive English control `How do I compare properties?` enters product scope and returns guide results, isolating the Chinese failure from corpus absence.

The 14 passing tests verify trusted document fidelity, malicious authored HTML escaping, forged/private document rejection, source-type filters, public HTML version binding, one native read-only help request and two retrieval scopes. They do not currently cover the failing action/background sentence, the omitted help-topic families or actual local Chinese retrieval.

This review changed only `docs/superpowers/plans/rag-expansion-2026-10-30/product-integration-review.md`. It did not edit shared source, rebuild/publish an index, restart services, commit/reset files or inspect real private data. No live browser or configured external-provider validation is claimed.

## First follow-up after scope/query changes (historical; final resolution below)

Read-only recheck of updated `scope.py`, `service.py`, `evaluation.py` and expansion tests confirms these original probes are fixed:

| Probe | Current result |
| --- | --- |
| `I know how favorites work. Select the first house.` | Product false; normal action routing retained |
| `How do favorites work? Then select the first house.` | Product false |
| `我知道怎么收藏了，请选定第一套。` | Product false |
| `How do I start a new case?` | Product true; first guide section Start a case and chat |
| `How do I upload a contract?` | Product true; first guide section Upload a contract for review |
| `How do I revoke cloud consent?` | Product true; first guide section Private contract search and separate consent |
| `How do I edit my rental requirements?` | Product true; first guide section Edit rental requirements and see all matches |
| `怎么使用我的租房需求？` | Product true; correct first guide section; HTTP local search returns 6 product excerpts |
| `收藏和选定并跟进有什么区别？` | Product true; correct first guide section; HTTP local search returns 6 product excerpts |
| `How do I start a new case at NCAT?` | Product false; legal scope retained |
| `How much notice must my landlord give before entry?` | Product false; legal scope retained |

The two Chinese queries were exercised through `/api/v1/cases/{synthetic_id}/rag/search` with `allow_external_ai=False`, a fresh temporary case, an isolated guide-only index and an injected offline provider. Both returned HTTP 200, `scope=product`, only `product_guide` excerpts, and no external AI calls. `service.py` and `evaluation.py` both call the same `retrieval_query()` normalization for keyword retrieval. **Original finding 3 is closed.**

**Residual P1 action boundary:** `Can you compare my favorites and explain how they differ?` still returns product true. The new `_ACTION` matches imperatives at a clause start but does not recognize this common polite `Can you compare ...` action. The later “how” supplies the explanatory token, so the assistant still forces knowledge and skips the existing compare behavior. Original finding 1 is fixed for its original imperative probe but remains open for this polite action form. Add this full sentence to the action-boundary regression set, preserving actual explanatory questions such as `How do I compare properties?`.

**Residual P2 help-topic coverage:** all seven following product-operation questions return product false and therefore exclude the guide:

- `How do I select electricity providers?`
- `How do I record a moving booking?`
- `How do I prepare inspection questions?`
- `How do I start bond follow-up?`
- `How do I create a move-out plan?`
- `How do I update repair follow-up records?`
- `How do I use lifestyle preferences?`

New-case/upload/requirements/cloud-consent coverage is fixed, but `_PRODUCT` still omits these other documented controls. Original finding 2 remains partially open. Prefer clearly product-specific operation phrases and retain legal counterexamples, rather than recognizing all occurrences of “bond”, “repair” or “inspection” as product help.

Current command `.venv/bin/python -m unittest server.tests.test_product_guide server.tests.test_rag_expansion -v` passes **16 tests**. Expanded direct/local-index probes and the two isolated Chinese HTTP probes were also completed without external calls or real/private data reads. Only this report was edited during the follow-up; no shared source or test files were changed.

## Final recheck and finding closure

The revised English explanation pattern now requires an explanatory request at the start of the message (including explicit “explain/tell me/show me” requests), so the incidental “how” in `Can you compare my favorites and explain how they differ?` no longer forces product help. This action, the original background-sentence/selection example, English mixed help/action example and Chinese explicit selection example all return product false. The positive control `How do I compare properties?` remains product true and retrieves the favorites/comparison section. **Finding 1 is closed.**

All seven lifecycle questions listed in the first follow-up now return product true and retrieve the guide. Electricity providers and moving booking retrieve Utilities, moving and cleaning providers; inspection questions retrieve Confirm selection and prepare an inspection; move-out planning retrieves Move-out plans and bond follow-up; repair follow-up retrieves Repair emails and follow-up records; lifestyle preferences retrieve Lifestyle preferences and sources. Bond follow-up enters product scope and its relevant Move-out plans and bond follow-up section is present among the six returned excerpts. The original new-case/upload/requirements/cloud-consent fixes remain intact. **Finding 2 is closed.**

`ProductScopeTests.test_product_and_legal_search_do_not_cross_scopes` now contains both Chinese examples through the HTTP endpoint with `allow_external_ai=False`; it verifies nonempty product-only evidence and zero provider inputs. Shared `retrieval_query()` use in service/evaluation remains intact. The prior independent HTTP recheck and current test rerun confirm the local multilingual fix. **Finding 3 remains closed.**

The final boundary probes keep NCAT new-case procedure, landlord entry notice, lease enforceability and repair responsibility outside forced product help. The scope changes do not alter the fixed guide source, private-contract access controls, escaped HTML renderer or citation version binding.

Final verification: `.venv/bin/python -m unittest server.tests.test_product_guide server.tests.test_rag_expansion -v` — **16 tests passed**. Additional isolated guide-index probes verified ten explanatory English/Chinese help questions return product evidence and eight action/legal controls do not force product help. No external calls, real case/private-file reads or shared source/test edits occurred. Only this review report changed during the final recheck.
