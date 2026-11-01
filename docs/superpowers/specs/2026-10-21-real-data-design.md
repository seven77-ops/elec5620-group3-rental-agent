# Agent 2 real data workbench

The user approved continuing the researched approach: government rent benchmarks first, with Domain rental search and TfNSW commute access where credentials are available. Implement locally in the existing `codex/local-ai-integration` checkout, retaining the existing modified AI verification document. No push, subscription, provider signup, or live model call is required.

## Scope and alternatives

Use a separate real-data workbench beside the existing synthetic journey. This delivers useful historical market comparison, explicitly entered real listing records, and credential-gated live queries without misrepresenting incomplete advertisements as evaluated properties. Replacing the complete synthetic journey now would require real evidence for lease windows, bills, availability and permitted downstream handoff; merely changing synthetic flags would invalidate the existing guarantees. An offline report alone would not provide the requested usable integration.

## Data and behavior

- Bundle a compact government benchmark snapshot for postcodes 2008, 2037, 2042 and 2050, flats/units, one or two bedrooms. Include independently calculated September 2026 statistics and official June-quarter 2026 statistics, source URLs, original file SHA256 values and exact periods. The loader runs offline and makes no network calls at startup. A source-derived artifact is produced deterministically by a build script; the original research workbooks remain in the parent project's data directory.
- Compare an explicitly entered base weekly rent with the same postcode and bedroom count. Return sample size, quartiles, median and deviation; label the result as historical reference, never a property valuation or a safety/affordability score. Reject unsupported room/per-person scopes from this whole-property comparison. Unknown or unsupported cohorts return no benchmark, not a fabricated value.
- Manual listing intake is case-bound, saved in existing SQLite, capped at 30 records, and records the submitted source URL, observation time, address/locality, stated weekly rent, scope, optional coordinates, bedrooms and bills status. Reject future observation times, invalid types/URLs/coordinates and unknown fields; retain stale records with an explicit freshness flag. Do not fetch arbitrary URLs or turn these records into eligible recommendations. Missing attributes remain null. Export saved snapshots as JSON and recover them after refresh.
- Domain search uses a fixed official HTTPS endpoint, API-key authentication, at most 20 rental advertisements and server-configured permission for this intended use. TfNSW uses fixed official endpoints and a server-side key, explicit origin/destination coordinates and a future Sydney arrival timestamp. Provider configuration is allowlisted in the existing `.env` loader. Public configuration exposes readiness booleans and documentation URLs, never keys. Each live query requires an explicit external-query checkbox and has no automatic retry or polling.
- Provider transport has a total timeout, streamed response size limit, strict JSON parsing, no redirects or environment proxy credentials, and redacted error codes. An unconfigured provider does not make HTTP requests. Tests inject HTTP transport only; the product has no fake-success mode.
- Route results preserve planned timestamps and request inputs; elapsed duration comes from the first planned departure to last planned arrival so waiting is included. Leg travel duration is separate. Missing timestamps do not yield a guessed total; empty journeys are a normal no-result response. No Opal fares are inferred.

## UI and boundaries

Add a lazy `真实数据` navigation page using the existing Ant Design forms, alerts and compact listing layout. Show postcode/bedroom/base-rent benchmark controls, preserved manual listing records, a bounded Domain query panel and a TfNSW coordinate/arrival form. Configuration and offline limitations are visible. An optional external map link opens the explicitly supplied coordinates; no map SDK, geocoder, billing account or background lookup is introduced.

The real workbench never invokes `evaluate`, changes synthetic evidence timestamps, sends listings to an LLM, creates a SelectedListingEvidence or starts a contract. The original Agent1–4 journey is retained. This phase is real data collection and market reference, not a claim of end-to-end real property ranking.

## Verification

Test source values and cohort mismatch, immutable inputs, missing values, manual import validation/persistence/case isolation, provider gates, exact outbound authentication and query parameters, timeout/size/redaction failures, waiting-inclusive route durations and malformed responses. Browser verification covers baseline query, scope mismatch, import/refresh/export, unconfigured provider states, and 360px layout. Run the original backend, Agent2 and handoff regression suites, API client tests and production build. Perform a fresh code-review subagent pass as required by requesting-code-review; fix material findings before completion.
