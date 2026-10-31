# Official English corpus capture — 30 October 2026 (Sydney)

Captured all eight approved public documents. Every record has language `en`, scope `public`, jurisdiction `NSW`, canonical `source_url`, checked date `2026-10-30`, text `content_hash`, and `document_version`. No case uploads, user contracts, completed signatures or private documents were read. The existing `documents.json`, live index and services were not changed by this capture task.

## Captured sources

| ID | Source classification | Official version / publication | Extracted text |
| --- | --- | --- | --- |
| standard-lease | official_template | PDF updated 21 September 2026; landing published 7 April 2026 | 20 pages; 62,752 characters |
| tenant-information | official_guidance | PDF updated 8 October 2026; landing published 7 April 2026 | 10 pages; 34,202 characters |
| condition-reports | official_guidance | Published 24 May 2024 | 6,564 characters |
| shared-housing | official_guidance | Published 20 October 2026 | 10,949 characters |
| student-off-campus | student_guidance — University of Sydney | No publication date supplied by Reader | 4,716 characters |
| rent-increases | official_guidance | Published 10 October 2025 | 7,571 characters |
| wear-and-damage | official_guidance | Published 21 September 2026 | 6,575 characters |
| landlord-access | official_guidance | Published 24 May 2024 | 4,901 characters |

Canonical landing URLs are recorded in `server/app/rag/sources.py` and each snapshot record. The University of Sydney page is explicitly classified as student guidance, not NSW Government guidance.

### Original PDFs

- Lease: https://www.nsw.gov.au/sites/default/files/noindex/2025-06/residential-tenancy-agreement-form.pdf
  - 568,096 bytes; SHA-256 `5addb961d6864a794f1f5e44a74e21e5216e762eeeac9e176ec088c004480c64`.
  - HTTP Last-Modified: `Sun, 20 Sep 2026 22:06:09 GMT`; official landing says 21 September 2026 (Sydney).
  - Hash exactly matches the existing approved blank `agent3/data/templates/nsw-residential-tenancy-2026-09-21.pdf`. Downloaded public bytes are saved without modification. All form fields were empty/off; no populated signatures appeared on the rendered pages.
- Tenant information: https://www.nsw.gov.au/sites/default/files/noindex/2025-05/tenant-information-statement.pdf
  - 244,290 bytes; SHA-256 `a4e0eb3924f1813bab83a75c4e97ae62ec9098be11d41e8abce9f2ede1213dce`.
  - HTTP Last-Modified: `Thu, 08 Oct 2026 05:08:00 GMT`; official landing says 8 October 2026.

## Extraction and safety

`capture.py` exports `capture(source, *, client=None, checked_at=None)`, `parse_source(...)`, and `parse_pdf(...)`. The original `(id, title, url)` tuples remain compatible. `SOURCE_TYPES`, `PDF_DOWNLOADS`, and `PDF_SHA256` provide reviewed type/download metadata.

Capture accepts only complete registered source tuples, uses HTTPS fixed hosts/URLs, disables redirects and proxy environment settings, bounds streamed responses (2 MB Reader / 12 MB PDF), and rejects HTTP failures, error/challenge pages, source-envelope mismatches, unapproved PDF links, wrong PDF media types and changed PDF hashes. A future replacement of either official PDF requires explicit review/update of the pinned public original hash. Populated lease fields/annotations, encrypted/invalid PDFs and pages without extractable text are rejected. Ordinary unit tests make no network calls.

PDF extraction retains the complete actual text from every page with `## Page N` headings, `page_count`, original-byte SHA-256, download URL, version label and Last-Modified. No OCR was necessary. Minimum extracted page text was 680 characters for the lease and 2,653 for the tenant statement. All 30 pages were rendered with Poppler and inspected in a contact sheet; blank lease fields and signature areas were confirmed. The source PDFs remain available for exact visual layout; extraction is reading-order text and does not reproduce form geometry.

Reader captures remove navigation/cookie/footer chrome. Material requirements, exceptions, examples, comparison tables and legislative links remain. University duplicate malformed card rows/CSS markers were removed while retaining the complete clean accommodation lists and rental advice. NSW related-content card sections are omitted after the substantive article and legislation links.

One discovery URL guessed under `starting-a-residential-tenancy/information-a-tenant-should-get-at-the-start-of-a-tenancy` returned a 200 Reader envelope titled “Page not found”. It was rejected and never included. The approved lease landing linked the correct tenant-information resource landing, whose current PDF was successfully downloaded. There are no outstanding capture access failures and no fallback/invented PDF.

## Verification

- Initial offline test run: six expected failures before implementation (missing capture module/type mapping).
- Final after HTTP-200 error-page hardening: `.venv/bin/python -m unittest server.tests.test_rag_capture -v` — 9 tests passed.
- Additional snapshot audit: eight metadata/text hashes verified; PDF page headings exactly 1–20 and 1–10; saved original PDF hashes match capture metadata and pinned hashes.
- `git diff --check -- server/app/rag/sources.py server/app/rag/capture.py server/tests/test_rag_capture.py data/knowledge/en/official-expansion.json` — passed.
- No live index rebuild, vector/embedding publication, service restart, commit, reset or clean performed.

## Exact owned files

- `server/app/rag/sources.py` — eight source tuples, source classifications and reviewed PDF URL/hash maps.
- `server/app/rag/capture.py` — bounded public capture, Reader parsing, complete PDF extraction and validation.
- `server/tests/test_rag_capture.py` — offline safety, parser, metadata and PDF boundary checks.
- `data/knowledge/en/official-expansion.json` — eight captured additions only.
- `data/knowledge/en/files/standard-lease-2026-09-21.pdf` — unchanged public blank original.
- `data/knowledge/en/files/tenant-information-2026-10-08.pdf` — unchanged public official statement.
- `docs/superpowers/plans/rag-expansion-2026-10-30/official-capture-report.md` — this report.

Parent integration must merge these records with existing knowledge and the product guide, import the new capture functions into the refresh script, accept the reviewed source types, derive PDF page chunk metadata, validate retrieval and publish through its normal workflow.

## Follow-up: HTTP-200 Reader error pages

A separate integration review found that Reader envelopes with `Title: 503 Service Unavailable` or `Title: 502 Bad Gateway` and a roughly 400-character error body passed the original parser despite the outer HTTP success response. Before the fix, a focused new test reproduced acceptance in six error-title/leading-body subcases (503, 502, 504 and 500 titles; 503 and 502 leading body labels).

The parser now recognizes complete HTTP failure labels in the Reader title or the first meaningful body line, and checks again after removing navigation before an H1. It supports standard error labels with optional HTTP/status-code prefixes and server suffixes. The check is anchored to complete labels rather than searching for `503` or `502` throughout ordinary prose. Existing source, size, challenge and HTTP-response checks remain active.

Regression tests cover both direct parsing and a mock HTTP 200 capture; leading error headings after navigation; legitimate guidance that mentions both “503 Service Unavailable” and “502 Bad Gateway”; and ordinary explanatory prose beginning “503 Service Unavailable can appear…”. The positive fixture compares normalized text, consistent with the parser's existing whitespace trim. All nine capture tests pass without network calls. Re-parsing the six previously captured official HTML snapshots yields their identical saved content hashes, so the accepted public corpus is unchanged. The owned-file whitespace check also passes. This fix changed only `capture.py`, `test_rag_capture.py` and this report; no shared index, scope or UI files were edited.
