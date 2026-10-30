# Current corpus status

The live knowledge corpus was expanded on 2026-10-30 to **14 documents / 153 fully embedded chunks**: 12 NSW Government sources (including complete standard-lease and tenant-information PDFs), one University of Sydney guide and one reviewed English product user guide. Source labels and product/rental scopes are distinct. Open `/api/v1/rag/product-guide` from the local app to read the product guide. See `2026-10-30-rag-corpus-expansion.md` for exact contents, verification and maintenance. The historical first-increment record follows.

# English-first public rental knowledge

## Delivered scope

The first working increment adds a shared public knowledge service to the existing React + FastAPI application. The corpus and original quotations are English. The shared panel answers in English; chat chooses English or Chinese based on the current question. Chinese keyword support is a small explicit topic bridge, not a general translator. Cross-language semantic retrieval remains dependent on configured embeddings.

The initial snapshot contained five NSW Government guides and 49 heading-based chunks: repairs, bond refunds, tenancy notices, breaking fixed terms, and dispute resolution. Sources were captured on 2026-10-30 through Jina Reader from the approved public URLs. One additional maintenance page returned a 403 error and was excluded. Navigation and related-link sections were removed. Snapshot ingestion rejects error pages; it never guesses their missing text.

- Source snapshot: `data/knowledge/en/documents.json`.
- Reviewed URL registry: `server/app/rag/sources.py`.
- Local index: `.runtime/rag.sqlite3`, separate from business cases.
- Entry points: normal chat for public guidance questions, plus “Ask rental knowledge” on chat, contract and aftercare pages.
- All matching listings, selected house, favorites, confirmed requirements, contract drafts and aftercare confirmations keep their existing business paths. RAG does not change them.

Public ingestion does not index private contracts or case history. The separately consented contract search added in the next increment is documented in `2026-10-30-contract-rag.md`. Neither service certifies legal correctness. English official knowledge is not a claim that every product page has been translated.

## Retrieval and generation

SQLite FTS5 with Porter/Unicode tokenization searches English text. Optional 1024-dimensional `text-embedding-v4` vectors are persisted in SQLite and searched with exact cosine for this small corpus. This intentionally avoids adding Chroma deployment dependencies in the first increment; the store is isolated behind `KnowledgeIndex` for later replacement if scale requires it.

Keyword and vector results use RRF fusion, with optional `qwen3-rerank`. Online embedding has a six-second transport deadline and reranking ten seconds. Offline embedding batches use a separate 30-second deadline (adapter overrides are bounded to 1–60 seconds); answer generation has a separate 30-second deadline. Ordinary startup and local-only search perform no external network requests. Text and heading-context changes produce new chunk IDs; unchanged chunks reuse vectors. Different embedding models/dimensions cannot be mixed. Publication is atomic, including vector generation: failure does not replace the old live index. Startup seeds an empty index only; an existing published index changes through the indexing command.

Queries with no evidence return `insufficient_evidence` without invoking the generation model. Sources checked more than 90 days ago are excluded by the current freshness policy; a recent check is not proof a rule cannot change. Refresh the sources before demonstration or deployment.

The generation model selects existing evidence and paragraph IDs. The backend retrieves exact quote text itself, checks returned IDs, schema and amounts/dates, and builds URLs and source metadata. Unknown/invalid IDs, bad model output, provider failure or source-version changes do not become an unsupported completed answer. A failed summary returns viewable English excerpts (`sources_only`). No full-case history is sent to the answer model.

A valid quote is not by itself proof a paraphrase is legally correct or preserves every exception. This still needs annotated claim-support review before broader release; the smoke evaluation below does not measure that.

## Official Bailian configuration

The user confirmed that the official Bailian key and existing chat key are the same. RAG now reuses the active chat key when `RENTAL_RAG_API_KEY` is absent or blank; an explicitly supplied RAG key takes precedence. The active key selection follows the chat provider’s generic-versus-legacy configuration. Retrieval destinations are still configured explicitly and are never guessed from the chat URL.

Append the RAG block from `.env.example` to the existing local `.env`, replacing the two endpoint placeholders with values from the official Bailian workspace and region matching the shared key. Leave the optional RAG key blank to reuse the configured chat key:

```
RENTAL_RAG_API_KEY=
RENTAL_RAG_EMBEDDING_URL=YOUR_FULL_HTTPS_EMBEDDINGS_ENDPOINT
RENTAL_RAG_RERANK_URL=YOUR_FULL_HTTPS_RERANK_ENDPOINT
RENTAL_RAG_EMBEDDING_MODEL=text-embedding-v4
RENTAL_RAG_RERANK_MODEL=qwen3-rerank
RENTAL_RAG_DIMENSIONS=1024
```

