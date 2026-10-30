# NSW RAG quality evaluation

The benchmark contains 80 annotated synthetic questions: 76 English and 4 Chinese; 72 have target passages in the five captured NSW public guides and 8 require abstention or clarification. It replaces the former document-presence smoke test. It does not certify legal correctness.

The supported questions cover repair classification, reimbursement prerequisites, bond conditions and payment stages, valid notice contents and service, calendar versus working days, break-fee tiers and exceptions, dispute channels and application triggers. The remaining questions exercise unavailable private contracts, another tenant's data, an unseen notice's validity, missing notice facts, Victoria, future law, a property's quietness/pet approval and an instruction to invent a bond guarantee. All private examples are synthetic questions. No actual private contract or case data is read or sent.

Each supported target names an exact document and section plus literal passage cues that must exist in that section. Gold conditions, required-claim regexes, forbidden-conclusion regexes and a manual review checklist accompany every case. These are review annotations derived from the captured source snapshot, not an independently lawyer-adjudicated gold standard. The benchmark is deliberately small and corpus-specific; it cannot measure general tenancy advice competence.

## Reproduce

From the repository worktree:

```sh
.venv/bin/python -m unittest server.tests.test_rag_evaluation server.tests.test_rag -v
.venv/bin/python scripts/rag_evaluate.py --as-of 2026-10-30
```

The offline command creates a temporary keyword index from `data/knowledge/en/documents.json`, makes zero network calls and explicitly marks both cloud modes skipped. It writes `docs/frontend/2026-10-30-rag-quality-offline.json` and `.review.json`. It does not alter the live runtime.

For an actual three-mode comparison with the already published public vectors:

```sh
.venv/bin/python scripts/rag_evaluate.py --external --as-of 2026-10-30 \
  --output docs/frontend/2026-10-30-rag-quality-external-retrieval.json
```

For generation as well:

```sh
.venv/bin/python scripts/rag_evaluate.py --external --generate --as-of 2026-10-30 \
  --output docs/frontend/2026-10-30-rag-quality-external.json
```

Use `--limit 3` or `--ids nsw-001 nsw-073` for a small smoke run. Generation defaults to the hybrid plus rerank results only, for at most 80 chat attempts. Repeat `--generation-mode keyword --generation-mode hybrid --generation-mode hybrid_rerank` only when a generation comparison across all three modes is intended; that can make 240 chat attempts. `--generate` requires `--external`. `--runtime DIR` selects the read-only public `rag.sqlite3`; default is `.runtime`. `--cases` and `--corpus` allow a versioned alternative corpus and annotations. The copied persisted index must match the supplied corpus version.

Cloud runs read the allowed local configuration through `scripts.local_ai_env.load_ai_env`; they never print keys or endpoint URLs. They use a consistent SQLite backup of the existing index in a temporary directory. No publication, embedding of new corpus documents, runtime writes, app restart or case mutation occurs. The default 80-case external run makes 8 query-embedding batch requests (10 unique questions each), at most 80 rerank requests and, only with `--generate`, at most 80 chat attempts. A maximum of 2 workers applies to each stage. Query vectors are reused across both hybrid modes. The embedding batch deadline is 30 seconds; the existing adapters bound rerank and chat deadlines. Actual call counts and timings are reported; absent results, unavailable configuration, incomplete compatible vector coverage and upstream failures stay visible.

A normal exit 0 means the report was written. Add `--strict` to exit 1 when a supported passage is missed at rank 6, generated output fails mechanical checks, or a requested external mode is skipped/degraded. This is an automation gate, not a human claim-support verdict. The checked-in offline run correctly fails a strict all-targets gate.

## Scoring and review

- `keyword` uses the existing keyword search and freshness policy.
- `hybrid` uses keyword search plus cosine retrieval and reciprocal-rank fusion, without reranking.
- `hybrid_rerank` reranks the same fused candidates using the configured provider. A rerank failure retains the fused order and labels the case degraded.
- All modes use the same corpus/index version and `--as-of` date. Sources checked more than 90 days earlier, or future-dated, are excluded. Freshness filtering is a product policy, not verification that the law has remained unchanged.
- Recall at 1/3/6 and reciprocal rank require the annotated section and literal cues. Unsupported cases are excluded from these denominators. Retrieving related guidance for an unsupported question is recorded, not counted as a successful answer.
- With generation, the evaluator supplies precomputed evidence through the production `KnowledgeService.answer` path, preserving its JSON schema, quote-id resolution and unsupported-number rejection. It does not rerun retrieval or spend duplicate embedding/rerank calls.
- Citation checking requires each claim and returned citation to reference retrieved evidence with a literal source substring. It proves source membership. It does not prove that a claim follows from the quotation.
- Required and forbidden regexes operate on accepted claim text, not on the quotations. They can miss semantic errors and produce false alarms for alternate wording, negation and translations. Conditions must still be assessed manually.
- The report separately records the raw, unvalidated model response for review, valid empty-claim model abstentions and provider errors. When the backend falls back after a timeout or rejected claim, that does not count as successful model abstention. Raw responses must be reviewed as untrusted text. They are never treated as accepted answers.

