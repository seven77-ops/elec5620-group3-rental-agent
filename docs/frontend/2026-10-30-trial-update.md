# Team trial publication — 30 October 2026

Use branch **`codex/group-trial-20261022`**, tracked by **draft PR #7**. This publication includes the previously local-only RAG, contract/chat and Agent4 integration, plus the English product release and its follow-up output guards. It does not merge `main`.

## Install and configure

Use a fresh clone as shown in the [root README](../../README.md). For an existing clean trial checkout, confirm the branch and run `git fetch origin` followed by `git pull --ff-only`. Do not reset someone else's uncommitted work.

Windows PowerShell, after cloning and entering the repository:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r server/requirements-lock.txt
cd frontend
npm ci
cd ..
.\.venv\Scripts\python.exe scripts/dev.py
```

Open `http://127.0.0.1:5173`; optional ports are `--web-port 5197 --api-port 8017`. The actual publication verification ran on macOS, not a Windows device. Optional automatic MCP startup remains POSIX-specific; see its historical handoff for the direct fallback.

Copy `.env.example` to `.env` and configure your own backend credentials only if testing external AI or transport. New installations default to `RENTAL_AI_ENABLED=0` and `RENTAL_JEV_MODE=off`. A developer's configured localhost is not a shared hosted service. Do not send keys in the group or commit them.

The server lockfile includes the pinned offline language detector `lingua-language-detector==2.2.0`; reinstall dependencies after pulling. It adds no model request. Public keyword search seeds a new local index from the public corpus. External embeddings/reranking require matching endpoint/model configuration and an explicit `scripts/rag_index.py --embed` build. No private index, business database, upload or prebuilt cloud vector database is distributed in this release.

## Changes to exercise

- English navigation, forms, statuses, validation, authored assistant responses, contract guidance, repair drafts and retrieval summaries. Original source facts, names, messages and quotations are retained. Multilingual input remains valid; English authored output is checked, including unsupported cardinal-budget guesses and foreign-language prose. Short/name ambiguities remain a detector limitation, not proof that every string is English.
- Public knowledge: 14 documents / 153 chunks, local keyword search and optional vector/RRF/rerank, distinct NSW, official-template, university and product-help sources. Source and paragraph IDs, values, dates and qualifications are checked. Public summaries are source-isolated and receive a separate model source review; fallback keeps readable evidence and an explicit retry. This does not replace human source-support assessment.
- Private contracts: standalone TXT/DOCX/PDF intake after explicit document consent; basic review and original evidence inside chat. Private local search and external processing are separately granted, bound to case/review/file versions and revocable. Page/line citations and protected original access remain scoped. Upload without selection does not fabricate a selected home or advertisement comparison.
- Chat repairs: complete subject/body preview, rewrite and copy before saving. An explicit save persists the exact preview; rewrite reuses the same issue and original property snapshot. Failure keeps the request; no actual email delivery.
- Contract extraction: separate timeout, precise error category, source/role checks per field, manual completion for rejected fields and explicit review before filling. No automatic signature or draft save.
- Sourced lifestyle ordering retains every hard match. Evidence coverage is not a desirability score; quietness, safety and property distance remain unestablished. Work-condition edits, favorites and one-confirmation selection remain intact.
- Optional Jev routing: state/continuation first, six domains, configurable off/shadow/active modes and uncertainty/failure fallback. Classification cannot bypass consent, versioning or human review.
- Agent4 member enhancements integrated with source prefill, multiple claims, controlled AI facts/drafts, reminders and readable tasks. Anda's additions include the cross-case operator inbox, persistent decision history and progress. Operator release unlocks draft preparation; it is not a refund or deduction decision.
- The separate agent-reply entry form is removed. Inspection questions/download remain read-only, contract facts are entered in contract assistance and historical records are retained.

The inventory remains 1,000 advertisements / 72 areas. Copy translation is not new housing acquisition, live availability verification, new route collection or new supplier-price research. See the English catalogue audit and earlier data provenance.

## Team testing

Use the [manual questions](english-manual-test-questions.md), especially H01, R01–R03, C01–C04 and M01, with synthetic information and the sample contract. Record case ID, steps, expected/actual result and a screenshot when something fails. Do not upload personal documents simply to test.

Test requirements → all results/edits → favorites or direct selection → inspection/contract → contract questions → aftercare → human review. The optional [15-step automation](2026-10-28-full-journey-test.md) is provided for reproducibility. This publication's actual checks are listed below; files containing previous browser/model test records are not evidence that those checks ran again now.

Send trial feedback to Anda in the group. Please do not directly edit the shared trial branch or merge `main`; keep module work in your own branches. Anda will coordinate integration fixes. We have not sent the group notification automatically.

## Evaluation boundaries

Existing implementation reports retain their original code stage and hashes. On the expanded corpus, the saved 80-question hybrid/rerank report retrieved 72/72 annotated targets; keyword-only retrieved 67/72. The 26-question real generation report passed 25/26 mechanical checks; rescoring unchanged outputs with a count-noun/period correction gave 26/26 without new provider requests. An earlier 49-chunk generation run passed 76/80, with four requested-language failures. Those scores are not relabeled as current-code legal accuracy, and independent human semantic review remains pending.

Cross-device and full-team acceptance, refreshed sources/prices, current availability and formal Agent3→Agent4 coordination remain separate work. Nothing here sends emails, books services, signs contracts or handles bond funds.

## Actual publication verification

Checks ran against an isolated publication copy on macOS, Python 3.13 and Node 22.23.1. Business cases and credentials were not copied from the developer runtime.

| Check | Actual result |
| --- | --- |
| Final server suite after review fix | 707/707, 384.699 seconds |
| Agent1 / Agent2 / Agent3 / Agent4 | 52 / 91 / 40 / 62, all passed |
| Module integration | 6/6 |
| Frontend unit/API tests | 44/44 |
| TypeScript + Vite production build | Passed; existing large-chunk advisory |
| Repair/language focused regression | 27/27, overlapping the full suite |
| Isolated browser | English repair preview → explicit save → reload; exact subject/body persisted as prepared_not_sent; 97 housing matches → single confirmation → selected home survives reload |

Total: 958 backend/module/integration checks and 44 frontend checks. The complete automatic browser suite, Windows and real external AI/transport were not rerun for this publication. Browser observations used deterministic injected model transport and the real bundled catalogue.

The independent reviewer found a supplied non-Latin building/name rejected by the repair-language guard. Two API regressions first failed with 502; the minimal fix preserves validated locations and explicitly introduced Unicode names, while rejecting an invented name. The reviewer confirmed resolution with no new P1/P2 finding. The earlier pre-fix server baseline passed 705 tests; it is retained separately and is not the final result.

Source fixes were copied back only after confirming source fingerprints, preserving other checkout work. No unrelated source drift was observed. Historical evaluation reports retain original input-path metadata to preserve report hashes and replay chains. Credentials, user databases/uploads, dependencies and generated local test output are excluded. Logs, hashes and review details are retained in the task's publication evidence folder.

- [PR #7](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/7)
- [SCRUM-34](https://breezebee64.atlassian.net/browse/SCRUM-34)
- [SCRUM-35](https://breezebee64.atlassian.net/browse/SCRUM-35)
