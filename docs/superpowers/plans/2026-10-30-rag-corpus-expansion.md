# English rental and product knowledge expansion implementation plan

**Goal:** Add every user-approved official topic and an accurate English website guide to the existing local RAG, with accurate provenance, working source links and verified retrieval.

**Approved design:** The user approved the seven recommended categories and product guide in the preceding conversation. Retain the five current official snapshots. Add standard lease, tenant information, condition reports, shared housing, University of Sydney off-campus advice, rent increases, fair wear/damage and landlord-access notice guides. Use official public PDF text for the lease/tenant statement when available; retain page/version provenance. Author product guidance from actual implemented UI flows. Keep legal guidance, university guidance and product help distinguishable, and route explanatory product questions to product content without treating them as actions or legal sources. Do not modify business records or index private user material.

**Architecture:** Existing SQLite index and official embedding/rerank adapters stay in place. Extend approved public source kinds, add a strictly trusted local product guide and a public read-only HTML endpoint. Retrieval supports source-kind filtering before ranking; inferred product questions search product help while legal questions exclude product help. The shared UI labels each source accurately. Publish the expanded corpus and vectors atomically only after validation.

**Tech stack:** FastAPI, SQLite FTS/vector adapter, pypdf, React/Ant Design, existing official Bailian configuration.

## Constraints

- Workspace: `/Users/seven/Documents/AI_coding/5620房产Agent/.workspaces/frontend-demo`; reuse it, no reset/clean/commits of unrelated work.
- English corpus; NSW government and sydney.edu.au primary sources only. No invented text for failed downloads.
- Private grants/cases remain isolated. No real user contracts, contacts or conversations sent to providers.
- Reuse existing credentials; never print keys. Real publication embeds public/approved product text only.
- Freshness and version guards, validated citations, conditional source preservation and no hidden generation retry remain.
- Preserve `.runtime/web.sqlite3` and compare its sorted objects digest before/after local reload.

## Tasks / owned interfaces

- [x] Task 1, official capture: `server/app/rag/sources.py`, new `server/app/rag/capture.py`, `data/knowledge/en/official-expansion.json`, public PDF caches under `data/knowledge/en/files/`, focused capture tests. Keep `SOURCES` tuple compatibility; `SOURCE_TYPES` maps ids to `official_guidance`, `official_template`, `student_guidance`. Capture API `capture(source)` / `parse_source(source,raw)` returns validated metadata+English text. Snapshot expansion contains additions only. See focused brief.
- [x] Task 2, product guide: `data/knowledge/en/product-guide.md`, new `server/app/rag/product_guide.py`, focused tests. `product_document()` creates a deterministic local public record; `validate_product_document(doc)` validates its trusted identity/body; `product_guide_html(doc)` returns escaped readable HTML. Source URL `/api/v1/rag/product-guide`, source type `product_guide`, jurisdiction `PRODUCT`. See focused brief.
- [x] Parent integration: test source-kind validation/filtering and working product source links first; extend `index.py`, `service.py`, CLI ingestion, model routing instructions and shared source labels without weakening private boundaries. Preserve source type/page/version in outputs. Add product-only read help entry and explicit jurisdiction-neutral heading. Only "how to" explanations route to help; direct selection/favorite commands retain workflows.
- [x] Add focused expansion questions with exact source/section annotations. Verify all approved categories, original 80 targets retained, lexical/hybrid/rerank distinction, product/legal scope separation, official-template PDF page citations and private consent regression.
- [x] Review files, run backend/browser/build checks. Back up the original public snapshot/index; embed/publish all newly needed public vectors. Run real English questions using only public/approved product text. Preserve index on failure; no silent partial publication.
- [x] Reload the local app after preserving the case DB. Verify expanded counts, vector coverage, help URL, source labels, actual read-only retrieval and unchanged business digest. Write handoff and measured limitations.
