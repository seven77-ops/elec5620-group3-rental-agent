# Team trial — 31 October 2026

Publish these changes to **`codex/group-trial-20261022` / draft PR #7**, with `main` unchanged. The update is organised into three functional commits, all created on the actual publication date. They are code-review boundaries, not separate deployments or repeated claims of the same work.

1. **Backend commute rules and evidence:** optional include/skip intake, saved-filter removal only after confirmation, legacy mode compatibility, distinct actual transit options and mode/transfer-qualified selection.
2. **Housing and contact interface:** complete card layout, shared selected-property header, four umbrella travel choices, compact commute references, and local Contact property agent enquiry preparation.
3. **Tenant-facing contract and knowledge flow:** readable review/results/history with retained sources and permissions, public knowledge through main chat, private contract search retained, shared canonical help and release instructions.

## Current behaviour

- Commute filtering is optional. Existing saved requirements remain until explicitly removed. A working opt-out survives reload and budget changes; saving/removing confirmed requirements still requires confirmation. Known-area searches can proceed without a commute constraint.
- Public transport means one real itinerary, which may contain one mode or a supported combination. Legacy train/metro/bus filters mean includes that mode. Distinct routes with different services/stops remain separate even when durations match. API alternatives are bounded, source-derived and do not invent transfers or legs for estimates.
- Final property details use a compact travel-mode grid and maps/source links, without large itinerary, route-detail or weight-control panels. Earlier documents describe intermediate expanded views and an equal average; those are historical stages, not additional current features.
- The catalogue's combined commute reference is display-only, using product-defined weights that favour public transport/driving and reduce long active journeys. Missing modes are excluded and ranges remain ranges. Hard filtering still uses the selected mode, its actual/reference duration and any transfer limit. It never uses the combined reference to satisfy a user's ceiling.
- Contact property agent appears with the selected home. The original HTTP(S) listing is where the user contacts/registers. Prepare enquiry creates an editable local English template; copy and an explicitly supplied single-recipient mailto open the user's tools. There is no booking, saved contact record, AI request or automatic email send. Closing/reopening retains the mounted draft; changing case/property or leaving the page resets it.
- The chat criteria area also shows the selected address/contact action. Contract drafting/review remains in the sidebar; compact chat lease shortcuts are removed. Existing selection, favorites and version checks are retained.
- Contract review leads with the saved document, items to check and essential facts. Evidence remains reachable, corrections remain versioned and optional AI suggestions still require explicit selection/confirmation. User-facing JSON/raw diagnostics are hidden on these surfaces; backend validation, processing withdrawal, private-search/cloud consent and human-review restrictions remain intact.
- General rental and product-help questions use main chat and its citations. The redundant public knowledge modal is removed. Private contract questions remain a separate document-scoped panel. Product-help snapshots are synchronised with the current controls; no other public source text or private business record is changed by that help update.

The inventory and original transport snapshots are unchanged: this is no new housing acquisition, route harvest, live availability verification or supplier-price research. References may expire and require explicit refresh. Existing reports and transcripts keep their original source versions.

## Publication review

A new regression reproduced a TypeError when a successful explicit scheduled lookup received the catalogue's normal `usyd_commute: null` shape after a missing/expired snapshot. The fix builds a fresh annotation with current destination/origin/source time, routes and note, while preserving the catalogue and existing annotation timestamps. The test uses a mocked provider/resolver, not an external route request. Actual verification results are appended below.

## Install and try

Use the [root README](../../README.md) and [30 October setup](2026-10-30-trial-update.md). Protect your uncommitted module work before pulling. New installations still default to AI disabled and Jev off; supply your own backend configuration. Credentials, databases, private indexes, uploaded contracts and dependencies are not distributed.

Run through requirements → optional commute choice or known-area search → results/details → favorites or selection → Contact property agent → sidebar contract draft/upload/review → private questions → aftercare. Use [manual prompts](english-manual-test-questions.md) and synthetic information. Please send steps, expected/actual results and screenshots to Anda in the group; let Anda coordinate integration fixes and keep your module work on separate branches. Do not merge `main` yet.

Historical feature documents contain implementation-stage tests. They are not automatically new publication results. This publication does not claim full automated browser, real-provider, Windows, cross-device or whole-team acceptance unless explicitly recorded below. Formal M3→M4 coordination and independent human assessment of generated source support remain outstanding.

## Actual publication verification

All checks below ran on the final combined publication tree in an isolated macOS/Python 3.13/Node 22 environment; the three commits are not three independent full test runs.

| Check | Actual result |
| --- | --- |
| Server after null-snapshot fix | 745/745, 452.985 seconds |
| Agent1 / Agent2 / Agent3 / Agent4 | 52 / 91 / 40 / 62, all passed |
| Module integration | 6/6 |
| Frontend unit/API tests | 66/66 |
| TypeScript + Vite build | Passed, existing large-chunk advisory |
| Focused commute tests | 40/40, overlapping server suite |
| Browser observations | Selected-property/contact header; original listing link; local editable enquiry; synthetic date-conflict review and original-source action |

That is 996 backend/module/integration checks and 66 frontend checks, counted once. Browser checks used disposable cases, the bundled real catalogue and injected deterministic model transport. They made no external model/route call and did not send an enquiry. The complete automatic browser suite, Windows and real provider calls were not rerun here.

The independent review confirmed the null-annotation fix with no remaining P1/P2 finding. The new test first reproduced the TypeError; its post-fix expected origin includes the original-address/suburb provenance added by the existing resolver. No business restriction was loosened to make it pass.

Credentials, runtime cases, uploaded documents, dependencies and generated local outputs are excluded. Original development work was not reset. Source fixes/documentation are synchronized only when original fingerprints match. Logs, hashes and exact file-to-commit assignments remain in the task's publication evidence.

- [PR #7](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/7)
- [SCRUM-34](https://breezebee64.atlassian.net/browse/SCRUM-34)
- [SCRUM-35](https://breezebee64.atlassian.net/browse/SCRUM-35)
