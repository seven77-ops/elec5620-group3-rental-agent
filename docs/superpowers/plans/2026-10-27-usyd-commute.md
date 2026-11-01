# USYD student housing and commute implementation plan

Goal: restrict the product to USYD students and annotate every public listing with a source-backed main-campus location/distance/commute record; make the requested duration an actual recommendation limit.

Architecture: a fixed, verified Camperdown/Darlington reference destination; resumable offline public-address and route harvesting; an immutable catalogue sidecar of all 500 annotation records. Online recommendation searches the full annotation inventory first and only refreshes a bounded set of public transport routes for the user's actual arrival time. Missing observations never become eligibility. Road routing estimates are labelled separately from scheduled public transport, with source, date, reference point and mode.

- [x] Verify official main-campus reference and API mode parameters. Use only public listing addresses for external queries; no paid Google API.
- [x] Add failing coverage for wrong campus, strict time ceiling, source/fingerprint validation, unknown modes, all-listing annotation coverage, and mode distinctions.
- [x] Build source-backed coordinates and resumable route snapshot for all listings. Use one-to-many/bounded matrix requests for road modes; never relabel a car route as pedestrian/cycling. Preserve unavailable records explicitly.
- [x] Enforce USYD-only chat policy and remove workplace/other-school intake. Retain user budget, room requirements, mode, arrival time and explicit limits.
- [x] Use stored observations to select promising houses across the entire catalogue, refresh actual requested public transport times where possible, exclude excessive/unknown durations from recommended homes and areas.
- [x] Display mode-specific annotated durations, distance, baseline time and provenance in listing details and recommendations. Keep unknown/over-limit alternatives collapsed and without save-as-recommended actions.
- [x] Test actual external records, deterministic backend and browser scenarios (USYD 20 min vs relaxed limit; different modes), build, read-only review, then restart the existing local website without changing saved user records.
