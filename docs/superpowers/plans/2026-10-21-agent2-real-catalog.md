# Agent2 real catalogue implementation plan

**Goal:** use the 500 real advertisements in the production Agent2 API and website without fabricated missing facts or simulated fallbacks.

**Architecture:** a validated bundled catalogue feeds an Agent2 real evaluator and existing saved-object repository. Agent1 continues to own confirmed profiles. Real selections remain provisional and are gated before the legacy contract workflow.

**Tech stack:** Python/FastAPI/SQLite and React/Ant Design/TypeScript.

- [x] Write server regression tests for default real mode, catalogue integrity/filtering and provisional evaluation/selection boundaries; run to confirm failure.
- [x] Bundle `agent2/data/real/listings.json`; implement `server/app/real_data/catalog.py` and `server/app/adapters/real_agent2.py`; wire defaults in Settings, routes and app factory. Retain explicit fixture injection for legacy regression tests only.
- [x] Replace the recommendation route with paginated real catalogue browsing, filters, details and current-profile candidate saving. Update mode labels and guard legacy contract UI.
- [x] Add meaningful browser coverage for all four core facts, filtering, pagination, empty state, evaluating and saving a candidate, refresh persistence, and unknown fields.
- [x] Run server regressions, frontend build/API tests and targeted browser tests; inspect desktop/mobile screenshots; request independent code review and fix material findings.
- [x] Restart the existing 5191/8011 preview, verify the existing case loads real data, and document real API semantics and limits.

Validation commands: `.venv/bin/python -m unittest discover -s server/tests -v`; `npm run build`; `npm run test:api`; `WEB_TEST_BASE_URL=http://127.0.0.1:5193 npm run test:e2e -- agent2-real.spec.ts real-data.spec.ts`.
