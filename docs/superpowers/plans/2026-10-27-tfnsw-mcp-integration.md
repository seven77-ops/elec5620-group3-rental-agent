# TfNSW MCP Integration Implementation Plan

**Goal:** Connect the approved local TfNSW MCP to Agent2 and the existing chat, preserving strict USYD commute criteria and existing case data.

**Architecture:** A pinned MIT upstream server runs in an isolated environment on loopback. A bounded HTTP MCP adapter in the existing backend converts read-only tool results to the current commute DTO. Existing direct TfNSW queries remain the failure fallback; invalid or late routes never gain eligibility. Agent1 and saved-profile confirmation remain unchanged.

**Tech stack:** Existing FastAPI/httpx stack; upstream MCP2.1.1 in its separate locked environment; existing React/Ant Design UI.

- [x] Add failing protocol/DTO tests for key handling, local-only endpoints, SSE/JSON limits, time arithmetic, transfers, provider fallback and privacy.
- [x] Vendor pinned upstream source/license/lock and add reproducible setup and lifecycle scripts. Keep its dependencies out of the website environment.
- [x] Implement MCP HTTP client and trip conversion; connect planner and expose provider metadata without secrets.
- [x] Add bounded nearby-stop and service-alert chat intents using known catalogue IDs and coordinates only.
- [x] Display concise route steps and transit information in existing UI; retain actual source and unknown/error states.
- [x] Verify offline integration, real MCP queries, real AI conversation and browser flow in isolated case storage; request read-only review and fix findings.
- [x] Restart existing website, compare stored-object hashes and document exact coverage/limits.

Constraints: fixed Fisher Library reference; per-call X-API-Key from backend only; no private notice addresses; no external MCP URL; no invented times or automatic preference edits; no paid Google API; bounded calls and fallback must not turn failure into fabricated success. This plan implements the user's approval of the preceding assessment; no further approval is needed.