One official key can be supplied to both adapters when that workspace/region/account has both model permissions. Obtain the exact endpoints from the official console. Merely sharing a key does not establish that a particular endpoint/model is enabled for the account. A separate model training or hosted Bailian knowledge-base service is not needed for this local-index architecture. Never paste keys into chat or commit a filled `.env`.

Then run from this worktree:

```
.venv/bin/python scripts/rag_check.py
.venv/bin/python scripts/rag_check.py --probe
.venv/bin/python scripts/rag_index.py --embed
```

`--probe` sends only synthetic English strings and verifies real embedding dimensions and rerank indexes. `--embed` sends the five **public** guide texts to the configured embedding endpoint. It reuses unchanged chunk vectors. Restart `scripts/dev.py --web-port 5191 --api-port 8011` after editing settings so the API loads them. The case-scoped status endpoint reports actual configuration and vector coverage.

Refresh reviewed public sources and rebuild without cloud calls:

```
.venv/bin/python scripts/rag_index.py --refresh
```

A refresh failure leaves the previous published index in place. Rerun with `--embed` when refreshed text needs new vectors. Index rebuild alone does not update source checked dates.

## Interfaces

- `GET /api/v1/cases/{case_id}/rag/status`
- `POST /api/v1/cases/{case_id}/rag/search`
- `POST /api/v1/cases/{case_id}/rag/answers`
- `GET /api/v1/cases/{case_id}/rag/sources/{chunk_id}`

POST bodies contain `question`, boolean `allow_external_ai`, and optional `language` (`en` default or `zh`). With external processing disabled, the answer endpoint returns source excerpts and makes no model request. A question containing private information should only be sent after the user chooses external processing. The shared panel explicitly covers this permission and distinguishes public guidance from private-contract analysis.

No arbitrary-URL ingestion or client-controlled case/scope filters are exposed. Every route requires an existing case. The public corpus contains no private cases; this does not claim production multi-user authentication.

## Verification and remaining setup

- RAG unit/API coverage includes independent configuration, provider payload/response validation, model/dimension mismatch, Chinese topic bridge, unknown queries, public-only ingestion, atomic publication, model outage fallback, invalid citations, stale source versions, and unchanged business cases.
- Offline smoke questions: `data/knowledge/evaluation.en.json`; run `.venv/bin/python scripts/rag_evaluate.py`. The 20 questions passed document-presence-at-20 and no-result checks. The report is `docs/frontend/2026-10-30-rag-retrieval-smoke.json`. This is a small retrieval smoke test, not the proposed 80-case full evaluation or a legal-quality score.
- Real existing qwen-plus generation with a generic English repair question and only public evidence succeeded in approximately 7.62 seconds, returning three claims with backend-resolved citations. The test used a temporary case database.
- On 2026-10-30 the user supplied the Beijing workspace base URL and confirmed the existing chat key is the same official key. Real `text-embedding-v4` and `qwen3-rerank` synthetic probes both succeeded using that shared key. All 49 public English chunks were embedded at 1024 dimensions and published in the local index. Actual endpoints live only in ignored local `.env`; no key was duplicated or printed. A separate RAG key is optional and takes precedence over shared-key fallback.

The follow-on three increments are now implemented: see `2026-10-30-rag-quality.md`, `2026-10-30-contract-rag.md` and `2026-10-30-soft-preferences.md`. The 80-case evaluation replaces the historical 20-question smoke test. The existing 1000-listing structured search is deliberately not limited by the number of retrieved evidence chunks.


## Shared-key activation verification (2026-10-30)

The user confirmed key reuse and supplied the official Beijing workspace base URL. The local configuration now contains the documented `/compatible-mode/v1/embeddings` and `/api/v1/services/rerank/text-rerank/text-rerank` endpoints on that workspace. Chat settings were not replaced.

Real verification used temporary cases and only public source material:

- Synthetic embedding probe: succeeded with 1024 dimensions.
- Synthetic rerank probe: succeeded with both original candidate indexes returned.
- Public-corpus index: all 49 chunks embedded and published successfully. The initial six-second online deadline was too short for a batch; offline builds now use a separate bounded 30-second deadline.
- Repair question: HTTP 200, `answered`, methods `keywords + vectors + rerank`, three citations, approximately 13.76 seconds, no degraded-mode warnings.
- Security-deposit question: HTTP 200, `answered`, methods `keywords + vectors + rerank`, three citations, approximately 11.36 seconds, no degraded-mode warnings.
- Irrelevant quantum/astrophysics question: no source results. A diagnostic fix distinguishes this normal absence of matches from a missing semantic index.

These are observed real requests, not a guarantee for every question or future response time. The 20-question offline smoke report remains a keyword baseline; full comparative evaluation and legal claim-support assessment remain separate work.
