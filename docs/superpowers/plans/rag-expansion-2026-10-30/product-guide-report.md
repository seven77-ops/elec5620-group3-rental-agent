# Product guide implementation report

Reviewed release: 2026-10-30.

## Files changed

- `data/knowledge/en/product-guide.md`: English-first public guide, with existing Chinese and English control labels. Covers case versus conversation creation, requirements and all matches, approximate university commute, sourced lifestyle ordering, optional favorites/comparison versus direct selection, confirmation and inspection checklist, lease drafting/manual signatures, uploaded-contract review and independent search/cloud permissions, repair email preparation versus sending, utility/moving/cleaning provider details, move-out plans, bond follow-up, public knowledge and stale state recovery.
- `server/app/rag/product_guide.py`: canonical `product_document()`, strict `validate_product_document(doc)` and escaped `product_guide_html(doc)`.
- `server/tests/test_product_guide.py`: seven focused unit tests, including twelve guide-heading/UI-control mappings.
- `docs/superpowers/plans/rag-expansion-2026-10-30/product-guide-report.md`: this report.

No shared index, source snapshot JSON, assistant/service/router, UI, endpoint or publication files were changed by this task. No commits, resets, server restarts, real cases or private uploads were used.

## Trust and rendering

The canonical body is read only from the repository's fixed `data/knowledge/en/product-guide.md` path. Its SHA-256 version uses the exact UTF-8 text. Required metadata is explicit: document ID `product-guide`, title `Rental assistant user guide`, source URL `/api/v1/rag/product-guide`, type `product_guide`, jurisdiction `PRODUCT`, public scope, language `en`, checked date `2026-10-30`, publication date `null`, capture method `Local reviewed product documentation`. The checked date does not change with the wall clock.

Validation requires exact equality with the complete current local canonical record. Changes to body, hash, identity, URL, scope or release metadata fail. Adding case IDs, arbitrary paths, private contract text or any extra fields also fails. A recomputed hash cannot make a caller's replacement body trusted. Product records must be validated before the index adds chunk metadata.

The HTML renderer validates first, then escapes all authored heading, paragraph and list text. Raw HTML, images and Markdown links stay text. It emits no links, scripts, external resources or dynamic event attributes. Readability uses static local CSS, semantic headings and lists, an English document language, mobile viewport metadata and release/version footer. The renderer does not resolve the source URL or infer a host. Parent integration supplies the real public HTML endpoint and optional version checking.

## Capability evidence inspected

- `frontend/src/app/App.tsx`: case creation, current navigation labels and real-listing page mapping.
- `frontend/src/features/assistant/Assistant.tsx`, `RentalNeeds.tsx`, `RecommendationControls.tsx`, `ListingResults.tsx`, `CommuteResults.tsx`, `needs.ts`: conversations, requirement editing, changed-context warnings, result expansion/area controls and removal of fixed arrival clock fields from approximate discovery requirements.
- `frontend/src/features/RealRecommendations.tsx`: explicit filter application, zero-result alternatives, twenty-row pagination, direct selection and optional favorites.
- `frontend/src/features/real-data/ListingDetails.tsx`, `UsydCommute.tsx`: property source/photos, studio caveats, campus reference, estimated modes, source links and independent map directions.
- `frontend/src/features/assistant/AreaAdvice.tsx`, `server/app/areas/evidence.py`, `server/app/assistant/soft_preferences.py`: evidence categories/coverage and deterministic ordering after hard filtering. Missing or stale area sources do not establish absent facilities; quietness and safety do not score.
- `frontend/src/features/favorites/ListingActions.tsx`, `FavoritesDrawer.tsx`, `FollowupDialog.tsx`, `frontend/src/features/candidate/CandidateFollowup.tsx`: two-to-four property comparison, direct selection confirmation, missing-field supplement and actual downloadable inspection checklist. There is no inspection booking or agent-reply form in that checklist.
- `frontend/src/features/contracts/LeaseDraft.tsx`, `DraftAi.tsx`, `LeasePdfPreview.tsx`: manual entry, incomplete saves, independent optional AI field extraction, confirmation, saved-version PDF preview/download and blank signature fields.
- `frontend/src/features/ContractUpload.tsx`, `Contract.tsx`, `ReviewHistory.tsx`, `frontend/src/features/knowledge/ContractKnowledgePanel.tsx`, `server/app/rag/contracts.py`: upload limits, local field extraction/correction, original processing consent and revocation, local/cloud indexing permissions, per-question AI and search forgetting. Search revocation is distinct from deleting the original case/review.
- `frontend/src/features/living/RepairComposer.tsx`, `Repairs.tsx`, `RepairFollowup.tsx`: editable AI-polished drafts, copying, email-client opening, user-reported status and follow-up records; saving does not send email.
- `frontend/src/features/living/Utilities.tsx`, `UtilityProviderDetails.tsx`, `Services.tsx`, `LivingHub.tsx`: provider details, available plans/tariffs and sources, saved utility preferences, moving/cleaning company details and user-maintained quote/booking records. Saving a booking record does not submit a booking.
- `frontend/src/features/Aftercare.tsx`, `AftercarePlan.tsx`, `AftercareBond.tsx`, `AftercareBondDetails.tsx`: practical schedules, evidence references, explicit date changes, bond facts/claims, dispute review gates and unsent factual drafts.
- `frontend/src/features/knowledge/KnowledgePanel.tsx`: public source lookup and optional public-question/excerpt cloud processing.

## Verification

Tests were written before the module and guide. The first run produced seven explicit assertion failures because the trusted module was absent. After implementation, an initial prose assertion exposed a capitalization mismatch; the capability phrase check was corrected to compare case-insensitively, preserving its intended content assertion.

Final command from the frontend-demo workspace:

```text
.venv/bin/python -m unittest server.tests.test_product_guide -v
Ran 7 tests
OK
```

Coverage includes canonical body/version fidelity; deterministic complete metadata; caller mutation isolation; rejection of modified text even with its newly recomputed SHA-256; mutation of every release/identity metadata field; missing/invalid records; private scope, contract, fake-host URL and arbitrary path impersonation; renderer validation; semantic English HTML; and escaped malicious authored fixture text containing raw script/image/anchor tags and a `javascript:` Markdown link. Malicious fixture reads occur only in a temporary directory patched into the test's trusted source constant.

No user-case integration tests or live network/provider calls were needed for these pure document functions. Parent owns index, endpoint, routing, UI labeling and publication integration verification.

## Configuration-dependent or unverified runtime behavior

- Available AI services, OCR support, live journey conditions, property availability and provider prices/coverage were not exercised. The guide states these as conditional or requiring independent verification.
- The guide targets the implemented real-listing flow and notes that demonstration labels and upload limits differ. It does not extend the supported lease template to every tenancy arrangement.
- No law, legal deadline, signed-agreement validity guarantee, automatic signature, automatic inspection booking, automatic email sending, provider-account opening or booking submission is claimed.
- HTML structure and escaping were checked by Python's HTML parser. No live browser visual check or actual public endpoint check is claimed by this subtask.
