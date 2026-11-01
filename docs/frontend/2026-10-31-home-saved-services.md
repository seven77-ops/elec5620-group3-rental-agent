# Saved providers and services in My home

My home now brings together basic housing/contact information, saved electricity/gas/internet/water providers, and all saved moving/cleaning service records. Service entries retain status, date, quote and original notes, including completed records. Change utilities, Choose moving or cleaning and View record return to the existing editing pages without creating another data store.

The home endpoint adds bookings from the same read-only living record/version as profile.utilities. Merely viewing My home does not save anything. Basic home editing continues to preserve utility selections, bookings and hidden profile fields. Provider names come from the existing directory; unresolved provider metadata does not erase the saved record.

Utilities and Moving and cleaning both offer View in My home. Provider saves show a short success message. A service-company detail view offers Save to My home, followed by explicit confirmation, to create a Considering record without a date or quote. Existing provider records instead offer View in My home; the original Record quote or booking action remains available. No provider is contacted or booked by these saves.

Quick-save confirmation freezes its request ID, provider and expected version, so confirming again after a lost response returns the original receipt. A retained dialog handle is destroyed on component unmount or case change. Both boundaries were reproduced with failing browser regressions before the fixes and then passed.

Verification:

- 17 backend home/living-service tests and 8 product-guide tests passed.
- 71 frontend unit tests passed; production build, targeted Prettier checks and git diff --check passed.
- Final browser run: 14 passed, 1 explicitly historical planner test skipped. Coverage includes utility save/view, moving and cleaning quick choices, reload persistence, completed records and original notes, mobile layout, response-loss retry without duplicates, case switching without writes, previous home edit/conflict/loading behavior, repairs and utility concurrent changes.
- Browser verification used isolated fictional cases and the local test AI double. No real contracts or contacts were sent to external AI.
- The 15 public product-guide chunks were refreshed with a backup; other public chunks, keywords and vectors retained identical fingerprints.
- Live services were reloaded preserving their effective configuration, including Jev active mode. All five database logical fingerprints were unchanged across restart. Read-only live checks returned HTTP 200 for the frontend and home summary, including the previously saved four utility choices and one service record. User field contents were not logged.
