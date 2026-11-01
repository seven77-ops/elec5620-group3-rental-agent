> Historical implementation-stage record. The final compact UI no longer exposes the large itinerary/route-detail panels described below; source-backed alternatives remain in the API. See [current trial handoff](2026-10-31-trial-update.md).

# Public transport itineraries — 31 October 2026

The user approved a single public-transport entry that accepts a single transit mode or a combination, with individual routes instead of repeated category cards and without averaging unlike journeys.

## User behaviour

New travel choices are Public transport (any combination), Driving, Cycling and Walking. Existing saved train, metro and bus values remain compatible and are labelled Includes train/metro/bus. Public transport can include train, metro, bus, light rail, ferry and walking connections, only where the recorded route supports them.

Property details show distinct public transport itineraries, one total duration for each and recorded transfer counts. Supplied segments, service names and stop information appear under View journey details. Unspecified connections remain unspecified. The selected reference respects the requested mode and transfer limit; other routes are alternatives and may differ from the chosen limits. A recent personal query retains its own context. Estimates show ranges without fabricated route segments or transfer counts.

The API exposes at most six distinct planned transit_options alongside existing mode slots and a mode-bound selected_transit_route when a search chooses one. Existing source snapshots are read without rewrite; distinct options are recovered from their actual category observations. Future explicit route harvests retain available distinct provider journeys. Same-minute routes with different services or source stop identities stay separate. Current catalogue filtered results and chat discovery both carry the matching selected route.

## Verification

- 61 frontend unit tests passed, including identity, explicit filtered selection, personal query context, coordinate-refresh preservation, four travel choices and estimate boundaries. Production build passed.
- 100 related backend tests passed; the final focused multimodal module contains 14 passing tests. Compilation passed. All 2,012 existing planned category observations remained valid, including unspecified connection legs.
- Sixteen browser scenarios passed in the final grouped run. The historical estimate-only fixture was updated to clear the new actual-itinerary fields, then its complete scenario passed separately. Seventeen unique browser scenarios were verified, including mobile/desktop detail panels, transfer-qualified selection, existing filters, historical photo/route refresh and range-only fallback.
- Read-only review found and resolved route-identity and direct filtered-catalogue selection issues. The follow-up review found no remaining material blocker.
- The seven public product-help tests passed after the guide and canonical manifest were synchronized. Presentation examples describe expandable itineraries.

## Local release

The app was backed up and restarted on frontend 5191 / API 8011, with health ok and Jev active. Logical business records in web.sqlite3, intake.sqlite3 and aftercare.sqlite3 were unchanged. Only the public product-guide index was refreshed; other knowledge chunks and vectors were retained. Metadata and backup path are in .runtime/multimodal-reload.json.

A read-only live API check verified three real public catalogue records with a zero-transfer filter: each selected route respected the filter and the reported duration, and alternatives were bounded and distinct. No provider harvest or new external route query ran during development. Existing stored transcripts and source snapshots were not rewritten; opening historical details derives supported itinerary options from the route evidence already present.
