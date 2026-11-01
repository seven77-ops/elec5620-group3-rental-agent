# Real listing photos

User-approved: put actual advertisement photos in recommendation rows and property details; skip paid Google Maps. Initial sample then expand coverage where public original advertisements expose images.

Global constraints: preserve the 500 base listings and their existing fingerprint, original case data, saved reports and selections. No generated houses, unrelated images, guessed image paths, map integration, paid API or credentials. Accept only HTTPS images observed in the exact listing's property gallery, not agent logos, floorplans or related properties. Keep image source and observation time. Missing/failed photos degrade clearly. Existing blue/white UI and browsing/filtering behavior remain. No commits or publish.

## Task 1: backend and collection

- Add a validated `agent2/data/real/photos.json` sidecar keyed by known listing ID, source URL, observation timestamp, and image URLs. Runtime makes no external fetches.
- `RealCatalog.get/search` add `photos: [{url, source_url, captured_at}]`; missing sidecar yields an empty array. Metadata adds `photo_listing_count` and `photo_count`. Compute base fingerprint before media enrichment. Validate known ID, exact source URL, ISO timestamp, and explicit Domain CDN host.
- Collect publicly indexed original gallery URLs; bound collection and retain provenance in sidecar. Verify remote response status/content type without downloading files. Stop on access denial rather than bypass it. Coverage report must state actual count.
- Tests: missing sidecar, valid/invalid sources and URLs, unchanged fingerprint/filter results, deep copy isolation. Tests precede implementation.

## Task 2: frontend

- Add optional photo types to HousingAd/HousingCatalog. Small lazy thumbnail beside each property address, keyboard/click opens existing details. Details display a photo gallery with preview and source link. Actual image load failure and no images show a neutral “暂无照片” state. No remote placeholder photos.
- Show source attribution succinctly in detail. No map or key configuration. Responsive within current table and drawer; image URLs never treated as HTML.
- Meaningful browser checks for loaded image, preview, missing/broken image fallback, pagination, stable details when changing listing, and mobile overflow. Existing table column order preserved.

## Task 3: integration verification and review

- Backend relevant suites + frontend build/API tests, browser photo tests and Agent2/candidate flow regression in isolated runtime; actual network image load check.
- Read-only review against pre-change baseline in `/tmp/listing-photos-baseline`, fix important findings, document coverage/limitations.
- Restart main preview only after success, preserve original case records, leave main preview usable.

Progress: backend and frontend implemented; 335 listings / 1002 original gallery URLs, all verified HTTP 200 image content. Full backend 203 pass, related browser 13 pass, API 9 pass, build pass; actual Chrome image/preview decode and mobile screenshot verified. Base fingerprint and original case's 44 records unchanged. Review found no actionable defects. Main preview5191/8011 restarted; API returns335/1002 and exact basefingerprint; originalcase read-only browser check passed and44records unchanged. Temporary5195/8015 preview stopped. Complete.
