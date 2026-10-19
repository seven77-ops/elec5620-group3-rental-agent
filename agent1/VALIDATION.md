# Validation record - Agent1 1.2.0

Date: 2026-10-19 (Australia/Sydney). Execution environment: Linux, Python 3.12.

The full Agent1 suite passes: 52 tests. See verification/v1.2-tests.txt. The runnable --acceptance-demo also passes all 14 named checks; its actual output is in verification/v1.2-acceptance.json. This release has not yet been run on the user's Windows computer.

The release fixes offline pasted text changing confirmed session state, adds explicit recovery for compatible legacy ProcessingError sessions, and integrates Agent2's existing compare_reports with verified stored versions and snapshot checks. It adds English comparison output, raw comparison export, current/historical labels and recommendation run-ID validation.

New tests cover preserved confirmations/review tokens after offline text; legacy recovery without discarding revisions; all-candidate comparison; budget-priority Top1 DEMO-012 and DEMO-002 rank 9 to 3; tightened-budget exclusion; missing-route pending status; cross-search/snapshot/time errors; wrong run IDs; report tampering; and a delayed old response arriving after a new version completes. Tests preserve unknown scores/ranks as null and retain original stored reports.

The automatic acceptance scenario uses real local Agent2 code and synthetic data. It is scripted and does not call an LLM. Existing tests simulate GBK-default file reads. Agent1-authored source and documentation remain English, with explicit UTF-8 text file reads/writes. Upstream raw reports and comparison reasons are preserved and may contain Chinese.

A SHA-256 comparison confirms that all 287 recorded non-Agent1 files remain unchanged (excluding Git internals and Python bytecode). Only Agent1 is included in the update archive. No user database, credentials, reports or virtual environment is included.

Remaining external verification: user-side Windows execution of this release; actual joint testing with Anda; actual Sprint Review and team feedback. Live LLM quality, cross-machine delivery, authentication and the complete four-agent workflow are not established by these local results. Old-version preservation is covered by the test suite; a single exported version alone cannot prove all history is intact.
