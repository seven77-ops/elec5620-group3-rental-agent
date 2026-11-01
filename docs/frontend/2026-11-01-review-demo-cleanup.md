# Local review test-data cleanup and legacy housing browsing

The user authorized clearing previous test reports/evidence and contract-check
caches, replacing repetitive review history with distinct examples, and fixing
legacy Housing recommendations loading failures.

## Active-data changes

The offline maintenance tool defaults to a read-only plan. Applying it backs up
all five SQLite databases and relevant uploaded/private-index files outside the
active runtime, verifies no source data changed during planning, and removes the
authorized report/check objects in an exclusive transaction. Database integrity
is checked before removing backed-up upload files.

Cleared 18 contract reviews, 33 review snapshots, contract intake/AI/consent
caches, two direct issue reports, six legacy review sets and 21 uploaded files.
Old request receipts that could expose removed results are also removed. Private
contract quotation copies in derived chat results are redacted if present;
original user messages remain.

Retained all 93 case containers, Agent 1 profiles, selected properties, evaluations,
conversations, favorites, six saved unsigned lease drafts and living/service
records. Independent bond records/outcomes and their evidence are retained.
Original aftercare clock timestamps remain unchanged. Public RAG and utility
catalogue database hashes are unchanged. Backups are in `.runtime-backups/`,
ignored by Git and never served as application attachments.

## Demonstration history

Five explicit **Demo example** cards are installed in a separate runtime object
kind, only when the maintenance tool is applied. They are not tenant submissions,
contract approvals or pending review tasks and are excluded from Issue report
History. The cards have distinct titles, fictional source excerpts and advice:

1. Bond deduction for pre-existing wall marks.
2. Missing chair in the furniture inventory.
3. Cleaning charge without an itemised invoice.
4. Lease end date before the start date.
5. Weekly rent differs between two contract sections.

Demo cards have no editable advice or links to nonexistent tenant cases. New
user reports continue through the usual Pending → advice → History process.
Restarting services never resets new submissions or recreates removed tests.

Other pages do not require preloaded user cases. Public listing snapshots,
knowledge/help sources and provider directories are reference data and remain
installed. Upload a fictional contract file during the contract-check demo;
no previous successful check needs to be cached.

## Housing recommendations

The reported case was an early form-only case without an Agent 1 session.
Recommendation-context reads incorrectly invoked the write-side Agent 1 guard,
then the frontend left the loading state active on the error.

An unchanged historical confirmation can now supply read-only filter context.
Historical form values still pass through the legacy template-suppression policy;
there is no automatic preference confirmation or Agent 1 upgrade. Browsing,
manual filters and favorites work. A visible **Start a new search** action starts
a current-format case for new requirements and property selection. Backend
write/selection guards remain unchanged. Missing historical evaluation caches
fall back to saved filter context, and context failures stop the loading spinner.

## Validation

- 23 related backend tests passed, including cleanup idempotency, retained drafts,
  independent bonds, evidence still used by repairs, private chat redaction and
  legacy read-only filtering without weakening Agent 1 writes.
- 73 frontend unit tests and 9 browser scenarios passed.
- Frontend build, targeted formatting and `git diff --check` passed. The existing
  large vendor-chunk warning remains.
- Live checks: Pending 0, five unique read-only demo cards, empty contract-review
  lists, working legacy listing retrieval and enabled filters.
- All five live databases pass integrity checks; all 20 retained Agent 4 records
  remain schema-valid. Effective Jev mode remains `active`.
