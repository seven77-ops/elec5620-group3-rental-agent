# USYD student commute verification — 2026-10-27

The public rental flow now targets USYD Camperdown/Darlington students, using the verified Fisher Library facility point. Old destination choices and non-main-campus results cannot continue as current main-campus recommendations. Explicit time ceilings exclude excessive and unknown durations. Arrival time, travel day/date and transfer limits survive confirmation and page navigation; incompatible baseline observations need recent checked routes. A report's commute evidence is versioned, and expiry is checked again before saving a candidate.

After the same-day expansion, the catalogue has 700 annotation records: 446 official building origins (425 exact matches and 21 disclosed building-number range endpoints), 445 scheduled transit observations and 446 observations for each road mode. The remaining 254 null-origin houses now have explicitly labelled coarse ranges, following the user’s new fallback authorization. See [the expansion verification](2026-10-27-usyd-expansion.md). See [the source and coverage specification](../../agent2/data/real/README-usyd.md).

## Initial implementation checks (before the 200-house expansion)

- Server regression suite: 364 passed.
- Agent1 suite: 52 passed. Agent2 suite, run from its package directory: 89 passed.
- Frontend unit tests: 21 passed. TypeScript and Vite production build succeeded.
- Browser: 16 passed, including actual 20-minute inventory filters, seven-mode listing details, phone layout, legacy destination retirement, chat-to-profile-to-report sync and previous form/UI regression cases.
- Real configured AI and TfNSW in an isolated temporary case: public transport to USYD main campus by weekday 10:00, budget AUD1200/week, one bedroom and one bathroom, maximum20 minutes returned10 houses with planned durations12–17 minutes. Changing to cycling20 minutes returned12 displayed houses with network estimates below20. Changing to UNSW returned the explicit scope response with no housing recommendations.
- Current website after restart: http://127.0.0.1:5191 and API8011 healthy. Walking20 minutes with weekly rent1200 returns11 annotated houses; every returned duration is at most20. The original129 stored user objects have identical before/after hashes.
- Read-only review and regressions covered SQLite nested-transaction avoidance, whole-criteria matching, stale evidence producing a different report, refusal to select expired routes, and mode-specific source/age validation.

No paid Google API was added. No real user case was changed during testing. Public addresses were used for external location and route collection; tenant/landlord notice addresses were excluded. A separate three-address OpenStreetMap check returned only street-level positions and was not used as house coordinates. Temporary test servers were stopped after verification.
