# USYD main-campus commute annotations

Updated 2026-10-28. The catalogue now has **1,000 real source-linked listings**. This expansion adds **300** across 28 suburbs: **215** in and around the main campus and **85** in commuter suburbs, including Burwood (20), Strathfield (12), Rhodes (12), Ashfield (9), Homebush (12), Mascot (6), Wolli Creek (9) and Wentworth Point (5). Existing 700 source records and their photos are unchanged. See `expansion-1000-20261028.json` for added IDs, observed facts, matched photos, positions, research links and fingerprints. The earlier 200-house expansion remains in `expansion-20261027.json`.

Each new listing has explicit advertised bedrooms, bathrooms, parking and weekly rent, one matching photo, and a validated building position. Conflicting card/detail facts, known leased/deposit-taken ads, duplicates and non-residential records were excluded. A parking dash means zero advertised spaces. Unknown billing scope, bills and lease terms remain unknown. Public snapshots do not certify current availability. All 1,000 have photos; the gallery contains 1,667 images in total. Of the new photos, 28 come from the exact same unit/address reference page and retain the actual photo-source link.

University accommodation guidance names Newtown, Redfern, Glebe, Annandale and Chippendale as nearby rental/shared-housing areas. This is area guidance, not a measured ranking of where most international students live. Farther suburbs were also included at the user's request.

All 1,000 have seven-mode annotation entries. **852** have source-backed building locations: 631 exact NSW Spatial Services points, 26 disclosed NSW building-range endpoints, 151 exact TfNSW building-address matches and 44 disclosed TfNSW building ranges. All new 300 have walking, cycling and driving observations; **299** have a checked reference-time public-transport option. One new listing returned no matching option in that sample; its other modes remain available. The original **148** unresolved houses retain null origins and use separately labelled coarse ranges.

| Mode | Located-house observations | Coarse ranges (separate field) |
| --- | ---: | ---: |
| Public transport, full journey | 849 | 148 |
| Journey containing train | 350 | 97 |
| Journey containing metro | 48 | 25 |
| Journey containing bus | 765 | 142 |
| Driving road estimate | 852 | 148 |
| Cycling road estimate | 852 | 148 |
| Walking road estimate | 852 | 148 |

Train/metro/bus entries are observed alternatives containing that mode, and may include other modes or walking. A null entry means the queried alternatives did not establish a duration, not that no such service can ever exist.