Every report has index/model identity, dataset fingerprint, stage wall times, per-case retrieval timings, degradation flags, failed case ids and the exact retrieved text. The adjacent review sheet includes the question, gold conditions, retrieved evidence, accepted answer, raw model observation and empty reviewer fields. Copy the sheet before annotating: rerunning the same output path overwrites it. Review each claim against its own quote, whether all material qualifications survive, whether the answer addresses the question and whether an abstention/clarification is appropriate. Populate `human_supported`, `human_conditions_preserved`, `human_abstention_appropriate`, reviewer, date and notes. `human_review_completed` and `human_support_pass_rate` remain false/null in automated output.

## Verified offline result

On the 2026-10-30 captured 49-chunk corpus, the full offline run evaluated 80 cases, including 72 supported targets:

| Metric | Keyword result |
| --- | ---: |
| Target passage at rank 1 | 55/72 (76.39%) |
| Target passage at rank 3 | 65/72 (90.28%) |
| Target passage at rank 6 | 70/72 (97.22%) |
| Mean reciprocal rank | 0.8435 |
| Generated answers | 0 |
| Completed human support reviews | 0 |

The two passage misses are `nsw-044` (Chinese notice-day counting) and `nsw-072` (Chinese Tribunal extension question). Both remain failures. The offline result provides no evidence about cloud quality; the measured external run is recorded below. 34 relevant unit tests passed, including the evaluator's 19 tests, original public RAG tests, production quotation rejection, graceful cloud failure and immutable-index checks.

The follow-up production fix retains the full heading path, including the before/after 23 March 2020 regime. All 49 contextual embedding inputs were rebuilt. Source captures still include some images and long table paragraphs; literal recall and quote availability should be inspected alongside source support.


## Measured external run and review (2026-10-30)

The second complete real run is `2026-10-30-rag-quality-external.json`, with its companion review sheet. It uses all 80 questions and the 49 contextual chunks in index `8b8a06a6d50ed9eff5818524eace8f2453adcf75bc6eb5e90c7418072f0657bf`.

| Metric | Keyword | Hybrid | Hybrid + rerank |
| --- | ---: | ---: | ---: |
| Annotated passage recall at 6 | 70/72 | 71/72 | 72/72 |
| Automated answer checks | — | — | 70/80 |
| Observed valid model abstentions | — | — | 8 |
| Exact citation membership failures | — | — | 0 |

Six rerank requests timed out; those cases retained fused order and are marked degraded. Retrieval median was approximately 3.4 seconds and p95 10.28 seconds. The complete evaluation took approximately 417 seconds. These timings are observations, not service guarantees.

The audit `2026-10-30-rag-quality-external-context-v2-audit.json` classifies the ten failed checks. Three are safe fallbacks after invalid quote identifiers or a duration assigned to the wrong paragraph; four are Chinese-only scoring expressions conflicting with conservatively preserved English source wording; three revealed an overly strict numeric guard on facts in trusted heading context. The gold questions/regexes were not relaxed. The audit also found adjacent-exception and non-colon list lead-in gaps that mechanical citation membership did not catch.

Production safeguards preserve original conditional/table passages with full heading context, reject mismatched numeric units and date regimes, and retain adjacent exception/list groups. A targeted post-fix rerun is recorded separately rather than presented as a new 80-case pass rate. Automated recall or citation membership is not a legal entailment score; a completed independent human review remains outstanding.


## Targeted fix verification

`2026-10-30-rag-quality-followup.json` reran nine previously problematic English cases against real embedding/rerank/generation: 9/9 automated checks passed, 0 degraded requests and 0 exact-citation failures. This process imported the passage module before its last download-link bridge fix, so it is not evidence that adjacent exceptions were preserved.

After the passage implementation was frozen, `2026-10-30-rag-quality-followup-final.json` reran 019/020/023: 3/3 automated checks passed with 0 degraded requests. Direct inspection confirmed that 019 keeps “should” with both principal-tenant actions, 020's 14-day repayment quotation includes both the debt and final-apprehended-violence-order exceptions, and 023 preserves the early-claim alternatives. All quotations remain exact source substrings. The original 80-case report is retained unchanged; these subsets do not establish a revised 80/80 pass rate.


## Continued answer verification

The continuation fixes citation-pair constraints, duplicate resolved claims, missing abstention details, formatting-aware numeric validation and complete captured procedure groups. See `2026-10-30-rag-answer-hardening.md` for reproduced causes and verification.

The unchanged full 80-question set was run again in `2026-10-30-rag-quality-verified-80.json`: **76/80** strict automatic answer checks, comprising **76/76 English** and **0/4 Chinese**. All four remaining failures requested Chinese but conservatively received English source clauses; they remain failures and are separately reported as requested-language mismatches. The audit confirms missing facts are retained for all eight valid model abstentions, with no exact duplicate accepted claims. Annotated passage recall remains **72/72** at rank 6; no retrieval degradation, citation-membership failure or provider failure was observed. The run took 274.78 seconds. These are measured automatic results, not a human entailment score.

After that run imported its modules, the final conservative qualifier addition (“usually/most” and related language) was verified separately; its regression protects the exact deadline trigger. The full reports are retained with their actual measured code stages rather than relabeled as a later run. Final frozen-code regression covers **185 passing tests**. Existing browser contract/full-journey checks passed; the three public RAG browser tests, including the new missing-facts case, passed. Final local UI/API health is 200 and all 484 business records retain their pre-reload digest.


Final qualifier real-call check (`2026-10-30-rag-quality-qualifier-final.json`): 1/1 automated check passed, no degraded request or citation/provider failure. Any returned 28-day passage retains the original entitlement trigger; the regression separately forces the formerly over-broad paraphrase. This targeted call supplements the preceding full report.
