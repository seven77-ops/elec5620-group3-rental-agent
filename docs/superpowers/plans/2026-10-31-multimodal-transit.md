# Multimodal public transport implementation plan

**Goal:** Show real public transport itineraries instead of duplicated train/bus category cards, without averaging routes.

**Architecture:** Keep legacy mode identifiers for saved preferences. Expose bounded, validated transit_options alongside existing modes. Group primary public transport and road modes in the UI, with distinct actual itineraries, evidence-backed legs and a fastest valid reference. Existing data gains only deduplicated options already supported by its source slots. No external harvest or business-record rewrite.

**Tech stack:** Python API, React/TypeScript, Ant Design, unittest, Node tests and isolated Playwright.

- [x] Add backend journey deduplication and validation with legacy snapshot compatibility, actual options on future harvest/live planner and English umbrella-mode copy. Validate real durations/transfer ceilings, stale records and no fabricated evidence.
- [x] Add pure frontend itinerary presentation helpers and tests for mixed/single-mode routes, identical versus distinct routes, estimates, missing legs and legacy modes. Keep main selectors to four umbrella/road choices; retain clear legacy includes-mode labels.
- [x] Replace duplicate mode cards in property details with public transport itinerary cards, expandable supplied legs, total duration, transfers, evidence status and road references. Inspect responsive UI at 360px and desktop; ensure maps links and old saved selections work.
- [x] Run focused backend/frontend and affected browser journeys, build, review changes. Update product help/presentation examples. Back up local runtime, refresh only public help, reload preserving active Jev and user business rows.
