# Agent2 real catalogue integration

User authorization: use the collected real data in the website and backend; stop using simulated listings. The four essential fields are bedrooms, bathrooms, car spaces and advertised weekly rent. Other facts remain unknown.

The default server bundles the audited 500-ad snapshot, with source URLs and collection metadata. A missing or malformed snapshot fails closed; there is no demo-data fallback. Legacy synthetic data remains only for explicitly injected regression fixtures.

GET /api/v1/listings provides validated filters, stable sorting and server pagination. GET /api/v1/listings/{id} returns source facts and unknowns. Confirmed Agent1 profiles bind evaluations to the case/profile and catalogue fingerprints. Evaluation reports provide provisional candidates and never invent comparable costs, routes, market estimates or evidence completeness. Advertised-price filters operate on the advertisement amount, not per-person affordability.

The recommendations webpage uses this API, displays the four core facts, all 71 suburb options, and source/freshness information, with pagination and detail views. It supports saving a candidate against a current confirmed evaluation. Historical synthetic reports remain readable/exportable but cannot be selected in the real catalogue flow. A real candidate snapshot is not a certified contract handoff; downstream Agent3 currently requires further integration and must reject it clearly.

Test catalogue integrity, filters, empty states, pagination, immutable snapshots, profile/version and request-ID conflicts, legacy selection rejection, selection replay, and downstream/AI gates. Validate desktop/mobile UI and normal preferences-to-candidate flow. Preserve existing local cases and unrelated Agent3/4 behavior.
