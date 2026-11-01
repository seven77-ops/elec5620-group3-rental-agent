# Saved providers and services in My home

**Goal:** Complete the existing choose/save/view flow by displaying saved utility providers and moving/cleaning records in My home.

**Architecture:** Read the existing profile.utilities and bookings from the same versioned home summary. Resolve names from the existing provider directory without duplicating records or inventing confirmed bookings. Keep basic home editing independent of provider loading. Add a confirmed quick save in service-company details that reuses the existing bookings endpoint and idempotent write flow. Existing records remain visible, including completed records.

**Constraints:** English UI; preserve user data and full profiles; explicit confirmation and version checks; no external booking or AI request. No Git publication. Use existing Ant Design components and synthetic isolated tests.

- [x] Add failing read-only summary and browser tests for utility save/view, quick service choice, reload persistence, original service records and mobile access.
- [x] Include bookings in the read-only home response. Add compact Utilities and Moving and cleaning sections in My home, with change/view-record navigation.
- [x] Add Save to My home in service details, confirming a local considering record; avoid a duplicate quick-save when that provider already has a record. Add saved-choice viewing links and success feedback to both service screens.
- [x] Verify conflict/loading preservation, relevant backend tests, browser flows, frontend units/build/format; update guide/canonical snapshot/index and reload live service preserving environment/databases.
