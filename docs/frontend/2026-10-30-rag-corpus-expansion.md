# English RAG corpus expansion — 2026-10-30

The user approved all seven recommended knowledge categories and an English website guide. The live corpus now contains **14 documents and 153 chunks**, all covered by `text-embedding-v4` 1024-dimensional vectors. The existing official Bailian rerank and chat configuration is reused.

## Added material

| Document | Kind | Original / scope |
| --- | --- | --- |
| Standard residential tenancy agreement | NSW official template | Full 20-page blank public PDF, updated 21 September 2026 |
| Tenant information statement | NSW official guidance | Full 10-page public PDF, updated 8 October 2026 |
| Rental property condition reports | NSW official guidance | Inspection records and condition-report responsibilities |
| Sharing a residential rental property | NSW official guidance | Subletting, co-tenants, permission and bond changes |
| Off-campus accommodation | University of Sydney advice | Student housing, inspections, costs and scam awareness |
| Tenants and rent increases | NSW official guidance | Notice, renewal, frequency, negotiation and disputes |
| Fair wear and tear versus damage | NSW official guidance | Responsibilities, qualifications and concrete examples |
| Minimum notice periods for access | NSW official guidance | Entry purposes, notice requirements and exceptions |
| Rental assistant user guide | Product help | Actual controls and workflows, separate from tenancy law |

The five previous public guides remain intact. The resulting breakdown is 11 NSW guidance documents / 108 chunks, 1 official template / 20 chunks, 1 University guide / 11 chunks and 1 product guide / 14 chunks. The public PDF originals are saved in `data/knowledge/en/files/`; the English guide is `data/knowledge/en/product-guide.md`. `documents.json` is the combined active corpus and `official-expansion.json` preserves the eight newly captured external references.

## Product behavior

“User guide” beside “Ask rental knowledge” opens `/api/v1/rag/product-guide` as a readable standalone English page. It covers requirements, all matches, approximate commutes, sourced preferences, favorites/comparison and direct selection as parallel choices, inspection preparation, lease form/AI extraction/preview, contract review and separate search consents, repair-email polishing, provider cards, service records and move-out/bond follow-up.

Product explanations search only the product guide. Rental-rule questions exclude product help. Explicit action requests keep the normal workflow and confirmation path, including commands that also mention an explanation. Chinese product questions have a local topic bridge, so no-cloud help search works too. Guidance does not fabricate a user's selected provider or saved contract values.

The shared source display labels NSW Government, official templates, University of Sydney and product help separately. Official PDF citations retain physical page numbers and point to the reviewed official PDF. A complete public PDF page can be quoted within an 8000-character bound; an oversized or syntactically unfinished page is excluded from generation rather than exposed as a complete rule. Its original file and indexed text remain viewable. Other source groups keep their existing 3200-character grouping policy. Cross-page applicability still requires review; citations do not certify legal validity.

## Trust, capture and publication

Only fixed reviewed source tuples are fetched. Reader error pages—including HTTP 200 envelopes containing 502/503 error pages—are rejected. The registered identity, URL and source type are bound in both directions. The two public PDFs are pinned by SHA-256, checked for blank fields where applicable, and validated against fixed local public originals; caller-provided file paths are never used. Product documentation must match its canonical local text and metadata exactly. HTML rendering escapes content and uses a restrictive content-security policy. Historical product citations include a version query; a changed version returns 409.

No private user contract, contact or case history was included in capture, embedding or evaluation. Private contract indexes and consent/revocation checks remain separate. Publication was built in `.runtime/rag-expansion-stage` using the previous 49 cached public vectors and 104 newly generated vectors. A backup of the previous public corpus/index was retained, then the complete verified set was published atomically. The live index version is `c6e77c988f84f5e112e164ffd28987711b644c8836c32a8fdd322b81efc3d5c6`.

## Verification

- 224 backend regression tests passed; 39 focused private/citation checks and 44 final passage/evaluation/expansion checks passed after the last bounded-page and scoring refinements. Counts overlap and are not added together.
- Frontend production build passed. The existing vendor bundle-size advisory remains.
- Eight unique browser scenarios passed, covering the complete rental journey, private consent/revocation, public guidance, intentional abstention, user guide and University provenance. One obsolete “official sources” heading assertion was updated for the new “reference sources” label and both contract tests reran successfully.
- Original unchanged 80-case retrieval benchmark on the expanded corpus: 72/72 annotated target passages at rank 6 with hybrid + rerank, no degraded requests. Keyword-only: 67/72; hybrid without rerank: 70/72. These are retrieval results; the previous full generation score is not relabeled as a new expanded-corpus generation run.
- New English benchmark: 26 questions (24 supported and 2 personal-state questions requiring abstention). Real hybrid/rerank/generation retrieved all 24 targets, produced 2 valid abstentions and had no provider/degradation/exact-citation failures. First run: 25/26 answer checks, with an incomplete PDF-page quote safely rejected. After that page was excluded from generation, the full rerun answered correctly but retained 25/26 due a scorer accepting “4 times” while the answer used the equivalent “4 inspections”.
- The original scoring fixture/report remains saved. A regression now accepts either count noun and additionally requires the explicit 12-month period. Re-scoring the exact same accepted outputs gives 26/26 with zero new provider calls; `rag-expansion-rescored.json` records the source report hash and scoring revision. It is a transparent replay, not a fresh generation run or human legal review.
- UI/API and the guide returned HTTP 200 after reload. Read-only live checks verified English/Chinese product-only scope and separately labeled university/rental sources. All **541 business rows** matched the fresh pre-reload digest `ee1bd3e271c92d2b940701b685c7f243c76c66580bd13cdcdd0a7979cb55f1df`; the case database was backed up before reload.

Reports: `2026-10-30-rag-expansion-original-80.json`, `2026-10-30-rag-expansion-evaluation.json`, `2026-10-30-rag-expansion-verified.json` and `2026-10-30-rag-expansion-rescored.json`, with adjacent review sheets. Independent task reviews are in `docs/superpowers/plans/rag-expansion-2026-10-30/`.

## Maintenance

Run `.venv/bin/python scripts/rag_index.py --refresh --embed` to fetch registered public sources, append the current reviewed product guide and build vectors. A changed pinned PDF requires reviewing the new original/hash before publication. Existing startup seeds an empty index only; it does not silently replace a published version. Update product guide content and its explicit reviewed-release metadata when functionality changes, then rebuild. Public source timestamps are capture metadata, not proof the law cannot change.
