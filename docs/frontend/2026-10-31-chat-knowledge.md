# Rental knowledge through the main conversation

General rental and product-help questions now use the existing main-chat knowledge route. The redundant public knowledge button and modal have been removed from the assistant, contract and aftercare headers. The chat already displays grounded answers, source citations and expandable source excerpts, so no new routing or backend business behavior was needed.

The private ContractKnowledgePanel remains in place. Uploaded contract search, document processing consent and case scope remain separate. Public source-only retrieval is still available through the existing API. Rental requirements, saved profiles and search filters are preserved during public knowledge questions; the conversation can resume intake afterward.

## Changes

- Removed KnowledgePanel mounts and retired the unused public modal component.
- Migrated browser coverage to ordinary chat, including English and Chinese input, missing personal facts, product help, university advice, reloads and resumed intake.
- Added six isolated backend main-chat audit tests, including active Jev routing, grounded citations, saved-profile preservation and private-contract boundaries.
- Updated the reviewed public help source, its canonical documents snapshot and the bilingual presentation examples.
- Backed up the local public RAG SQLite index before refreshing only its 14 product-help chunks. All 139 other chunks and their vectors were verified unchanged.

## Verification

- Frontend production build passed; Vite reported its existing large-vendor-chunk advisory.
- Frontend unit checks: 66 passed.
- Browser regression: 17 passed (chat RAG, private-contract consent and page flows).
- Focused backend audit: 19 passed. The strengthened saved-profile interruption case also passed independently.
- Product-guide source/snapshot checks: 8 passed.
- Browser checks use temporary runtimes, synthetic cases and injected AI transports. They do not exercise remote production AI services or modify existing user cases.

An obsolete aftercare attachment-error test was retired because that section was removed earlier. The retained tenancy-source error test still checks readable error presentation. No production aftercare behavior was changed to satisfy the stale test.
