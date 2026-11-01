# English product release — 30 October 2026

The rental assistant now uses English for all newly authored product content.
This includes navigation, forms, accessibility labels, status descriptions,
validation errors, chat suggestions, generated follow-up questions, recommendation
explanations, repair emails, contract review guidance and retrieval summaries.
English is the product default; there is no Chinese output-language control.

Original user messages, names, addresses, document text, source quotations and
saved business records retain their original values. Multilingual input remains
supported for compatibility. Historical developer notes and example source
documents are not rewritten as if they were new English product content.

## Routing and retrieval

1. The shared chat receives the message, consent and current task context.
2. Active Jev classifies the request. Existing continuation, validation and
   fallback rules still determine whether that classification can be used.
3. Alibaba extracts supported facts and generates the response for the selected
   housing, contract, aftercare or knowledge workflow. Shared generation policy
   fixes authored output to English while preserving source facts and names.
4. Public retrieval and private contract retrieval keep their existing scopes,
   consent, version checks and citations. Generated summaries and follow-up
   information must be English; unsupported or untranslated model output falls
   back to an English source-only explanation. Exact original excerpts remain
   available beside the explanation.
5. Repair drafts appear in chat, can be rewritten and copied there, and are saved
   only after the existing confirmation. No email is sent automatically.

The conversion does not change the meaning of identifiers, schema fields,
classification routes, recommendation calculations or business statuses.

## Frontend and public catalogue changes

The browser document language is `en`. Ant Design uses its English locale, with
Australian dates and currency presentation. English copy covers desktop/mobile
navigation, housing cards, contract upload/review, aftercare, human review,
progress, preferences, utility providers and public help.

Public catalogue translations preserve prices, numbers, dates, identifiers, URLs
and original source metadata. Existing listing and campus fingerprints remain
stable when only a displayed label changes; changing a substantive listing fact
still changes its fingerprint. All 1,000 commute annotations retain their
catalogue binding. See [catalogue preservation audit](2026-10-30-english-catalogue-audit.json).

The product guide Markdown and indexed catalogue are synchronised. The live
release refreshes only the public product-help chunks, preserving all other
knowledge chunks and vectors. Existing utility snapshots are retained; the
translated public catalogue may add a new snapshot.

## Verification

Verification uses temporary runtimes and synthetic case/document data. Checks
cover English-only rendered copy, multilingual input compatibility, grounded
source citations, repair preview/save equality, standalone contract review,
human review persistence, mobile layout, stale responses and explicit consent.

The full backend suite passed 695 tests. After the final legacy Agent 2 copy
changes, 82 relevant API/generation/retrieval checks and the Agent 1 boundary
suite passed again. Additional proper-name and wrong-language regressions are
covered by 22 focused generation/retrieval tests.

The individual Agent 1–4 suites also passed: 52, 91, 40 and 62 tests
respectively. The frontend production build and 44 frontend unit tests passed. The 24 selected
browser journeys passed across the release run and the corrected rental-needs
helper rerun. The source selectors for all 160 browser tests in 47 files parse.

Real Jev and Alibaba checks passed for English repair drafting, standalone
contract Q&A with private citations, and public retrieval with official
citations. See [real-provider result](2026-10-30-english-product-real.json).
These tests use synthetic inputs and do not send existing user records.

The workspace `AGENTS.md` records the English product rule for future work.

## Local release

The live workspace is `.workspaces/frontend-demo`; the browser is served at
`http://127.0.0.1:5191` and the API at `http://127.0.0.1:8011`. The release reload
backs up the SQLite databases before replacing the verified local launcher,
checks protected records before/after, and verifies active Jev configuration.
The completed reload verified unchanged `web.sqlite3`, `intake.sqlite3` and
`aftercare.sqlite3` records, all prior utility snapshots, and all non-product-help
knowledge chunks/vectors. The human review inbox retained 10 items. Active Jev
was configured and enabled; the live English page, public provider endpoint and
14 product-help index chunks were checked after reload. The local operational
result is saved in `.runtime/english-product-reload.json`.
Secrets and private database contents are excluded from this document.

## English-chain audit fixes

The follow-up audit reproduced and repaired three regressions:

- Literal English cardinal amounts (for example `seven hundred dollars`) now
  pass the month-to-week budget guard. Complete compound amounts are parsed
  together, so `seven hundred and fifty` cannot justify a model-extracted 700.
  Unsupported arithmetic or a unit-only answer still cannot change the budget.
- Generated prose is checked with the pinned local
  `lingua-language-detector==2.2.0` dependency, including sentence-level checks.
  Confidently identified foreign-language prose is rejected; supplied names,
  source names and quoted excerpts remain literal. Ambiguous short labels are
  not treated as reliable language samples. Detection is offline, adds no AI
  request, and caches the detector rather than private text or query results.
- The knowledge-modal test targets its footer Close button instead of an
  ambiguous page-wide locator shared with the modal's close icon.

Verification: 705 backend tests, 44 frontend unit tests and 16 isolated browser
journeys passed, including the complete rental journey. The final leading-`and`
cardinal adjustment also passed 17 focused budget/language/API tests. Production
build and dependency consistency checks passed. A real-provider call using only
synthetic repair text produced a valid English email and passed the local check
in approximately 61 ms; no existing case or contact data was sent.

## Publication review — 30 October 2026

The trial publication additionally fixes a repair-email guard that rejected a supplied non-Latin building/location or an explicitly introduced Korean name inside otherwise English prose. Two API regressions failed before the fix and now pass; an invented location still rejects. The patch preserves validated source location/name tokens without allowing a foreign-language generated body. Independent re-review confirmed the fix.

Final publication checks: 707 server, 52/91/40/62 member and 6 integration tests passed; 44 frontend tests and the production build passed. See [publication handoff](2026-10-30-trial-update.md) for actual browser scope and retained limitations. These results do not relabel the earlier model/browser runs as newly executed.
