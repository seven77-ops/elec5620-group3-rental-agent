# Private uploaded-contract search

The Contract page now has an “Ask about this contract” panel for the selected uploaded review. Its English-first questions and original quotations use the shared answer model, while the private text index remains local. A contract citation identifies the uploaded filename, review version, PDF page, extracted line range and clause heading. Clicking it opens a protected copy of the current source document at the cited page. Official NSW guidance is separately labeled and cannot establish what a missing private clause says.

## User flow

1. Upload/review a contract using the existing document-consent flow.
2. Open “Ask about this contract”, explicitly enable local search, then index the current version. Cloud processing is a separate optional choice covering embeddings, reranking and answer generation.
3. Enter a question, for example “What does this contract say about cleaning when I leave?” A local-only grant returns matching original excerpts without a cloud request. AI summarization additionally requires the question's external-processing checkbox.
4. “Forget contract search” revokes access and removes derived chunks/vectors. It clears the visible answer immediately, including while an answer is pending. The original uploaded review remains available through its original flow. Normal chat can use the currently selected review only while this independent grant remains active.

## Isolation and invalidation

Each grant binds case, review, original consent, current selection, review version/digest and uploaded-file SHA-256. A current context token is required. Other-case review IDs return 404 before consent lookup. Changed review contents, selection or file bytes require re-enabling the current version. Missing or revoked indexes are not recreated on read.

Derived SQLite files are isolated under `.runtime/rag-private/<case-review-hash>/index-<grant>.sqlite3`. Publication checks permission/version again after external calls. Questions recheck before each private cloud stage, before generation and before returning. Revocation also removes private quotation copies from derived conversation/receipt results; historical reads and in-flight final persistence revalidate grants. Revoking the original upload consent revokes derived search grants too. If file deletion fails, revocation remains committed and cleanup is explicitly pending.

The routes live under `/api/v1/cases/{case_id}/rag/contracts/{review_id}`: `status`, `index`, `search`, `answers`, `revoke`, `sources/{chunk_id}` and `document`. The document endpoint validates the active grant and exact returned bytes, uses `Cache-Control: no-store`, and supports PDF page links. These boundaries inherit the current local application's case model; they are not a replacement for production multi-user authentication.

## Verification

- 16 focused backend tests cover local-only zero-cloud behavior, page-2 PDF citation, absent private facts, scoped source/document access, stale versions/hashes, idempotency, revocation, filesystem cleanup failure, concurrent revocation, stale history, and no subsequent cloud/persistence leaks.
- Two browser tests cover independent consent, citation display, forget/re-enable and ignoring an answer that finishes after revocation.
- A real end-to-end probe used only a synthetic two-page PDF. All four chunks received official 1024-dimensional embeddings; contract/public vector search and reranking plus Qwen generation returned a page-2 cleaning citation with its fair-wear-and-tear qualification in 22.31 seconds. Revocation removed the derived index and old source access returned 403.

No existing private user contract was sent to a provider for verification. Semantic similarity and valid source links do not prove every summary preserves every legal condition; unsupported/malformed summaries fall back to excerpts and the public answer benchmark records remaining limits.
