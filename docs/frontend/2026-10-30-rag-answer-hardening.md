# RAG answer follow-up: citation stability and transparent abstention

The user requested continuation after the three RAG business increments. This follow-up addresses observed answer-contract defects without changing the original 80 questions or their strict answer patterns.

## Reproduced causes

1. The model-facing schema accepted any evidence/quote strings, although the resolver later rejected nonexistent pairs. Previous real failures included a quote index from another source or an invented paragraph number. Each request now supplies a schema limiting exact evidence/quote pairs, plus instructions to copy those pairs and combine claims from the same passage. The resolver still validates every claim atomically; an invalid claim causes source-only fallback. There is no hidden repair retry or another private-data cloud call.
2. Empty model claims were raised as an error, discarding valid `unknowns` and presenting an outage warning. Intentional abstention now returns `insufficient_evidence`, the missing facts and successful call metadata, with separately identified `generation_outcome=model_abstained`. Relevant source excerpts remain inspectable.
3. Source preservation could turn several model paraphrases into identical quoted claims. Exact resolved duplicates are removed after all claims pass validation, keeping citation numbering consecutive. Distinct supported claim texts remain intact.
4. Four Chinese benchmark questions requested Chinese wording while the conservative guard retained English original clauses to preserve qualifications. Such answers now explicitly report actual source language and carry an English-original notice. Evaluation separately records requested-language mismatch and outcome categories; its original Chinese checks still fail. No translation is presented as verified, and the gold is unchanged.

## Outcome diagnostics

`generation_outcome` distinguishes `no_evidence`, `local_only`, `no_complete_passages`, `answered`, `model_abstained`, `invalid_response`, `invalid_citation`, `unsupported_claim` and `provider_error`. These are bounded server-generated diagnostics, not model text. Raw unaccepted model responses remain limited to the evaluation review output and are not published as accepted answers.

## Verification

The six new answer-integrity tests first reproduced the missing scope restriction, discarded unknowns, duplicate quotes, absent language notice and an unnecessary call when no complete quote is available. A further evaluation regression ensures English source preservation never silently passes Chinese required patterns. Browser coverage checks that missing rent-ledger/payment facts reach the user without an AI-outage warning. Verification uses only isolated fixtures and public/synthetic questions.

Final measured results and reload checks are appended after verification. The prior complete 80-case report remains unchanged; a new full run is saved under `2026-10-30-rag-quality-final-80.json`.


- Backend: **181 tests passed** in 119.70 seconds, including the six new integrity tests, evaluation regression, private contract authorization/revocation, rental assistant, lease generation and model transport.
- Browser: existing contract consent/revocation tests (2), full rental journey (1) and public RAG tests (2) passed. The new abstention test initially asserted that no limitation section could exist, but the isolated fixture correctly warns that embedding/reranking are unconfigured. The assertion was narrowed to the actual bug: no spurious generation/citation-failure warning. All three public RAG browser tests then passed in 9.3 seconds; the missing ledger/payment facts are visible.
- Existing 80-case gold is unchanged (SHA-256 `895fafb00a1795d576d82f987e49642a783412e790384d41c34b2c3e6ba3e148`).
- Local service reloaded at `http://127.0.0.1:5191`. UI/API returned 200; a local-only source query returned the new `generation_outcome=local_only` field without a cloud call. All **484** live business rows matched the pre-reload SHA-256 `5d963de583ba81c6f3cdbd148b0836ef707c7789f103257882726951e7398917`. A fresh SQLite backup was saved before reload.


## First complete follow-up run and further fixes

`2026-10-30-rag-quality-final-80.json` completed all 80 cases with the unchanged gold: annotated passage recall was **72/72**, automated answer checks **74/80**, 8 valid model abstentions, zero exact-citation failures, zero provider failures and zero degraded retrieval requests. Total wall time was 278.11 seconds. The server classified 70 answered results, 2 source-only rejections and 8 intentional abstentions. Four of the answered results are English source preservation for Chinese requests and remain strict answer-check failures.

The other two failures were inspected claim by claim:

- `nsw-024`: a valid duration from an adjacent procedural step was attached to the notification paragraph. The guard correctly rejected it. Captured accordion subsections now remain complete quotation groups, keeping each procedure's steps, pronouns, deadlines and exceptions together, within the existing 3200-character bound. Different accordion topics stay separate; oversized procedures are omitted as a whole.
- `nsw-031`: the real source contains `_Residential Tenancies Act 2010_(the Act)`. The closing Markdown underscore caused the numeric tokenizer to miss the supported year. Visible-text normalization now removes formatting delimiters while retaining intra-word underscores and stripping URL numbers as before. Unsupported years/units still reject.

The three new regressions reproduced those cases before fixes. Correctly resolved source replay accepted the six recorded claims after the fixes; see `2026-10-30-rag-answer-replay.json`. Replay is not a substitute for new model output. A second final full run is saved separately as `2026-10-30-rag-quality-verified-80.json`.

A read-through of the first run's unpreserved paraphrases identified `nsw-064`: a general Tribunal time-limit summary must retain the exact entitlement-trigger qualification, rather than assume every clock starts at the first event. The final guard now preserves original text when a source/claim uses “usually”, “generally”, “normally”, “typically” or “most”. Its failing regression reproduced the omission and now verifies the exact trigger remains. The in-flight 80-case run imported the guard before this final addition; a separate targeted check verifies the frozen final guard. Nothing is marked human-approved.


Final frozen-code backend regression: **185 tests passed** in 107.95 seconds. Public/private RAG, evaluation, model transport, soft preference ordering, assistant and lease workflows are covered. The final reload returned HTTP 200 for UI/API; a local-only source query made no cloud request, and all 484 business rows matched the same pre-reload digest. The latest source version still has 49 contextual public vectors; source text/embeddings did not need rebuilding for quotation grouping or visible-number fixes.


## Continued answer verification

The continuation fixes citation-pair constraints, duplicate resolved claims, missing abstention details, formatting-aware numeric validation and complete captured procedure groups. See `2026-10-30-rag-answer-hardening.md` for reproduced causes and verification.

The unchanged full 80-question set was run again in `2026-10-30-rag-quality-verified-80.json`: **76/80** strict automatic answer checks, comprising **76/76 English** and **0/4 Chinese**. All four remaining failures requested Chinese but conservatively received English source clauses; they remain failures and are separately reported as requested-language mismatches. The audit confirms missing facts are retained for all eight valid model abstentions, with no exact duplicate accepted claims. Annotated passage recall remains **72/72** at rank 6; no retrieval degradation, citation-membership failure or provider failure was observed. The run took 274.78 seconds. These are measured automatic results, not a human entailment score.

After that run imported its modules, the final conservative qualifier addition (“usually/most” and related language) was verified separately; its regression protects the exact deadline trigger. The full reports are retained with their actual measured code stages rather than relabeled as a later run. Final frozen-code regression covers **185 passing tests**. Existing browser contract/full-journey checks passed; the three public RAG browser tests, including the new missing-facts case, passed. Final local UI/API health is 200 and all 484 business records retain their pre-reload digest.


Final qualifier real-call check (`2026-10-30-rag-quality-qualifier-final.json`): 1/1 automated check passed, no degraded request or citation/provider failure. Any returned 28-day passage retains the original entitlement trigger; the regression separately forces the formerly over-broad paraphrase. This targeted call supplements the preceding full report.
