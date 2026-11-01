# Task: official English corpus capture

Work only in `/Users/seven/Documents/AI_coding/5620房产Agent/.workspaces/frontend-demo`.

User explicitly approved adding the seven proposed categories and product guide. Your independent role is capture of the eight official documents (first category is two documents). Own only:
- server/app/rag/sources.py
- new server/app/rag/capture.py
- data/knowledge/en/official-expansion.json (additions only, do not alter documents.json)
- data/knowledge/en/files/ (public originals only)
- server/tests/test_rag_capture.py
- docs/superpowers/plans/rag-expansion-2026-10-30/official-capture-report.md

Read existing scripts/rag_index.py, index.py and sources.py. Parent owns their integration and validation. Retain SOURCES tuples `(id,title,url)` compatibility and add SOURCE_TYPES mapping. Capture/parse functions exported from new capture.py; parent will replace script definitions with imports.

Required additions / proposed IDs:
1 standard-lease: NSW standard residential tenancy agreement, official_template. Landing https://www.nsw.gov.au/housing-and-construction/rental-forms-surveys-and-data/resources/standard-residential-tenancy-agreement . Verify/download actual current PDF or reuse ONLY the unchanged official blank template in agent3/data/templates after verifying official landing's version/hash; never read case uploads. Preserve full actual PDF text with `## Page N` headings, `page_count`, `download_url`, sha/version, no signatures filled. Existing blank is nsw-residential-tenancy-2026-09-21.pdf.
2 tenant-information: full official tenant information statement PDF preferred, official_guidance. Discover actual current official link from the official site. If unavailable, use the verified official page Information a tenant should get at the start of a tenancy and report limitation explicitly (never invent a PDF).
3 condition-reports: https://www.nsw.gov.au/housing-and-construction/rules/rental-property-condition-reports
4 shared-housing: https://www.nsw.gov.au/housing-and-construction/rules/sharing-a-residential-rental-property
5 student-off-campus: https://www.sydney.edu.au/study/accommodation/off-campus.html , student_guidance (NOT NSW Government).
6 rent-increases: https://www.nsw.gov.au/housing-and-construction/renting-a-place-to-live/rent-increases
7 wear-and-damage: https://www.nsw.gov.au/housing-and-construction/rules/fair-wear-and-tear-versus-damage-rental-properties
8 landlord-access: https://www.nsw.gov.au/housing-and-construction/rules/minimum-notice-periods-for-access-to-rental-property

All records language en, scope public, jurisdiction NSW; source_type per mapping. Add capture metadata checked_at 2026-10-30 client Sydney date, canonical source_url, content/document hash. Never pretend a failed capture is text. Use source-based safe fetch, allowlisted official hosts, bounded response sizes and no arbitrary caller URLs. PDF text headings page based; parent will derive chunk page metadata. Reader snapshots should remove navigation/footer, preserve all material qualifications/tables. Existing parse_source behavior may be reused with robustness fixes. Tests first for parse/capture/PDF validation, reject errors/private/redirect/unapproved links. No external calls during ordinary unit tests. Network read calls require escalation and user authorized official public retrieval. Use relevant agent-reach/PDF skills as needed. Do not print credentials or load user contracts.

Do not rebuild live indexes, restart services or edit shared index/service/UI. No commits/reset/clean. Record fetched versions, extraction quality, test commands/results, exact files and any access failures. Return concise completion and report path.
