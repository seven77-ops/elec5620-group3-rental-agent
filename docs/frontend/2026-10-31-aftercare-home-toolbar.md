# Aftercare home toolbar

The always-visible To-do items, Lease and living details and Home and contacts panels have been replaced by My home and In progress buttons beside Load latest information. Existing records and the underlying source APIs are retained.

My home shows six basic fields: address, suburb, postcode, agent/landlord name, email and phone. Saved location and contact groups remain authoritative, including intentionally blank fields. Without a saved location, selected real-listing facts are displayed as read-only references; confirmed lease/current draft facts supply a fallback. Draft contacts require the same displayed address. Source labels distinguish saved information, the selected property and the saved draft. Reading never saves a profile or confirms occupancy.

Edit details uses the existing confirmed, versioned, idempotent profile write. It merges the six visible fields into the retained full profile, preserving dates, furniture, notes and utility choices. A conflict reload preserves locally edited fields and refreshes untouched fields, including concurrent hidden-profile changes. Cancel editing makes no write.

In progress collects unresolved repairs and non-completed service records. Past bookings stay listed until explicitly completed. Missing contacts do not create a task. Opening an item closes the drawer and focuses its existing repair/service card. The Issue report form and History retain their simplified layout.

Current browser coverage replaces old home-editor/todo selectors and the full journey's historical lease-import and move-out planner steps. Historical tests for the removed planner and import UI are explicitly marked skipped; backend source, confirmation and preservation tests remain active. New home-toolbar tests cover read-only selection handoff, preservation, conflict recovery, desktop/mobile layouts and item navigation. The current issue reporting tests cover reporting, files and human advice.

Verification:

- Backend home/source/profile/continuity and product guide: 48 tests passed.
- Frontend unit checks: 71 passed. Production build, targeted Prettier checks and `git diff --check` passed.
- 23 distinct active browser scenarios passed across the broad run and targeted reruns. The broad run passed 20 and found two outdated test selectors/copy assertions; those were synchronised and both passed on rerun. Five historical tests for removed UI were explicitly skipped. This is not a claim of running every browser spec.
- A slow-provider regression first reproduced unsaved home edits disappearing, then passed after giving the drawer fragment a stable React key. The final targeted run passed this loading case, the four home-toolbar cases and four existing living-service cases; its remaining stale mail-preview assertion passed after copy synchronisation.
- The full journey passed from search and selection through contract draft/review, home editing, services, repairs, issue reporting and returned human advice.
- All browser verification used isolated fictional records and the local test AI double. No existing contracts or contacts were sent to external AI.

The live product-guide index was refreshed only for its 15 public product-guide chunks, with a backup and unchanged fingerprints for other public chunks, keywords and vectors. Local services were reloaded using their effective environment, preserving Jev active mode. All five database logical fingerprints remained unchanged across restart. Frontend, backend health and the existing case's read-only home endpoint returned HTTP 200; field contents were not logged.
