# Shared rental assistant

The conversation is a shared product entry point. Agent1 owns preference collection and confirmation, Agent2 owns real listing retrieval and comparison, Agent3 owns contracts, and Agent4 owns aftercare. This iteration implements conversation-driven Agent1/2 work and explicit links into the existing Agent3/4 pages.

## Interaction and reference

Reference: [Dubai AI Broker Assistant](https://github.com/nazsats/dubai-real-estate), inspected at commit `59451b87a7393e16203e091d39f3332ed132e7b9`. The useful patterns were a slim conversation history, a central conversation workspace, starter questions, a bottom composer, and property cards inside the conversation. The implementation uses the existing white and `#174EA6` theme and original components; it does not copy the reference's dark/gold styling or code.

The new `AI租房助手` navigation item spans the workflow. New cases start there; the preference form also provides a conversation shortcut. Recommendations retain the manual catalogue workflow with a more compact header and optional source/tool details. There are no invented property photographs.

## Execution boundary

Qwen extracts a typed intent and parameters. The server validates the complete object, then runs a predefined operation against the real catalogue or Agent1 adapters. Displayed facts and rent comparisons are computed from catalogue records. The model does not write preference versions, select candidates, approve contracts, or generate missing listing facts.

Preference changes produce a full condition summary, including inherited values. Applying a proposal requires explicit confirmation and runs Agent1 draft/confirm and Agent2 real evaluation in one transaction. Preview searches do not change saved preferences. Conversation revisions, case signatures and durable request IDs guard stale changes and duplicate submissions. External model calls run outside database transactions, and each sent message requires consent to use external AI.

## Verification scope

The real model check uses an isolated local runtime with generic rental requests. It exercises search, comparing the returned IDs, preference changes, unknown-data questions, contracts and aftercare. A separate browser integration app replaces only the model transport; its catalogue, Agent1 confirmation and Agent2 evaluation remain real. Neither test changes the user's existing case.

Final checks on 2026-10-22: all 6 live `qwen-plus` intent checks passed, including matching the searched core facts and the first two displayed IDs in order. The full UI/backend integration produced five real cards, compared two explicitly selected cards, confirmed a new Agent1 version, created an Agent2 report, survived reload, and fit a 360px viewport without browser errors. All 114 server tests, 52 Agent1 tests, 9 frontend API tests and 17 scoped browser tests passed. TypeScript/Vite production build and `git diff --check` passed; Vite retains its existing large shared vendor chunk warning.

The original preview was restarted at `http://127.0.0.1:5191` with `.runtime/real-data-local`. The original case retained draft revision 4, three confirmations and four evaluations; its complete JSON hash was unchanged by the read-only check. Temporary browser-test servers were stopped.

Current limitations: source ads are snapshots whose live availability and billing scope require verification. Noise, commute, bills and move-in facts cannot be inferred from the four core housing fields. Agent3/4 conversation requests currently navigate to their existing pages. Open-ended question answering and full contract/aftercare chat execution are not part of this iteration.
