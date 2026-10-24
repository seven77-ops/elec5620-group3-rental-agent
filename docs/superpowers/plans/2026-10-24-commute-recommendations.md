# Commute-based area and housing recommendation implementation plan

**Goal:** Deliver the approved chat intake → confirmed destination → real address location → TfNSW routes → budget/commute area and listing recommendations → explained tradeoffs loop.

**Architecture:** Extend conversation-only rental brief without guessing from example profiles. A bounded data service resolves NSW locations and calculates real door-to-destination public transport plans. Server facts rank candidates; the model extracts requirements only. Optional structured results are shared with recommendations page. No paid Google API; ordinary outbound Maps links only.

**Tech stack:** Existing Python/FastAPI/httpx/SQLite and React/Ant Design/Qwen. Reuse existing DataProviders.trips; no new dependency.

## Global constraints
- Preserve user's original case, existing 500-listing catalogue/fingerprint and all previous Agent1–4 work; reuse existing suitable isolated checkout. Mutating QA uses /tmp runtime only. No commits/publishing.
- White and blue UI, 房源 terminology. Real public data only; never fabricate coordinates, route durations, unknown costs/quietness/availability or infer campuses. No paid maps.
- New external location/transport queries require per-turn external-data consent. Secret stays server-side. Provider failures/missing key/ambiguous addresses remain visible; unknown routes cannot satisfy a hard commute limit.
- Existing profile confirmation, candidate selection, contract draft and living services behavior remains intact. Preview does not silently change confirmed needs. No SQLite transaction held across external data/model calls.

## A. Real location and bounded route service (delegated implementer)
Files: NEW server/app/commute/{__init__,locations,planner}.py; focused tests server/tests/test_commute_data.py. Own only these files.
- [x] Tests first: NSW location choices are source-backed and bounded; listing matching cannot use suburb centroid or unrelated first result; malformed/ambiguous upstream returns no invented point; missing TfNSW key, consent, timing, day, route errors, unknown hard-limit and ranking covered.
- [x] `LocationResolver(transport=None).search(query,limit=5)` returns list `{id,label,latitude,longitude,precision,source_url}` using a verified official NSW address/POI service. `.listing(row)` returns source-backed building/address point or None; caches locally in instance. Source data precision disclosed.
- [x] `CommutePlanner(ctx,resolver=None).prepare(brief,destination,allow_external=False)` returns ordinary assistant answer plus optional `commute_recommendation` below. `ctx.settings.catalog`, `ctx.data_provider`, `ctx.repo` available. Provider calls strictly outside caller transaction.
- [x] Brief slots: existing budget_amount, budget_period, budget_scope, min_bedrooms/min_bathrooms/min_car_spaces, suburb/rental_mode/occupants; new recommend_areas bool, destination_query str, destination_id str, arrival_time HH:mm, commute_max_minutes integer1..240, commute_hard_limit bool, commute_priority balanced/rent/commute, max_transfers integer0..5, travel_day weekday/weekend, travel_date optional YYYY-MM-DD, commute_mode public_transport/walk/drive/bike. V1 actual routes support public_transport; others visibly unsupported.
- [x] Inventory filter before external calls; bounded <=12 candidate routes with balanced suburb coverage, no claim exhaustive entire city. Total matching count distinguished from evaluated count. Valid route includes wait/transfer gaps via existing provider total duration. Next matching weekday/weekend when no date; Australia/Sydney timezone and actual arrival_time. Source+datetime retained. No price division or per-person affordability claims when rent_scope unknown.
- [x] Result schema: answer `{intent:'recommend_areas',agent:'agent2',content,listings,actions:[],commute_recommendation:{status:'ready'|'partial'|'unavailable',destination,criteria:brief,queried_at,date,arrival_time,total_matching,evaluated_count,query_limit,areas:[{suburb,count,min_weekly_rent,max_weekly_rent,fastest_minutes:number|null,verified_route_count,reasons:string[],tradeoffs:string[]}],routes:[{listing_id,status:'ok'|'unavailable'|'unsupported'|'over_limit',duration_minutes:number|null,walking_minutes:number|null,transfers:number|null,departure_at:string|null,arrival_at:string|null,source_url,origin_precision,reason}],limitations:string[]}}`. Case-local route cache optional, freshness explicit; do not mutate case/profile.

