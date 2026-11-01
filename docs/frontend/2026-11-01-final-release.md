# Final course delivery — 1 November 2026

The shared final submission is `main`, integrated through [PR #7](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/7). The earlier trial branch and dated records retain the implementation history. New checkouts should follow the root README and use `main`.

## Integrated result

- Agent1 preference confirmation/versioning feeds Agent2 filtering, recommendations, favorites and explicit property selection. The bundled catalogue contains 1,000 advertisement snapshots, source links and qualified commute references. All areas/Reset filters preserve saved needs and the selected property.
- Agent3 supports unsigned lease drafting and consented document upload, read-only checks, original source excerpts and separately authorized private/AI processing. A record opened from Human review now binds the exact review ID within the current case; it never silently substitutes a later upload.
- Agent4 aftercare surfaces include My home with saved providers/services, In progress, repairs, and the simplified Issue report / History flow. Reports and uploaded evidence retain their original content; human advice is explicitly saved and returned to the user.
- English demo examples, dates and authored UI are consistent. Original user messages, uploaded documents, saved source quotations and business records are preserved. The retired Case progress UI redirects to the same case's assistant; the backend records/API remain.
- Public RAG review can use up to 15 seconds of the existing remaining deadline. Source/claim support checks and atomic fallback remain enforced. Runtime cleanup is an explicit, backed-up offline maintenance action; it is never run automatically on startup or by pulling this release.

## Final verification

Verification used an isolated frozen checkout, temporary synthetic cases and model doubles. No private user contracts or existing runtime data were used.

- Server discovery: 812 checks, 810 passed in the first run; two CLI checks initially failed because the isolated checkout lacked its expected `.venv/bin/python`. Adding a test-only virtualenv link resolved both, and the two targeted CLI checks passed. No product-code change was needed for that environment issue.
- Member suites: Agent1 52, Agent2 91, Agent3 41, Agent4 62; handoff integration 6. These are separate command scopes, not an inflated count of unique acceptance criteria.
- Frontend logic/API checks: 73 passed; TypeScript/Vite build passed again after the contract-link fix. The existing vendor bundle-size advisory remains.
- Browser checks through Chrome: older contract A versus later B (failure reproduced before fix, then exact ID/file/source passed), unavailable review rejection and explicit latest action; issue submission without tenancy, newest-first inbox, saved advice and user history; My home sections; All areas/Reset filters restoring 1,000 catalogue records.
- A two-upload browser regression is included at `frontend/e2e/contract-record-navigation.spec.ts`; the scenario was exercised through Chrome in this release audit. A full automated Playwright, mobile or Windows rerun was not performed. No fresh live external AI/transport call is claimed.
- Independent read-only review found the contract-link source mismatch; it was fixed and re-reviewed with no remaining merge blocker.

## Running and data boundaries

The app is a loopback/local course demonstration. The Human review UI opens the local queue directly; this release does not add production multi-user authentication. Use your own authorized backend credentials. Fresh installations default to AI disabled/Jev off; runtime databases, uploads, indexes, backups, `.env`, dependencies and generated local output are not published.

Existing profiles, selected homes, conversations, uploaded files and service data are not migrated or reset by this Git publication. Source snapshots do not establish current property availability. Generated drafts and service choices do not send emails, book services, sign leases or transfer funds.

Formal whole-team/member acceptance remains tracked separately; merging this final code version does not mark another member's trial task complete.

Jira: [SCRUM-34](https://breezebee64.atlassian.net/browse/SCRUM-34), [SCRUM-35](https://breezebee64.atlassian.net/browse/SCRUM-35), [SCRUM-41](https://breezebee64.atlassian.net/browse/SCRUM-41), [SCRUM-42](https://breezebee64.atlassian.net/browse/SCRUM-42). Team familiarisation: [SCRUM-44](https://breezebee64.atlassian.net/browse/SCRUM-44).
