# Public RAG first-summary timeout

The first chat reply could show Sources only until the user selected Summarise again. Both entry points already called the same KnowledgeService.answer pipeline; summary generation was not missing from the first request.

## Reproduced cause

Using the effective live model settings and fresh temporary databases, the public question `What should I check before signing a rental agreement in NSW?` reproduced sources_only / summary_review_failed. The initial answer completed in 9.074 seconds and all three isolated source summaries completed in about 4.5-5.4 seconds. The independent source check then hit its hard 8-second limit and raised ai_timeout after 8.005 seconds. Atomic fallback correctly withheld the unreviewed prose but left the user with sources and a manual retry button.

The other reported public question, `What should I know about rental bonds in NSW?`, completed its check in 7.675 seconds on the before run, showing why the outcome could vary near the cap. No private contracts, contacts or existing user messages were sent for reproduction.

## Change

The independent check now uses `min(15, deadline - monotonic())` rather than `min(8, ...)`. It can use available generation time while remaining bounded by the original deadline. The existing 36-second generation-stage budget starts after retrieval; this change does not move that start, change retrieval timeouts or extend the frontend timeout. No automatic retry or additional AI call was introduced.

Source identifiers, per-source schemas, independent support review, English/numeric/condition checks, atomic failure and private-content exclusions are unchanged. Failures still preserve sources instead of publishing unchecked text. Historical stored replies and receipts are not rewritten; retry remains available for those messages.

## Verification

- Added a regression simulating a check that needs more than eight seconds: failed before and passed after the fix.
- Added a remaining-budget regression: only 2.5 seconds left still means a 2.5-second review timeout.
- 74 related backend tests passed, including citation integrity, unsupported claims, language, private/public boundaries and main-chat knowledge behavior.
- 9 isolated browser scenarios passed, including first-answer display, collapsed evidence, historical retry without receipt rewrites, local-only search and housing-intake continuity.
- Both reported questions returned answered on their first post-fix request. The first check took 8.502 seconds and the second 7.467 seconds; total answer times were 25.450 and 23.072 seconds. These are individual observations, not an availability or latency guarantee.
- [Sanitised before/after metadata](2026-11-01-rag-first-summary-real.json) contains task timing and outcomes, without keys, private records or model response text.

Only `server/app/rag/public_summary.py` and its regression tests changed in application code. No knowledge corpus refresh is needed.

Local services were reloaded with their effective environment, preserving Jev active mode. All five SQLite database logical fingerprints were unchanged across restart. Existing failed historical replies remain saved; a new question uses the updated review budget.