The single reference is the NSW official Fisher Library facility point, -33.88630396441765, 151.190498785334, within USYD Camperdown/Darlington main campus. It is a facility point, not a certified pedestrian entrance or a classroom. Camden and other universities/workplaces are outside the product scope. The reference agrees with the [university's main-campus description](https://www.sydney.edu.au/about-us/campuses/getting-to-campus.html).

## Files and sources

- `locations.json`: NSW Spatial Services address points and identity-checked TfNSW Stop Finder building points, original listing identity, source-feature URL, query time, catalogue fingerprint. Range endpoints are distinguished from exact building-address matches.
- `usyd-commutes.json`: every listing ID, source address, coordinate/precision or null, straight-line distance, all seven mode entries, individual observation times, reference arrival time, source links and coverage totals. Same-address units may share a building point; no unit entrance or floor access is implied.
- Official address layer: https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Geocoded_Addressing_Theme_multiCRS/MapServer/1
- Campus reference: https://portal.spatial.nsw.gov.au/server/rest/services/NSW_Features_of_Interest_Category_multiCRS/MapServer/3/query?objectIds=238482&outFields=*&outSR=4326&f=pjson
- Scheduled public transport: [Transport for NSW Trip Planner](https://opendata.transport.nsw.gov.au/dataset/trip-planner-apis), sample weekday arrival at 09:00 Sydney time. Elapsed duration includes walking, waiting and transfers. Numeric transport classes follow the official technical manual; metro is identified from explicit provider mode names.
- Road estimates: © OpenStreetMap contributors / FOSSGIS OSRM, separate `routed-car`, `routed-bike` and `routed-foot` backends, bounded many-to-one matrix queries. See https://routing.openstreetmap.de/about.html . Driving excludes real-time traffic, parking, cost and the walk after parking. No Google API is used.

The loader checks the inventory and campus fingerprints, every listing identity, mode keys, official address/range match and mode-specific source backend. Individual observations expire after 7 days for transit and 30 days for roads. A new file timestamp cannot renew an old observation. Route data is cleared when its origin changes.

## Current rental-discovery policy (2026-10-29)

Housing discovery uses the selected mode, duration ceiling and optional transfer ceiling. Historical arrival clock/day/date are ignored for housing search and selection; the dedicated transport tools retain their own schedule queries. Stored observations retain source-specific expiry (7 days transit, 30 days road); unknowns fail explicit ceilings and coarse estimates use their UPPER bound. Source-backed estimates are not live verified journeys.

All compatible matches are available. Cards and details show selected-mode minutes or an estimated range, not a cross-mode average. Changes to working criteria recalculate local results only after explicit application; saved requirements/selection retain their own confirmation and version checks. Personal/per-room budgets do not become whole-ad rent caps. One explicit follow-up confirmation atomically saves supplied needs and selects the current preview listing; previews and cancellation do not save. Catalog/requirement/ownership conflicts still reject stale operations. Public advertisements do not certify availability, comparable costs or a signed tenancy.

## Rebuild

Only public listing addresses are sent. Keys stay in local `.env`; no private tenant/landlord service addresses are used.

```sh
.venv/bin/python tools/build_usyd_commutes.py
```

The collector resumes current observations, refreshes expired records, limits external queries and saves atomic checkpoints. `--reuse-locations` skips further geocoding. Public-road requests are sequential with at least 1.1 seconds between matrix calls. No periodic geocoding job or paid API is configured. Unknown and malformed observations remain unavailable.

## Coarse estimation method

This fallback was explicitly requested by the user. It never invents house coordinates or trip legs. Missing-origin houses first use current routes from the same street and suburb, then the same suburb, then the same postcode. A building point counts once even if several units share it. Transit donors use a consistent reference clock/day. Each mode records donor listing IDs, source URLs, sample count, observation time, evidence fingerprint, typical value and lower/upper range in `estimates`; exact `modes` remain unavailable.

Ranges cover the donor minimum/maximum plus a location margin. Street margins: walk 5, bike 4, drive 5, transit 8 minutes. Suburb: 15/8/10/12. Postcode: 20/12/15/18. Single-donor suburb/postcode estimates add another 5 minutes. Lower bounds are at least 1 minute. These are practical discovery intervals, not statistical confidence intervals or guaranteed maxima. 59 missing-origin homes use street samples and 89 use suburb samples (walking coverage after adding the new anchors). No donor means no estimate for that mode.

Expiry uses the oldest underlying observation, not a new file timestamp. The loader regenerates ranges from validated source records; stored estimates cannot override missing or expired donors. The collector persists these annotations for inspection. Formal report evidence hashes include the ranges; old reports and changed evidence cannot silently authorize a new selection.

## Same-day building refinement and UI update

The user requested narrower, house-specific times and a simpler result UI. `tools/refine_usyd_locations.py` uses the existing TfNSW key to look up unresolved public house addresses through Stop Finder. Only `singlehouse` candidates with matching street, suburb, postcode, finite high match quality and exact house number/range identity are accepted. A single advertised number at an official range endpoint is allowed and labelled as a range. Locality/stop/street results and ambiguous conflicting coordinates remain unresolved. Source labels, raw source IDs, coordinates, query URL without headers, query time and original listing identity are retained and revalidated by the loader.

This added 106 building points, reducing coarse-only houses from 254 to 148. Existing route observations were refreshed only for changed origins. Identical range labels still carry range precision. UI cards retain only compact facts and useful actions; source links are inside house details. Historic null-origin details can fetch newly recovered coordinates while preserving valid recent personalised trips by mode. Details offer per-mode outbound Google Maps URLs, with the validated house coordinates (or its full address when unlocated) as origin and Fisher Library as destination. These URLs do not call Google APIs or require a Google key ([official Maps URLs documentation](https://developers.google.com/maps/documentation/urls/get-started)). In-app durations remain TfNSW schedules or the mode-specific free road router, not Google durations.

## 2026-10-28 expansion verification

The expansion, photo loader, real catalogue, commute snapshot and historical expansion audits pass 38 backend tests. Sixteen browser regressions pass for pagination, filters, photo preview/fallback, old-chat hydration, mobile layout and commute limits. The TypeScript/Vite build passes. All 1,000 published first-image URLs returned HTTP 200 with an image content type. Added Burwood, Strathfield and Rhodes houses were also opened against the actual 5191 preview; their images and commute panels rendered on desktop and mobile. The screenshot's historical Westmoreland chat now loads its photo. Read-only hashes of both user databases match before and after the preview restart.

A broader concurrent-development run found an unrelated assertion still expecting the old 100-card reference rejection; this is outside the data expansion checks above. A transient SQLite lock in that run passed on isolated retry. No claim that the full concurrently edited suite is green is made here.
