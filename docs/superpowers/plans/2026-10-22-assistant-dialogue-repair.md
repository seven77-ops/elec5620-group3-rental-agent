# Rental dialogue repair

User feedback on the approved assistant design identifies a broken multi-turn intake flow. Scope is the existing Agent1/2 conversation; keep existing authorization and confirmation boundaries. No commits or unrelated refactoring.

Root cause reproduced: the starter receives a generic missing-preferences template, the next turn is classified as a one-off search, and zero results receive no catalogue-backed diagnosis. No structured conversation brief or last-query filters are persisted.

Design: a validated conversation-only rental brief stores explicitly supplied core conditions. Agent1 intake asks only the next missing question, including weekly/monthly and per-person/whole-property budget scope. Agent2 previews use that brief or the last query plus explicit updates. Empty results compute single-condition alternatives from the current catalogue; suggestion buttons only populate the composer. They never change budget, saved preferences or execute a request on their own. Full Agent1 confirmation stays explicit.

- [x] Add failing backend regressions for multi-turn brief, missing units, confirmed preference isolation, follow-up searches, catalogue-backed alternatives and strict schema.
- [x] Implement brief/schema/prompt, focused intake question generation, real search diagnosis and proposal composition using existing transactional flow.
- [x] Add suggestion action rendering and browser regression proving clicks only fill the composer.
- [x] Verify actual Qwen with the user's reproduced sequence in an isolated runtime, backend/browser regressions and build.
- [x] Restart original preview, verify original case/conversation preservation and document evidence.
