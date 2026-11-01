# Living services and chat implementation plan

**Goal:** Expand the approved Agent4 flow to repairs during tenancy, saved utility providers, real moving/cleaning contacts and shared chat actions while retaining existing move-out/bond workflows.

**Architecture:** Case-owned living-service records in the existing repository, a verified official-site provider directory, explicit versioned profile/repair/booking writes and reusable confirmation proposals. AI intent routing reads the same profile and directory and proposes changes for user confirmation. New React hub wraps legacy aftercare and links to real official/company sites.

**Constraints:** Existing dirty work is preserved; no commit or publish. No messages sent, bookings submitted, payment or real-account modifications. Email is a reviewed mailto/copy draft. Official website links and only verified phone numbers; no invented rates/ratings/availability. User address and account numbers are not shared with suppliers by the app. Water supplier is not presented as competitively switchable. Actual clock and blank real tenancy forms replace demo defaults only in real mode; historic demo behavior remains supported. Test with isolated cases.

- [x] Verify official websites/contact pages for NSW energy/internet/water and Sydney removalists/cleaners; persist provenance and verification date in `server/app/living/providers.json`.
- [x] Implement `server/app/living/service.py` and tests: case-owned versioned profile, utility choices, repair drafts/status, service bookings, confirmed proposal apply with receipt/conflict guards. Define API contract below before frontend work.
- [x] Implement `frontend/src/features/living/` and `frontend/src/api/living.ts`: four-tab hub, contact/profile editing, repair drafts with explicit open-email action, utility selectors with official links, real provider cards and recorded quote/appointment status. Keep Ant Design white/blue and 360px responsive layout.
- [x] Register routes; extend assistant schema/prompt/tools and action UI for `living_services` queries and confirmed data changes using the same case record; browser and actual-model scenarios must cover utility choice and repair draft without automatic writes.
- [x] Update real aftercare tenancy initial values and real clock, preserving legacy Agent4 functions; do not infer a signed tenancy from a generated draft.
- [x] Run backend full suite, Agent4 regressions, frontend build/API tests and browser flow; inspect desktop/mobile, true-model smoke tests, no browser errors, and original saved-case preservation. Record scope and results; leave original preview running.

## API contract

Provider directory: `GET /api/v1/living-providers` -> `{checked_on,providers:[{id,name,categories,website,contact_url,phone,coverage,source_url,checked_on,notes}]}`.

Case root `/api/v1/cases/{case_id}/living-services`:
- `GET /` -> `{case_id,version,profile,repairs,bookings,updated_at}`. Profile fields: address,suburb,postcode,agent_name,agent_email,agent_phone,emergency_phone,move_out_date,bedrooms,bathrooms,carpeted,has_pets,moving_to,has_elevator,own_furniture,landlord_furniture,utilities (`electricity`,`gas`,`internet`,`water`: provider ID or null),notes. Empty defaults; candidate address can be suggested with explicit source indication.
- `POST /profile` -> record. Body `{request_id,expected_version,confirmed:true,values:<full profile>}`.
- `POST /repairs` -> record. Body `{request_id,expected_version,confirmed:true,values:{title,description,location,priority:'normal'|'urgent'}}`. Repair entry has repair_id,status:'prepared'|'contacted'|'resolved',created_at and email:{to,subject,body,delivery_status:'prepared_not_sent'}.
- `POST /repairs/{repair_id}` -> record. Body same envelope; values `{status:'prepared'|'contacted'|'resolved'}`.
- `POST /bookings` -> record. Same envelope values `{provider_id,booking_id?:string,service_date:string|null,quote_amount:number|null,status:'considering'|'contacted'|'booked'|'completed',notes:string}`. Provider must be cleaner/removalist, booking updates case-owned.
- `POST /proposals/{proposal_id}/apply` -> record. `{request_id,expected_version,confirmed:true}`. Proposal creation is internal service `prepare_proposal(case_id,kind,values,source_message)` -> `{proposal_id,kind,summary,expected_version,status:'pending'}`; kind profile (partial merge) or repair. It does not mutate living profile/repairs/bookings. Apply checks case and exact version; duplicate request ID replays its receipt.

Profile and service endpoint failures use existing API error envelopes. Root owns routes, assistant integration, source research and real-clock adapter changes. Backend worker owns living package except provider JSON; frontend worker owns living UI/API plus existing Aftercare/TenancyForm/App wiring, never assistant files. These are independent modules against the frozen contract above.

## Completion

Implemented local JPEG/PNG/PDF evidence uploads alongside the approved living flows. Final verification: 175 server tests, 57 Agent4 tests, 9 frontend API tests, 22 browser scenarios, production build, 5 real qwen-plus cases, desktop/mobile visual checks, and original case/chat preservation all passed. Details: `docs/frontend/2026-10-22-living-services.md`. Original preview remains at ports 5191/8011; isolated test services are stopped after verification.
