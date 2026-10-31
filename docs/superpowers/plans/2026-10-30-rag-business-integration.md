# RAG quality, private contracts and evidence-backed soft preferences

User approved all three increments after the working English public RAG and real official embedding/rerank activation. Execute without a further approval gate; use only synthetic contracts for tests. Never send existing user contracts to test services.

## Independent deliverables

1. Evaluation: 80 passage-annotated questions, exact reference/citation and condition checks, repeatable keyword vs hybrid vs rerank comparisons, honest failure/degradation reporting, reviewable claims. Agent rag_evaluation owns only evaluation data/scripts/tests/docs; no shared runtime or existing RAG service changes.
2. Soft preferences: rank all already-hard-filtered rows using explicit lifestyle priorities and current attributable area/advertisement evidence. Agent soft_preferences owns focused modules/types/UI/tests; parent integrates shared assistant hooks. Unknown quiet/safety and missing coverage never become verified property features.
3. Private contract retrieval (parent): case+review+hash/version-bound explicit knowledge consent, separate per-document private indexes, page/clause provenance, optional external processing only under extended consent, revocation cleanup, stale-input guards and existing contract-page entry. Public and private evidence retain identities; no arbitrary cross-case filters accepted.

## Parent sequence / acceptance checklist

- [x] Test new private-contract API before implementation: no index without independent consent, other-case IDs rejected, local-only zero cloud calls, actual page/line/section citations, review changes require new consent/reindex, source hash changes stop reads, revocation removes local chunks/vectors and blocks cached/source answers, external consent cannot escalate a local-only grant, concurrent revocation/context change blocks output.
- [x] Add private index/service boundaries and shared answer composition supporting supplied validated evidence without changing public-only ingestion.
- [x] Add case-scoped status/index/search/answers/source/revoke routes; bind requests to current review version/context token. Indexing external work occurs outside business DB write transactions. Publication and consent recheck must prevent revoked/superseded results.
- [x] Add Contract page panel with explicit local indexing consent and separate cloud-processing choice covering embedding/rerank/generation. English query UI; show contract page/section/version and official citations distinctly. Ask through normal chat only when current active private consent exists; never silently fall back to another case/document.
- [x] Review/integrate soft-preference hooks without losing hard-filtered IDs or persisting non-schema keys.
- [x] Review and run 80-case evaluation, preserve keyword baseline and actual hybrid/rerank metrics and failures. Run annotated answer checks and explicitly identify manual-review limits.
- [x] Test regressions including main rental journey; real end-to-end calls use only synthetic contract/public source text. Verify live case data before restart, preserve all existing data, load verified changes and report remaining measured limitations.
