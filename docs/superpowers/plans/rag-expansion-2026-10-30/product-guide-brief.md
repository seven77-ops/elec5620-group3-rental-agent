# Task: trusted English product guide

Work only in `/Users/seven/Documents/AI_coding/5620房产Agent/.workspaces/frontend-demo`. User approved an English website guide alongside official RAG expansion.

Own only:
- data/knowledge/en/product-guide.md
- new server/app/rag/product_guide.py
- server/tests/test_product_guide.py
- docs/superpowers/plans/rag-expansion-2026-10-30/product-guide-report.md

Read actual frontend features and current docs to author accurate help. Explain new case/chat, editing requirements and all matched results, current transit estimates (no fixed arrival time), sourced lifestyle ordering, favorites/comparison and direct single-house selection as parallel choices, selection confirmation/follow-up, inspection question list, lease draft form/AI assistance/preview/manual signatures, uploaded-contract review and independent search/cloud consent/revocation, repair-email polishing vs actual sending, utilities/moving/cleaning provider cards/details, aftercare/bond features. Include no nonexistent agent-reply form, auto bookings, automatic sending, legal-validity guarantee or automatic signature. State existing-language UI labels when useful; guide prose English-first. Avoid personal data, invented case addresses, and legal rules (those belong to official sources). Verify actual capability rather than copying outdated docs.

Required interfaces:
`product_document()` returns dict: document_id product-guide, title Rental assistant user guide, source_url /api/v1/rag/product-guide, source_type product_guide, language en, jurisdiction PRODUCT, scope public, checked_at 2026-10-30, published_at date or null, document_version sha256(text), capture_method Local reviewed product documentation, text from Markdown file. Deterministic across calls; checked date explicit reviewed release metadata, not automatically today's freshness.
`validate_product_document(doc)` verifies local trusted identity, URL, body and version against authored file, returns None or raises ValueError for forged/private/changed records. Parent index already rejects case_id/private scopes; still cover malicious/forged public product input.
`product_guide_html(doc)` returns safe readable English HTML with escaped authored content. No raw HTML execution, scripts, private data, arbitrary file access or fake host URLs. Parent registers actual public HTML GET /api/v1/rag/product-guide, with optional version validation. Rendering may use a small safe heading/paragraph/list formatter or escaped whitespace pre-wrap; keep it readable and source-bound. Do not add frontend routes or dependencies.

Write meaningful tests first: body fidelity/version changes rejected; cannot pass user contract as product; text safely escaped in HTML; headings/help topics map to implemented functionality; renderer no scripted links. You may render in isolated fixture if useful, but do not create user cases/read private uploads. Parent handles source classification, prompt routing, actual endpoint, index publication, UI labeling and integration tests.

No changes to docs JSON main snapshot, shared index/service/assistant/UI files; no commits/reset/clean/restart. Record exact files/tests and uncertain capabilities in the report. Return concise completion and report path.
