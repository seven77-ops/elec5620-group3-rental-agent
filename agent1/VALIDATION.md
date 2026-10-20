# Validation record - Agent1 1.2.0

Date: 2026-10-19 (Australia/Sydney). Execution environment: Linux, Python 3.12.

The full Agent1 suite passes: 52 tests. See verification/v1.2-tests.txt. The runnable --acceptance-demo also passes all 14 named checks; its actual output is in verification/v1.2-acceptance.json. Yirui subsequently reported that all 14 scripted acceptance checks passed on Windows (see [PR #6](https://github.com/seven77-ops/elec5620-group3-rental-agent/pull/6) and the member update relayed for this review). This is member-reported Windows evidence, not an independent Windows run by the reviewer.

The release fixes offline pasted text changing confirmed session state, adds explicit recovery for compatible legacy ProcessingError sessions, and integrates Agent2's existing compare_reports with verified stored versions and snapshot checks. It adds English comparison output, raw comparison export, current/historical labels and recommendation run-ID validation.

New tests cover preserved confirmations/review tokens after offline text; legacy recovery without discarding revisions; all-candidate comparison; budget-priority Top1 DEMO-012 and DEMO-002 rank 9 to 3; tightened-budget exclusion; missing-route pending status; cross-search/snapshot/time errors; wrong run IDs; report tampering; and a delayed old response arriving after a new version completes. Tests preserve unknown scores/ranks as null and retain original stored reports.

The automatic acceptance scenario uses real local Agent2 code and synthetic data. It is scripted and does not call an LLM. Existing tests simulate GBK-default file reads. Agent1-authored source and documentation remain English, with explicit UTF-8 text file reads/writes. Upstream raw reports and comparison reasons are preserved and may contain Chinese.

For the original Agent1 implementation upload, a SHA-256 comparison recorded 287 unchanged non-Agent1 files (excluding Git internals and Python bytecode), and only Agent1 was included in that update archive. The subsequent documentation/evidence follow-up also updates integration documentation; the original checksum statement does not describe those later documentation changes. No user database, credentials, reports or virtual environment is included.

Remaining external verification: preserve the member's Windows command/environment/output alongside the reported result; actual member-attended joint testing with Anda; actual Sprint Review and team feedback. Live LLM quality, cross-machine delivery, authentication and the complete four-agent workflow are not established by these local results. Old-version preservation is covered by the test suite; a single exported version alone cannot prove all history is intact.

## Independent follow-up review - 2026-10-20

Reviewed implementation: commit `75ece8f6ca5a5c49607726983cd2d9ba8a6afb31` in PR #6. The follow-up changes documentation and reproducible review evidence only; it does not change application logic or merge the PR.

The reviewer independently ran the following on macOS using the local Python interpreter:

| Check | Command (from repository root unless noted) | Result |
|---|---|---|
| Agent1 suite | `python3 -m unittest discover -s agent1/tests -v` | 52 passed |
| Scripted acceptance | `python3 agent1/main.py --db <temporary-db> --acceptance-demo` | 14 named checks passed |
| Agent2 regression | From `agent2/`: `python3 -m unittest discover -s tests -v` | 71 passed |
| Existing integration suite | `python3 -m unittest discover -s integration/tests -v` | 6 passed |
| Actual Agent1 -> Agent2 -> Agent3 local chain | `python3 integration/reports/2026-10-20/verify_agent123.py` | 9 checks passed |

The chain starts with the Agent1 implementation's saved, explicitly confirmed synthetic profile, rather than importing the old fixed handoff profile. It checks the unconfirmed-search gate, actual Agent2 evaluation and retry reuse, profile export, a newly generated selection packet, Agent3 intake/reference binding, repeat intake and separate contract-processing consent. It returns DEMO-006, profile version 1 and `Reviewed`; the repeated intake returns the same review. The 30 input records divide into 15 eligible, 9 pending, 5 excluded and 1 duplicate.

The confirmation, selected property and consent in this scenario are scripted test actions. The selected-at timestamp remains the dataset's fixed synthetic time (`2026-09-17T10:00:00+10:00`), and contract rules use `2026-10-15`. The execution date of 2026-10-20 does not imply refreshed real listings. `Reviewed` is a prototype workflow status, not approval to sign a lease.

Raw logs, environment details, the executable chain check and structured results are stored in [integration/reports/2026-10-20](../integration/reports/2026-10-20). All test data is synthetic; no live LLM request, member-attended joint session, unified-frontend acceptance, cross-machine delivery or complete four-agent acceptance is claimed.
