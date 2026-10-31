# RAG business integration handoff — 2026-10-30

## Delivered

- English public knowledge: 80 annotated questions compare keyword, hybrid and reranked retrieval, with per-claim exact-source checks, conditional source preservation, explicit fallbacks and review sheets.
- Private uploaded contracts: Contract-page search panel, independent local/cloud consent, case/review/file/version binding, page/clause provenance, protected original-document preview, revocation and derived-history cleanup. Normal chat can use the current independently authorized contract.
- Listing lifestyle preferences: explicit English/Chinese preferences reorder the entire hard-matching set using attributable current suburb/ad evidence. Per-card reasons distinguish advertisement claims from suburb context; missing evidence stays unknown. Changing/clearing preferences persists without relaxing budget/room/commute constraints.

## Evidence and limits

The complete real 80-case run achieved 72/72 annotated passage recall at rank 6 after reranking, compared with 70/72 keyword and 71/72 hybrid. Automated answer checks passed 70/80; eight valid model abstentions and no exact citation-membership failures were observed. Six rerank timeouts used the fused fallback. That is not an 80/80 answer-quality result. The audit found quote-id failures, language-scoring mismatches and real heading/exception handling defects; the latter received source-preserving fixes and a separate targeted rerun. Independent human legal/entailment review remains pending.

A synthetic two-page PDF was indexed through the actual official embedding/rerank services and answered by the existing chat model. It returned a page-2 cleaning citation preserving its exception. Revocation removed its derived index and blocked old source access. No existing user's private contract was used for real provider verification.

See the focused handoffs:

- `2026-10-30-rag-quality.md` and `2026-10-30-rag-quality-external.json`
- `2026-10-30-contract-rag.md`
- `2026-10-30-soft-preferences.md`

## Verification record

The final verification record below is updated after integration tests and the local reload. Automated tests use isolated cases and synthetic documents; the live business database is backed up and compared before/after reload.


- Backend integration/regression suite: **159 tests passed** (91.83 seconds), covering public/private RAG, evaluation, soft preference integration, assistant API and lease drafts/forms. Final frozen guard/passage suite: **34 tests passed**.
- Browser suite: **11 tests passed** across contract consent/citations/revocation, stale in-flight replies, public RAG, parallel selection/favorites, soft preference rendering and full rental journey.
- Frontend production build: passed. Existing bundle-size advisory remains.
- Targeted provider rerun: nine cases passed mechanical checks; after final source grouping was frozen, 019/020/023 passed again and their complete exception/action quotations were inspected. Reports remain distinct from the complete 80-case baseline.
- Local app reloaded at `http://127.0.0.1:5191`; API health and frontend returned 200. Seven private RAG routes including protected original preview are loaded; public status reports all 49 contextual 1024-dimensional vectors, embedding/rerank/generation configured.
- Live business data: **484 rows**, identical sorted kind/id/body SHA-256 before and after reload: `5d963de583ba81c6f3cdbd148b0836ef707c7789f103257882726951e7398917`. A SQLite backup was taken before reload. No business records were rewritten by this integration.


## Continued answer verification

The continuation fixes citation-pair constraints, duplicate resolved claims, missing abstention details, formatting-aware numeric validation and complete captured procedure groups. See `2026-10-30-rag-answer-hardening.md` for reproduced causes and verification.

The unchanged full 80-question set was run again in `2026-10-30-rag-quality-verified-80.json`: **76/80** strict automatic answer checks, comprising **76/76 English** and **0/4 Chinese**. All four remaining failures requested Chinese but conservatively received English source clauses; they remain failures and are separately reported as requested-language mismatches. The audit confirms missing facts are retained for all eight valid model abstentions, with no exact duplicate accepted claims. Annotated passage recall remains **72/72** at rank 6; no retrieval degradation, citation-membership failure or provider failure was observed. The run took 274.78 seconds. These are measured automatic results, not a human entailment score.

After that run imported its modules, the final conservative qualifier addition (“usually/most” and related language) was verified separately; its regression protects the exact deadline trigger. The full reports are retained with their actual measured code stages rather than relabeled as a later run. Final frozen-code regression covers **185 passing tests**. Existing browser contract/full-journey checks passed; the three public RAG browser tests, including the new missing-facts case, passed. Final local UI/API health is 200 and all 484 business records retain their pre-reload digest.
