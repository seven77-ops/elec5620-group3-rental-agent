# Lease address and calendar-term implementation plan

**Goal:** Search existing real NSW addresses/localities, fill structured PDF address boxes, choose a calendar lease length and calculate dates, expose common extra PDF fields in the web form.

**Architecture:** Local catalogue search (no external API), optional backward-compatible fields in the existing draft schema, shared calendar-month arithmetic and explicit term validation, existing versioned/confirmed draft and AcroForm generation.

**Global constraints:** No paid service/map, fabricated address, postcode guessing from unit numbers, silent rewriting of saved versions or original case. Keep all prior source data/fingerprints, draft confirmation/AI consent, unsigned signatures and official terms. Structured metadata is filled only after an explicit choice or manual input. Calendar term means same date after N calendar months (target month-end clamp); this matches the current PDF date convention. Custom dates remain an explicit option. Switching periodic clears end and preset. Legacy drafts/old payloads remain readable and downloadable.

## Task 1: backend and PDF

- New optional strings (default empty): `suburb,state,postcode`; `landlord_notice_suburb,landlord_notice_state,landlord_notice_postcode`; tenant and agent same prefixes; `agreement_place,landlord_name_2,landlord_residence,landlord_phone`; `electrical_repair_name,electrical_repair_phone,plumbing_repair_name,plumbing_repair_phone,other_repair_name,other_repair_phone`.
- New optional date `agreement_date` (default null). Optional `lease_term_months` integer 6,12,24,36,60 or null (custom). Old fields remain required in payload, new fields optional. Normalize missing new fields to defaults for validation only; don't mutate saved versions.
- `add_months(start,months)` clamp calendar end; preset/start computes absent end, rejects contradictory supplied end; changing to periodic forbids/clears preset and end. Custom fixed dates validate end > start and render natural months if exact, otherwise explicit days (no invented standard term).
- Preserve AI grounding; explicit numeric/Chinese calendar durations can ground lease_term_months. AI start/preset patches calculate derived end; explicit end date without duration switches custom; periodic clears preset/end. Keep confirmation unchanged.
- `GET /api/v1/lease-addresses?q=...` bounded 10 suggestions from existing 500 addresses + suburb/postcode pairs. Response `{items:[{id,kind:'address'|'locality',address,full_address,suburb,state,postcode,source_url?}],source:'local_catalog'}`. Address is street portion without trailing suburb; locality address is empty; never invent a street. Case-insensitive full/street/suburb/postcode search; min2chars, max120; blank yields empty. NSW source scope explicit.
- PDF text mapping: landlord suburb/state/postcode Text field1.12/1.13/1.14; tenant2.11/2.12/2.13; agent2.17/2.18/2.19. Agreement date1.1/place1.2; landlord_name_2=1.5; landlord_residence=1.7; landlord_phone=1.8; emergency names/phones4.5..4.10. Property address3.11 appends chosen locality/state/postcode only when absent. Known calendar preset ticks matching official checkbox, no `480 days`; month-end works. Existing values/missing new fields use get to keep old PDF generation supported.
- Tests first: address source identity/no external I/O, all structured PDF canonical + widget values, calendar monthend/leap, contradiction, periodic/custom/legacy, AI patch and persistence/idempotency. Backend worker owns server only, no frontend/data/runtime mutations.

## Task 2: frontend

- Add optional types/default handling; per-address AutoComplete component with debounced read-only search, stale-response guard, manual entry, locality/State/postcode fields. Explicit select fills all, later typing clears stale metadata. Locality-only selection fills metadata and prompts street entry; no fabricated building/unit. Existing filled freeform addresses remain untouched unless edited.
- Calendar lease selector:6个月、1年、2年、3年、5年、自定义日期; start changes calculate disabled end; explicit custom restores editable end; periodic clears both. Calendar math mirrors backend. Include natural month-end helper, avoid implicit business write. Apply AI patches and version load consistently.
- Expose signing date/place, secondary landlord/residence/phone and optional urgent-repair contact fields. Map all to confirmation summary and saved PDF; blank remains blank. Keep extra fields collapsed.
- Browser scenarios with real local Redfern/Burwood suggestions -> PDFs include all suburb/state/postcode fields; start/preset changes/endmonth/periodic/custom; saved reload; old version and no-match manual entry; mobile layout.

## Task 3: verify and review

- Backend appropriate/full suites, frontend build/API/calendar unit tests, contract and relevant chat browser regressions on isolated runtime. Generate deterministic sample PDF; check AcroForm, widgets/appearance/blank signatures then render affected official pages for visual inspection.
- Independent scoped code review and targeted fixes. Preserve originalcase record snapshot `/tmp/lease-autofill-original-case.json`. Baseline `/tmp/lease-autofill-baseline`. Restart main preview only when backend passes; temporary testserver stopped, main5191 remains usable. No commits/publishing.

Progress: complete. Address search, structured PDF fields, calendar-term form controls and common additional fields are implemented. Review fixes preserve AI explicit custom dates, clear hidden presets when type is cleared, distinguish pure locality/postal searches from street input, and reject compound durations (including truncated model quotes) instead of shortening them to a preset.

Verification on 2026-10-23:
- Backend: 217 full-server tests passed; 51 covering tests passed. Parent independently reran address/draft tests: 23 passed.
- Frontend: TypeScript/Vite build passed; 14 API/calendar/address unit tests passed; 7 contract browser tests and 3 candidate/chat follow-up browser tests passed on isolated runtime5195.
- Real configured qwen-plus provider: two fictitious rental descriptions extracted literal tenant name, weekly rent/period and bond; the second also grounded fixed12months/start2026-11-01. Browser AI extraction required user consent and review before filling; it did not save a draft automatically.
- Actual browser-generated PDF `/tmp/lease-autofill-browser.pdf` contains complete20-page official form plus cover. Landlord/tenant Redfern/NSW/2016 and agent Burwood/NSW/2134 populate separate boxes;6months checkbox and31Aug2026→28Feb2027 dates match. Affected PDF pages and desktop/mobile form screenshots inspected; no clipping or page errors observed.
- Independent scoped review `/tmp/lease-autofill-review.md` closes all fourP2 findings, no remainingP1/P2.
- All45 original-case records match `/tmp/lease-autofill-original-case.json`;500-listing/71-suburb catalogue fingerprint remains `03302a834d238d453d6bcc880ec2d7c31d704a8cb0cb3421013252a67f6429dc`.
- Main5191/8011 restarted with frozen backend. Read-only address queries and original-case desktop/mobile load passed with zero writes/errors. Isolated5195/8015 stopped; main preview remains running. No commits or publishing performed.

Address search covers the existing NSW catalogue and its locality/postcode pairs only. Unmatched addresses can be entered manually; this is not a comprehensive NSW address-validation service and no paid mapping API is used.
