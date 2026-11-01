# Assistant workspace synchronization

Goal: make conversation requirements, Agent1 confirmed preferences, Agent2 reports and a selected real property visibly connected. Keep white/#174EA6 and existing transaction and confirmation boundaries. Work in the existing dirty checkout; no commits or dependency changes.

Design: a persistent “我的租房需求” entry opens a compact editable drawer in chat, with explicit pending/saved status. The full manual preferences route remains accessible for advanced fields. Sidebar placement follows the user's preference; default is to consolidate the independent preferences entry into chat. A prepared proposal exposes every inherited profile condition, followed by an explicit confirmation that atomically saves Agent1 and generates Agent2. A chat card can explicitly save the current candidate only against current confirmed profile filters; a preview never silently relaxes them.

API additions, using /api/v1/cases/{case_id}/assistant/conversations/{conversation_id}:
- POST /proposals: {request_id,expected_revision,expected_profile_fingerprint,brief}. Validate a complete BRIEF_SCHEMA, build a full profile from the current draft, persist a revision-bound proposal and return {proposal_id,summary,conversation}. No model call or profile mutation. Repeated identical requests return the same result.
- POST /selections: {request_id,expected_revision,expected_profile_fingerprint,listing_id,confirmed:true}. Require a displayed catalogue ID, current confirmation and matching fingerprint. Compose default real evaluation and real candidate selection in a single transaction; append a confirmation with a link to recommendations, return {case,conversation}. Reject out-of-profile, stale, cross-case or unknown cards; rollback failures.

- [x] Add failing backend tests for preparation/application and read-after-save page linkage, stale/ownership validation, explicit candidate selection and rollback.
- [x] Implement bounded workspace operations using the existing Agent1/Agent2 adapters and durable receipts.
- [x] Add typed client APIs, an editable needs drawer/status strip, card selection confirmation and chosen-candidate feedback. Keep inherited advanced conditions visible in confirmation.
- [x] Adjust sidebar/entry points, and verify browser sync from chat to report, refresh persistence, manual editing, cancellation and mobile.
- [x] Run scoped and regression tests/build; restart original runtime and read-only verify original data preservation.