## B. Conversation routing / shared preview (root)
Files: assistant/dialogue.py,intents.py,service.py; NEW assistant/commute.py; provider.py; assistant/routes.py.
- [x] Tests first for opt-in area recommendation intake, unknown area allowed, incremental requirements, destination ambiguity/selection validation, no external call without consent, updates preserve unrelated slots, no mutation of case.
- [x] Add recommend_areas intent with brief_patch; extract above slots, model sees only known destination choices, never generates coordinates or route facts. Questions ask budget units/housing, destination, arrival and commute ceiling in focused groups; old ordinary preference flow remains unchanged.
- [x] Resolve destination choices after consent, display choices and require explicit valid ID before routing. Public destination_options on message; selected ID maps to latest retained server choices in owned conversation; new destination_query invalidates old selection. Persist conversation brief/options and report only after existing optimistic checks. Named followups update same slots.
- [x] New optional turn allow_external_data=false (backwards compatible). Latest commute recommendation endpoint under owned case; store report case/profile/catalog fingerprints and source conversation revision; do not show stale preview as current after requirements change.

## C. Frontend and verification (root)
Files: api/assistant.ts; NEW features/assistant/CommuteResults.tsx,commuteResults.css; Assistant.tsx; RealRecommendations.tsx.
- [x] Structured destination-choice suggestions populate composer and await explicit send; show area options, route time/walk/transfers/source/date, missing-key/partial coverage honestly; listing detail/source/save use existing guards.
- [x] Same latest result accessible on recommendations page with stale-state disclosure and link back to chat. Existing manual catalogue filters remain available. New consent copy includes location/transport services, request boolean sent per turn.
- [x] New e2e fixtures for destination choices, partial/no-key result, hard-limit unknown, mobile and shared page. Actual configured Qwen multi-turn test in isolated runtime, actual public location queries as available, provider fixture tests cover key-dependent route path. Report live-TfNSW limitation if key remains missing.
- [x] Full backend, frontend build/unit and focused regressions. Independent readonly scoped review; fix material findings and retest. Main preview restart after checks, verify original case45objects/catalogue unchanged, clean test server only.


## Completion evidence and external prerequisites
- Final full backend: 303 tests passed in 34.685s (`/tmp/commute-upgrade-full-server-final.log`). Frontend 14 unit checks, production build and diff check passed. Existing large vendor chunk advisory retained.
- Browser regression: 20 tests passed; final 2 commute presentation tests rerun after compact copy changes. Actual configured Qwen verified newcomer intake, explicit official campus choice, 40→50 minute amendment, rent priority and commute priority. Actual browser sent a 55 minute amendment and verified the same criteria on recommendations page, 360px layout and pending map links without save actions.
- Official small location queries verified universities, campus-qualified searches, Redfern and street addresses. Source point precision is disclosed. No live TfNSW minute result is claimed while the key is missing.
- Independent scoped review `/tmp/commute-upgrade-review.md`: three substantive findings closed (campus field matching, arrival deadline validation, and direct saved-field proposal preserving the commute brief). Real model choice-query relabel and priority extraction issues also received focused fixes and verification.
- Main preview 5191/8011 restarted with the same user runtime. All 45 original case objects and the 500-listing catalogue fingerprint are unchanged. No commits or publishing.
- External prerequisites remain: user will configure local TFNSW_API_KEY; it was absent at the last check. The 500-address harvest was rejected by automatic approval review and has NOT executed. Concrete payload `/tmp/commute-geocoding-review.json` is ready; explicit user authorization question is pending. Optional validated sidecar loader is ready, but no sidecar has been created and no data-export workaround was attempted.
