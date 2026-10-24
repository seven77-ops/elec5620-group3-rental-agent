# Agent1 integration into the existing rental workspace

The user approved merging PR6 and connecting the existing frontend to Agent1's confirmation, immutable versions, actual Agent2 search, and recommendation comparison. Preserve the approved React/Ant Design layout and existing downstream contracts.

New browser cases use `PreferenceAgent`, its persisted revision-bound review token, `HandoverService`, and `compare_current`. The editable form remains the input UI; example values and listings are synthetic and no live LLM is enabled. Model configuration, M3/M4 workflow changes, and production authentication are outside this change.

Agent1 Store owns sessions, immutable profiles and tasks. Place its tables in the adapter SQLite file and join the adapter transaction for case creation, draft updates and confirmation through a connection-scoped Store adapter; do not change member module code. Reserve evaluation task identity in an atomic adapter/core transaction; run the real LocalSupervisor only after committing that reservation so acceptance and results survive a lost HTTP reply. Reconcile retries with the same task ID. Before publishing an evaluation/comparison, verify the current confirmed version again. Old responses cannot publish as the newest result.

The adapter maintains its monotonic browser draft revision separately from Agent1's per-draft revision. Confirmation includes the displayed review token plus saved browser revision/fingerprint. Exact confirmation retries reuse the saved confirmation; altered/stale tokens fail. Store Agent1 IDs/provenance on cases, confirmations and evaluations. Original reports and comparison structures remain unchanged for downstream selection and history.

Legacy form-only cases retain read-only history/exports. Their preference/search and downstream selection mutations require starting a new Agent1-backed case; do not invent confirmations or rewrite old history during migration. Existing independently confirmed aftercare cases remain available.

Verification: existing 25 boundary tests plus new core-backed persistence, token, retries, rollback, concurrent confirmation, version comparison and late-response tests; all member suites; build; visible browser journey through edit/confirm/evaluate/reconfirm/compare and selection/contract, including refresh and a mobile-width check. Screenshots/logs remain runtime artifacts. Jira records actual results and remaining live-model/team acceptance boundaries.
