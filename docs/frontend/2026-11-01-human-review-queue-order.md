# Human review queue timezone ordering

The reported issue was already present in the live Human review API, open and linked to its uploaded attachment, but appeared third beneath two older contract cards. The screen therefore made a successful submission look missing.

Contract timestamps used the Sydney offset (`11:56:59+11:00`) while the later issue used UTC (`01:01:15+00:00`, or 12:01 Sydney time). OperatorInbox compared ISO strings directly. Lexical order put the older 11:56 contract before the newer 12:01 report.

The inbox now parses the timestamp and compares the actual instant. Open items still come before completed items. Original timestamps, reports, files, advice and case associations are retained; no data migration or duplicate submission is needed. The tenant report-history endpoint already used chronological parsing.

Verification:

- A new regression first failed for UTC offsets, Z and a UTC date-boundary case, then passed with actual-instant sorting. It also checks that reads preserve the original timestamps and saved case state.
- 30 related backend tests passed, covering the inbox, reports, files, retries, legacy reports and decisions.
- 6 browser scenarios passed. The new mixed-queue test creates an older contract, submits a newer issue with an image, checks that the issue is the first review card, saves advice and verifies that the user receives it in History.
- All writes used isolated fictional cases. The user's existing report was inspected read-only; no report, attachment or advice was changed.
